import base64
import json
import logging
import os
from typing import Any, Dict, Optional

import requests

from ..api.base import APIClient

logger = logging.getLogger(__name__)


class PerplexityClient(APIClient):
    """
    Perplexity API client implementation with persistent system prompt support.
    """

    def __init__(self, api_key: str, **kwargs):
        """
        Initialize Perplexity API client.

        Args:
            api_key: Perplexity API key
            **kwargs: Additional configuration parameters
        """
        self.api_key = api_key
        self.max_tokens = kwargs.get("max_tokens", 2500)
        self.temperature = kwargs.get("temperature", 0.7)
        # Add conversation history tracking
        self.max_history_messages = kwargs.get("max_history_messages", 10)
        self.conversation_history = []

        # API endpoint - verify this is current
        self.api_url = os.getenv("PERPLEXITY_API_URL", "https://api.perplexity.ai/chat/completions")

        # Updated default model name for 2025
        self.default_model = "llama-3-sonar-small-32k-online"

        logger.info("Initialized Perplexity API client")

    def send_text_message(self, message: str, ai_config: Dict[str, Any]) -> tuple[Optional[str], Optional[str]]:
        """
        Send text message to Perplexity API.

        Args:
            message: Message text to send
            ai_config: AI configuration dictionary

        Returns:
            AI response text or None if failed
        """
        try:
            # Get model from config or environment or use default
            model = ai_config.get("api_model", os.getenv("PERPLEXITY_MODEL", self.default_model))

            # Get system prompt from config
            system_prompt = ai_config.get("system_prompt", "")

            # Add user message to conversation history
            self.conversation_history.append({"role": "user", "content": message})

            # Trim conversation history if it exceeds max length
            if len(self.conversation_history) > self.max_history_messages:
                self.conversation_history = self.conversation_history[-self.max_history_messages :]

            # Log model being used
            logger.info(f"Using Perplexity model: {model}")

            # Create full messages list with system prompt + conversation history
            full_messages = []

            # Add system message if it exists
            if system_prompt:
                full_messages.append({"role": "system", "content": system_prompt})

            # Add conversation history
            full_messages.extend(self.conversation_history)

            # Prepare request payload with system prompt and conversation history
            payload = {
                "model": model,
                "messages": full_messages,  # Use system prompt + conversation history
                "max_tokens": self.max_tokens,
                "temperature": self.temperature,
            }

            # Set up headers with API key
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }

            # Add debug logging
            logger.debug(f"Sending request to Perplexity API: {self.api_url}")
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
                logger.error(f"Perplexity API error: {response.status_code} - {response.text}")
                return None, None

            # Parse response JSON
            response_data = response.json()

            # Add debug logging
            logger.debug(f"Perplexity API response: {response_data}")

            # Extract response text
            response_text = response_data.get("choices", [{}])[0].get("message", {}).get("content", "")

            # Add assistant response to conversation history (not including system prompt)
            self.conversation_history.append({"role": "assistant", "content": response_text})

            logger.info(f"Received response from Perplexity API: {response_text[:50]}...")

            return response_text, None

        except requests.exceptions.RequestException as e:
            logger.error(f"Request error with Perplexity API: {e}")
            return None, None
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error with Perplexity API response: {e}")
            return None, None
        except Exception as e:
            logger.error(f"Error sending text to Perplexity API: {e}")
            return None, None

    def send_image(self, image_path: str, ai_config: Dict[str, Any]) -> tuple[Optional[str], Optional[str]]:
        """
        Send image to Perplexity API.

        Note: As of 2025, Perplexity may not support image inputs directly.
        This implementation falls back to browser automation if the API call fails.

        Args:
            image_path: Path to image file
            ai_config: AI configuration dictionary

        Returns:
            AI response text or None if failed
        """
        try:
            # This is a best-effort implementation that may need updates based on
            # Perplexity's API capabilities in 2025

            content_type = "image/jpeg"

            # Get model from config or environment
            model = ai_config.get(
                "api_vision_model",
                ai_config.get("api_model", os.getenv("PERPLEXITY_MODEL", self.default_model)),
            )

            # Get system prompt from config
            system_prompt = ai_config.get("system_prompt", "")

            # Read image file and encode as base64
            with open(image_path, "rb") as image_file:
                base64_image = base64.b64encode(image_file.read()).decode("utf-8")

            # Get prompt from config
            prompt = ai_config.get("image_prompt_template", "Describe this image briefly.")

            # Add image prompt to conversation history (text only)
            self.conversation_history.append({"role": "user", "content": prompt})

            # Trim conversation history if it exceeds max length
            if len(self.conversation_history) > self.max_history_messages:
                self.conversation_history = self.conversation_history[-self.max_history_messages :]

            # Create full messages list
            messages = []

            # Add system message if it exists
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})

            # Add conversation history except the last message
            if len(self.conversation_history) > 1:
                messages.extend(self.conversation_history[:-1])

            # Add the image message for the current request
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

            # Prepare request payload - using OpenAI-compatible format
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
            logger.debug(f"Sending image request to Perplexity API: {self.api_url}")

            # Make API request
            response = requests.post(
                self.api_url,
                headers=headers,
                json=payload,
                timeout=30,  # Add timeout for reliability
            )

            # Check for successful response
            if not response.ok:
                logger.error(f"Perplexity API error with image: {response.status_code} - {response.text}")
                logger.warning("Perplexity API may not support image inputs; falling back to browser automation")
                return None, None

            # Parse response JSON
            response_data = response.json()

            # Extract response text
            response_text = response_data.get("choices", [{}])[0].get("message", {}).get("content", "")

            # Add assistant response to conversation history
            self.conversation_history.append({"role": "assistant", "content": response_text})

            logger.info(f"Received image description from Perplexity API: {response_text}")

            return response_text, None

        except requests.exceptions.RequestException as e:
            error_message = str(e)
            logger.error(f"Request error with Perplexity API: {error_message}")
            logger.warning("Perplexity API may not support image inputs; falling back to browser automation")
            return None, None
        except Exception as e:
            logger.error(f"Error sending image to Perplexity API: {e}")
            return None, None

    def clear_conversation_history(self):
        """
        Clear the conversation history.
        """
        self.conversation_history = []
        logger.info("Cleared conversation history")
