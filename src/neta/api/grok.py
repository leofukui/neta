import base64
import json
import logging
import os
from typing import Any, Dict, Optional

import requests

from ..api.base import APIClient
from ..utils.image_processing import compress_image

logger = logging.getLogger(__name__)


class GrokClient(APIClient):
    """
    Grok API client implementation.

    Note: This implementation should be verified against official Grok API
    documentation as it becomes available.
    """

    def __init__(self, api_key: str, **kwargs):
        """
        Initialize Grok API client.

        Args:
            api_key: Grok API key
            **kwargs: Additional configuration parameters
        """
        self.api_key = api_key
        self.max_tokens = kwargs.get("max_tokens", 100)
        self.temperature = kwargs.get("temperature", 0.7)
        self.max_image_size_kb = kwargs.get("max_image_size_kb", 500)

        # API endpoint updated based on error - changed from api.grok.x to api.x.ai
        self.api_url = os.getenv("GROK_API_URL", "https://api.x.ai/v1/chat/completions")

        # Default model for 2025
        self.default_model = "grok-2"

        logger.info("Initialized Grok API client")

    def send_text_message(
        self, message: str, ai_config: Dict[str, Any]
    ) -> tuple[Optional[str], Optional[str]]:
        """
        Send text message to Grok API.

        Args:
            message: Message text to send
            ai_config: AI configuration dictionary

        Returns:
            AI response text or None if failed
        """
        try:
            # Get model from config or environment
            model = ai_config.get("api_model", os.getenv("GROK_MODEL", self.default_model))

            # Get prompt template from config
            prompt_template = ai_config.get("text_prompt_template")
            if not prompt_template:
                logger.warning("No text prompt template found in config, using raw message")
                prompt = message
            else:
                # Format prompt with message
                prompt = prompt_template.format(message=message)

            # Log model being used
            logger.info(f"Using Grok model: {model}")

            # Prepare request payload
            payload = {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": self.max_tokens,
                "temperature": self.temperature,
            }

            # Set up headers with API key
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }

            # Add debug logging
            logger.debug(f"Sending request to Grok API: {self.api_url}")
            logger.debug(f"Headers: {headers}")
            logger.debug(f"Payload: {json.dumps(payload)}")

            # Make API request
            response = requests.post(
                self.api_url,
                headers=headers,
                json=payload,
                timeout=30,  # Add timeout for reliability
            )

            # Check for successful response
            if not response.ok:
                logger.error(f"Grok API error: {response.status_code} - {response.text}")

                # Try fallback URL if primary fails
                fallback_url = os.getenv(
                    "GROK_FALLBACK_URL", "https://api.grok.ai/v1/chat/completions"
                )
                logger.info(f"Trying fallback Grok API URL: {fallback_url}")

                response = requests.post(fallback_url, headers=headers, json=payload, timeout=30)

                if not response.ok:
                    logger.error(
                        f"Fallback Grok API error: {response.status_code} - {response.text}"
                    )
                    return None, None

            # Parse response JSON
            response_data = response.json()

            # Add debug logging
            logger.debug(f"Grok API response: {response_data}")

            # Extract response text
            response_text = (
                response_data.get("choices", [{}])[0].get("message", {}).get("content", "")
            )
            logger.info(f"Received response from Grok API: {response_text[:50]}...")

            return response_text, None

        except requests.exceptions.RequestException as e:
            logger.error(f"Request error with Grok API: {e}")
            # Check if this is a DNS resolution error and suggest updating the URL
            if "nodename nor servname provided" in str(e) or "Failed to resolve" in str(e):
                logger.warning("DNS resolution error. Consider updating GROK_API_URL in .env")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error with Grok API response: {e}")
            return None
        except Exception as e:
            logger.error(f"Error sending text to Grok API: {e}")
            return None

    def send_image(
        self, image_path: str, ai_config: Dict[str, Any]
    ) -> tuple[Optional[str], Optional[str]]:
        """
        Send image to Grok API.

        Note: Check Grok's documentation for their latest multimodal API support.
        This implementation may need updating as their API evolves.

        Args:
            image_path: Path to image file
            ai_config: AI configuration dictionary

        Returns:
            AI response text or None if failed
        """
        try:
            # Compress image before sending
            compressed_image_path = compress_image(image_path, self.max_image_size_kb)

            # After compression, we know it's a JPEG
            content_type = "image/jpeg"

            # Get model from config or environment
            model = ai_config.get(
                "api_vision_model",
                ai_config.get("api_model", os.getenv("GROK_MODEL", self.default_model)),
            )

            # Read image file and encode as base64
            with open(compressed_image_path, "rb") as image_file:
                base64_image = base64.b64encode(image_file.read()).decode("utf-8")

            # Get prompt from config
            prompt = ai_config.get("image_prompt_template")
            if not prompt:
                logger.warning("No image prompt template found in config, using default")
                prompt = "Describe this image briefly."

            # Prepare request payload - format may need adjusting based on Grok's actual API
            payload = {
                "model": model,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:{content_type};base64,{base64_image}"},
                            },
                        ],
                    }
                ],
                "max_tokens": 60,
                "temperature": self.temperature,
            }

            # Set up headers with API key
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }

            # Add debug logging
            logger.debug(f"Sending image request to Grok API: {self.api_url}")

            # Make API request
            response = requests.post(
                self.api_url,
                headers=headers,
                json=payload,
                timeout=30,  # Add timeout for reliability
            )

            # Check for successful response
            if not response.ok:
                logger.error(f"Grok API error with image: {response.status_code} - {response.text}")

                # Try fallback URL if primary fails
                fallback_url = os.getenv(
                    "GROK_FALLBACK_URL", "https://api.grok.ai/v1/chat/completions"
                )
                logger.info(f"Trying fallback Grok API URL for image: {fallback_url}")

                response = requests.post(fallback_url, headers=headers, json=payload, timeout=30)

                if not response.ok:
                    logger.error(
                        f"Fallback Grok API error with image: {response.status_code} - {response.text}"
                    )
                    logger.warning(
                        "Grok API may not support image inputs; falling back to browser automation"
                    )
                    return None, None

            # Parse response JSON
            response_data = response.json()

            # Extract response text
            response_text = (
                response_data.get("choices", [{}])[0].get("message", {}).get("content", "")
            )
            logger.info(f"Received image description from Grok API: {response_text}")

            return response_text, None

        except requests.exceptions.RequestException as e:
            error_message = str(e)
            logger.error(f"Request error with Grok API for image: {error_message}")

            # Check if this is a DNS resolution error
            if (
                "nodename nor servname provided" in error_message
                or "Failed to resolve" in error_message
            ):
                logger.warning("DNS resolution error. Consider updating GROK_API_URL in .env")

            logger.warning("Falling back to browser automation")
            return None, None
        except Exception as e:
            logger.error(f"Error sending image to Grok API: {e}")
            return None, None
