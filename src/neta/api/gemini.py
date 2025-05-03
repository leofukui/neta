# File: neta/api/gemini.py
import logging
import os
from typing import Any, Dict, Optional

# Google AI Python SDK
import google.generativeai as genai

from .base import APIClient

logger = logging.getLogger(__name__)


class GeminiClient(APIClient):
    """
    Gemini API client implementation.
    """

    def __init__(self, api_key: str, **kwargs):
        """
        Initialize Gemini API client.

        Args:
            api_key: Gemini API key
            **kwargs: Additional configuration parameters
        """
        self.api_key = api_key
        self.max_tokens = kwargs.get("max_tokens", 100)
        self.temperature = kwargs.get("temperature", 0.7)
        self.max_image_size_kb = kwargs.get("max_image_size_kb", 500)

        # Initialize Google GenAI client
        genai.configure(api_key=self.api_key)
        logger.info("Initialized Gemini API client")

    def send_text_message(self, message: str, ai_config: Dict[str, Any]) -> Optional[str]:
        """
        Send text message to Gemini API.

        Args:
            message: Message text to send
            ai_config: AI configuration dictionary

        Returns:
            AI response text or None if failed
        """
        try:
            # Get model from config or environment
            model_name = ai_config.get("api_model", os.getenv("GEMINI_MODEL", "gemini-pro"))

            # Get prompt template from config
            prompt_template = ai_config.get("text_prompt_template")
            if not prompt_template:
                logger.warning("No text prompt template found in config, using raw message")
                prompt = message
            else:
                # Format prompt with message
                prompt = prompt_template.format(message=message)

            # Create generation config
            generation_config = {
                "max_output_tokens": self.max_tokens,
                "temperature": self.temperature,
            }

            # Get Gemini model
            model = genai.GenerativeModel(model_name, generation_config=generation_config)

            # Call Gemini API
            response = model.generate_content(prompt)

            # Extract response text
            response_text = response.text.strip()
            logger.info(f"Received response from Gemini API: {response_text[:50]}...")

            return response_text

        except Exception as e:
            logger.error(f"Error sending text to Gemini API: {e}")
            return None

    def send_image(self, image_path: str, ai_config: Dict[str, Any]) -> Optional[str]:
        """
        Send image to Gemini API using vision capabilities.

        Args:
            image_path: Path to image file
            ai_config: AI configuration dictionary

        Returns:
            AI response text or None if failed
        """
        try:
            # Compress image before sending
            compressed_image_path = self._compress_image_for_api(image_path, self.max_image_size_kb)

            # After compression, content type is always JPEG
            content_type = "image/jpeg"

            # Get vision model from config or environment
            model_name = ai_config.get(
                "api_vision_model", os.getenv("GEMINI_VISION_MODEL", "gemini-pro-vision")
            )

            # Read image file
            with open(compressed_image_path, "rb") as image_file:
                image_data = image_file.read()

            # Get prompt from config
            prompt = ai_config.get("image_prompt_template")
            if not prompt:
                logger.warning("No image prompt template found in config, using default")
                prompt = "Describe this image briefly."

            # Create generation config
            generation_config = {"max_output_tokens": 60, "temperature": self.temperature}

            # Get Gemini model
            model = genai.GenerativeModel(model_name, generation_config=generation_config)

            # Call Gemini API with image
            # Note: Gemini takes the mime_type directly
            response = model.generate_content(
                [prompt, {"mime_type": content_type, "data": image_data}]
            )

            # Extract response text
            response_text = response.text.strip()
            logger.info(f"Received image description from Gemini API: {response_text}")

            return response_text

        except Exception as e:
            logger.error(f"Error sending image to Gemini API: {e}")
            return None
