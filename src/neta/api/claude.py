# File: neta/api/claude.py
import base64
import logging
import os
from typing import Any, Dict, Optional

# Anthropic library
from anthropic import Anthropic

from .base import APIClient

logger = logging.getLogger(__name__)


class ClaudeClient(APIClient):
    """
    Claude API client implementation.
    """

    def __init__(self, api_key: str, **kwargs):
        """
        Initialize Claude API client.

        Args:
            api_key: Claude API key
            **kwargs: Additional configuration parameters
        """
        self.api_key = api_key
        self.max_tokens = kwargs.get("max_tokens", 100)
        self.temperature = kwargs.get("temperature", 0.7)
        self.max_image_size_kb = kwargs.get("max_image_size_kb", 500)

        # Initialize Anthropic client
        self.client = Anthropic(api_key=self.api_key)
        logger.info("Initialized Claude API client")

    def send_text_message(
        self, message: str, ai_config: Dict[str, Any]
    ) -> tuple[Optional[str], Optional[str]]:
        """
        Send text message to Claude API.

        Args:
            message: Message text to send
            ai_config: AI configuration dictionary

        Returns:
            AI response text or None if failed
        """
        try:
            # Get model from config or environment
            model = ai_config.get("api_model", os.getenv("CLAUDE_MODEL", "claude-3-opus-20240229"))

            # Get prompt template from config
            prompt_template = ai_config.get("text_prompt_template")
            if not prompt_template:
                logger.warning("No text prompt template found in config, using raw message")
                prompt = message
            else:
                # Format prompt with message
                prompt = prompt_template.format(message=message)

            # Call Claude API
            response = self.client.messages.create(
                model=model,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                messages=[{"role": "user", "content": prompt}],
            )

            # Extract response text
            response_text = response.content[0].text
            logger.info(f"Received response from Claude API: {response_text[:50]}...")

            return response_text, None

        except Exception as e:
            logger.error(f"Error sending text to Claude API: {e}")
            return None, None

    def send_image(
        self, image_path: str, ai_config: Dict[str, Any]
    ) -> tuple[Optional[str], Optional[str]]:
        """
        Send image to Claude API using vision capabilities.

        Args:
            image_path: Path to image file
            ai_config: AI configuration dictionary

        Returns:
            AI response text or None if failed
        """
        try:
            # Compress image before sending
            compressed_image_path = self._compress_image_for_api(image_path, self.max_image_size_kb)

            # After compression, we know it's a JPEG
            content_type = "image/jpeg"

            # Get model from config or environment
            model = ai_config.get("api_model", os.getenv("CLAUDE_MODEL", "claude-3-opus-20240229"))

            # Read image file and encode as base64
            with open(compressed_image_path, "rb") as image_file:
                image_data = image_file.read()
                base64_image = base64.b64encode(image_data).decode("utf-8")

            # Get prompt from config
            prompt = ai_config.get("image_prompt_template")
            if not prompt:
                logger.warning("No image prompt template found in config, using default")
                prompt = "Describe this image briefly."

            # Call Claude API with image
            response = self.client.messages.create(
                model=model,
                max_tokens=60,
                temperature=self.temperature,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": content_type,
                                    "data": base64_image,
                                },
                            },
                            {"type": "text", "text": prompt},
                        ],
                    }
                ],
            )

            # Extract response text
            response_text = response.content[0].text
            logger.info(f"Received image description from Claude API: {response_text}")

            return response_text, None

        except Exception as e:
            logger.error(f"Error sending image to Claude API: {e}")
            return None, None
