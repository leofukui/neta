import base64
import logging
import os
from typing import Any, Dict, Optional

import openai
from openai import OpenAI

from .base import APIClient

logger = logging.getLogger(__name__)


class OpenAIClient(APIClient):
    """
    OpenAI API client implementation.
    """

    def __init__(self, api_key: str, **kwargs):
        """
        Initialize OpenAI API client.

        Args:
            api_key: OpenAI API key
            **kwargs: Additional configuration parameters
        """
        self.api_key = api_key
        self.max_tokens = kwargs.get("max_tokens", 100)
        self.temperature = kwargs.get("temperature", 0.7)
        self.max_image_size_kb = kwargs.get("max_image_size_kb", 500)

        # Initialize OpenAI client
        self.client = OpenAI(api_key=self.api_key)
        logger.info(f"Initialized OpenAI API client")

    def send_text_message(
        self, message: str, ai_config: Dict[str, Any]
    ) -> tuple[Optional[str], Optional[str]]:
        """
        Send text message to OpenAI API.

        Args:
            message: Message text to send
            ai_config: AI configuration dictionary

        Returns:
            AI response text or None if failed
        """
        try:
            # Get model from config or environment
            model = ai_config.get("api_model", os.getenv("OPENAI_MODEL", "gpt-4"))

            # Get prompt template from config
            prompt_template = ai_config.get("text_prompt_template")
            if not prompt_template:
                logger.warning("No text prompt template found in config, using raw message")
                prompt = message
            else:
                # Format prompt with message
                prompt = prompt_template.format(message=message)

            # Call OpenAI API
            response = self.client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=self.max_tokens,
                temperature=self.temperature,
            )

            # Extract response text
            response_text = response.choices[0].message.content.strip()
            logger.info(f"Received response from OpenAI API: {response_text[:50]}...")

            return response_text, None

        except Exception as e:
            logger.error(f"Error sending text to OpenAI API: {e}")
            return None, None

    def send_image(
        self, image_path: str, ai_config: Dict[str, Any]
    ) -> tuple[Optional[str], Optional[str]]:
        """
        Send image to OpenAI API using vision capabilities.

        Args:
            image_path: Path to image file
            ai_config: AI configuration dictionary

        Returns:
            AI response text or None if failed
        """
        try:
            # Compress image before sending
            compressed_image_path = self._compress_image_for_api(image_path, self.max_image_size_kb)

            # Get vision model from config or environment
            model = ai_config.get(
                "api_vision_model", os.getenv("OPENAI_VISION_MODEL", "gpt-4-vision-preview")
            )

            # Get content type
            content_type = "image/jpeg"  # After compression, we know it's a JPEG

            # Read image file and encode as base64
            with open(compressed_image_path, "rb") as image_file:
                base64_image = base64.b64encode(image_file.read()).decode("utf-8")

            # Get prompt from config
            prompt = ai_config.get("image_prompt_template")
            if not prompt:
                logger.warning("No image prompt template found in config, using default")
                prompt = "Describe this image briefly."

            # Call OpenAI API with image
            response = self.client.chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:{content_type};base64,{base64_image}",
                                    "detail": "low",  # Use low detail to reduce tokens
                                },
                            },
                        ],
                    }
                ],
                max_tokens=60,
            )

            # Extract response text
            response_text = response.choices[0].message.content.strip()
            logger.info(f"Received image description from OpenAI API: {response_text}")

            return response_text, None

        except Exception as e:
            logger.error(f"Error sending image to OpenAI API: {e}")
            return None, None
