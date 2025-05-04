import base64
import json
import logging
import os
from typing import Any, Dict, Optional

import requests
from openai import OpenAI

from ..api.base import APIClient

logger = logging.getLogger(__name__)


class GrokClient(APIClient):
    """
    Grok API client implementation with persistent system prompt support.

    Note: This implementation follows official Grok API documentation patterns.
    """

    def __init__(self, api_key: str, **kwargs):
        """
        Initialize Grok API client.

        Args:
            api_key: Grok API key
            **kwargs: Additional configuration parameters
        """
        self.api_key = api_key
        self.max_tokens = kwargs.get("max_tokens", 1500)
        self.temperature = kwargs.get("temperature", 0.7)
        self.client = OpenAI(api_key=self.api_key, base_url="https://api.x.ai/v1")
        self.max_history_messages = kwargs.get("max_history_messages", 10)
        self.conversation_history = []

        # API endpoint updated based on official documentation
        self.api_url = os.getenv("GROK_API_URL", "https://api.x.ai/v1/chat/completions")

        # Default model for 2025
        self.default_model = "grok-2"

        logger.info("Initialized Grok API client")

    def send_text_message(self, message: str, ai_config: Dict[str, Any]) -> tuple[Optional[str], Optional[str]]:
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

            # Get system prompt from config
            system_prompt = ai_config.get("system_prompt", "")

            # Add user message to conversation history
            if not hasattr(self, "conversation_history"):
                self.conversation_history = []
                self.max_history_messages = 10  # Default value if not set in __init__

            self.conversation_history.append({"role": "user", "content": message})

            # Trim conversation history if it exceeds max length
            if len(self.conversation_history) > self.max_history_messages:
                self.conversation_history = self.conversation_history[-self.max_history_messages :]

            # Log model being used
            logger.info(f"Using Grok model: {model}")

            # Prepare messages with system prompt and conversation history
            formatted_messages = []

            # Add system message if it exists
            if system_prompt:
                formatted_messages.append({"role": "system", "content": [{"type": "text", "text": system_prompt}]})

            # Add conversation history
            for msg in self.conversation_history:
                formatted_messages.append({"role": msg["role"], "content": [{"type": "text", "text": msg["content"]}]})

            payload = {
                "model": model,
                "messages": formatted_messages,
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
                fallback_url = os.getenv("GROK_FALLBACK_URL", "https://api.grok.ai/v1/chat/completions")
                logger.info(f"Trying fallback Grok API URL: {fallback_url}")

                response = requests.post(fallback_url, headers=headers, json=payload, timeout=30)

                if not response.ok:
                    logger.error(f"Fallback Grok API error: {response.status_code} - {response.text}")
                    return None, None

            # Parse response JSON
            response_data = response.json()

            # Add debug logging
            logger.debug(f"Grok API response: {response_data}")

            # Extract response text
            response_text = response_data.get("choices", [{}])[0].get("message", {}).get("content", "")

            # Add assistant response to conversation history
            self.conversation_history.append({"role": "assistant", "content": response_text})

            logger.info(f"Received response from Grok API: {response_text[:50]}...")

            return response_text, None

        except requests.exceptions.RequestException as e:
            logger.error(f"Request error with Grok API: {e}")
            # Check if this is a DNS resolution error and suggest updating the URL
            if "nodename nor servname provided" in str(e) or "Failed to resolve" in str(e):
                logger.warning("DNS resolution error. Consider updating GROK_API_URL in .env")
            return None, None
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error with Grok API response: {e}")
            return None, None
        except Exception as e:
            logger.error(f"Error sending text to Grok API: {e}")
            return None, None

    def send_image(self, image_path: str, ai_config: Dict[str, Any]) -> tuple[Optional[str], Optional[str]]:
        """
        Send image to Grok API.

        Args:
            image_path: Path to image file
            ai_config: AI configuration dictionary

        Returns:
            AI response text or None if failed
        """
        try:
            # After compression, we know it's a JPEG
            content_type = "image/jpeg"

            # Get model from config or environment
            model = ai_config.get(
                "api_vision_model",
                ai_config.get("api_model", os.getenv("GROK_MODEL", self.default_model)),
            )

            # Get system prompt from config
            system_prompt = ai_config.get("system_prompt", "")

            # Read image file and encode as base64
            with open(image_path, "rb") as image_file:
                base64_image = base64.b64encode(image_file.read()).decode("utf-8")

            # Get prompt from config
            prompt = ai_config.get("image_prompt_template", "Describe this image briefly.")

            # Add user message to conversation history (text only)
            self.conversation_history.append({"role": "user", "content": prompt})

            # Prepare messages array
            messages = []

            # Add system message if it exists
            if system_prompt:
                messages.append({"role": "system", "content": [{"type": "text", "text": system_prompt}]})

            # Add image message
            messages.append(
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
            )

            # Prepare request payload following Grok's API format
            payload = {
                "model": model,
                "messages": messages,
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
                fallback_url = os.getenv("GROK_FALLBACK_URL", "https://api.grok.ai/v1/chat/completions")
                logger.info(f"Trying fallback Grok API URL for image: {fallback_url}")

                response = requests.post(fallback_url, headers=headers, json=payload, timeout=30)

                if not response.ok:
                    logger.error(f"Fallback Grok API error with image: {response.status_code} - {response.text}")
                    logger.warning("Grok API may not support image inputs; falling back to browser automation")
                    return None, None

            # Parse response JSON
            response_data = response.json()

            # Extract response text
            response_text = response_data.get("choices", [{}])[0].get("message", {}).get("content", "")

            # Add assistant response to conversation history
            self.conversation_history.append({"role": "assistant", "content": response_text})

            # Trim conversation history if needed
            if len(self.conversation_history) > self.max_history_messages:
                self.conversation_history = self.conversation_history[-self.max_history_messages :]

            logger.info(f"Received image description from Grok API: {response_text}")

            return response_text, None

        except requests.exceptions.RequestException as e:
            error_message = str(e)
            logger.error(f"Request error with Grok API for image: {error_message}")

            # Check if this is a DNS resolution error
            if "nodename nor servname provided" in error_message or "Failed to resolve" in error_message:
                logger.warning("DNS resolution error. Consider updating GROK_API_URL in .env")

            logger.warning("Falling back to browser automation")
            return None, None
        except Exception as e:
            logger.error(f"Error sending image to Grok API: {e}")
            return None, None
