import logging
import os
import tempfile
from io import BytesIO
from typing import Any, Dict, Optional, Tuple

import google.genai as genai
from PIL import Image

from .base import APIClient

logger = logging.getLogger(__name__)


class GeminiClient(APIClient):
    """
    Gemini API client implementation using the latest google-genai SDK.
    With persistent system prompt support.
    """

    def __init__(self, api_key: str, **kwargs):
        self.api_key = api_key
        self.max_tokens = kwargs.get("max_tokens", 700)
        self.temperature = kwargs.get("temperature", 0.7)
        self.max_history_messages = kwargs.get("max_history_messages", 10)

        self.conversation_history: list[dict[str, str]] = []

        self.client = genai.Client(api_key=self.api_key)
        logger.info(
            f"Initialized Gemini API client with google.genai version: {getattr(genai, '__version__', 'unknown')}"
        )

    def send_text_message(self, message: str, ai_config: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
        """Send text message to Gemini API."""
        try:
            if self._is_image_generation_request(message, ai_config):
                logger.info("Image generation request detected")
                return self._generate_image(message, ai_config)

            model_name = ai_config.get("api_model", os.getenv("GEMINI_MODEL", "gemini-2.0-flash-001"))
            system_prompt = ai_config.get("system_prompt", "")

            # Add user message to conversation history
            self.conversation_history.append({"role": "user", "content": message})

            # Create content list from conversation history
            contents = []

            # Add system prompt if it exists
            if system_prompt:
                contents.append(genai.types.Content(role="system", parts=[{"text": system_prompt}]))

            # Add conversation history
            for msg in self.conversation_history:
                contents.append(genai.types.Content(role=msg["role"], parts=[{"text": msg["content"]}]))

            generation_config = genai.types.GenerateContentConfig(
                max_output_tokens=self.max_tokens,
                temperature=self.temperature,
            )

            response = self.client.models.generate_content(
                model=model_name,
                contents=contents,
                config=generation_config,
            )

            response_text = response.text.strip()
            self.conversation_history.append({"role": "model", "content": response_text})

            # Trim conversation history if needed
            if len(self.conversation_history) > self.max_history_messages:
                self.conversation_history = self.conversation_history[-self.max_history_messages :]

            logger.info(f"Received response from Gemini API: {response_text[:50]}...")
            return response_text, None

        except Exception as e:
            logger.error(f"Error sending text to Gemini API: {e}")
            return None, None

    def send_image(
        self, image_path: str, ai_config: Dict[str, Any], message: Optional[str] = None
    ) -> Tuple[Optional[str], Optional[str]]:
        """Send image to Gemini API using vision capabilities."""
        try:
            model_name = ai_config.get("api_vision_model", os.getenv("GEMINI_VISION_MODEL", "gemini-2.0-flash-001"))
            system_prompt = ai_config.get("system_prompt", "")

            with open(image_path, "rb") as image_file:
                image_data = image_file.read()

            # Use passed `message` as prompt, fallback to template or default
            prompt_template = ai_config.get("image_prompt_template", "Describe this image briefly.")
            prompt = message or prompt_template

            # Add user message to conversation history (text only)
            self.conversation_history.append({"role": "user", "content": prompt})

            generation_config = genai.types.GenerateContentConfig(
                max_output_tokens=60,
                temperature=self.temperature,
            )

            # Create content list
            contents = []

            # Add system prompt if it exists
            if system_prompt:
                contents.append(genai.types.Content(role="system", parts=[{"text": system_prompt}]))

            # Add user message with image
            contents.append(
                genai.types.Content(
                    role="user",
                    parts=[
                        genai.types.Part(text=prompt),
                        genai.types.Part(
                            inline_data=genai.types.Blob(
                                mime_type="image/jpeg",
                                data=image_data,
                            )
                        ),
                    ],
                )
            )

            response = self.client.models.generate_content(
                model=model_name,
                contents=contents,
                config=generation_config,
            )

            response_text = response.text.strip()
            self.conversation_history.append({"role": "model", "content": response_text})

            # Trim conversation history if needed
            if len(self.conversation_history) > self.max_history_messages:
                self.conversation_history = self.conversation_history[-self.max_history_messages :]

            logger.info(f"Received image description from Gemini API: {response_text}")
            return response_text, None

        except Exception as e:
            logger.error(f"Error sending image to Gemini API: {e}")
            return None, None

    def _generate_image(self, prompt: str, ai_config: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
        """Generate an image using Gemini API."""
        try:
            model_name = ai_config.get(
                "api_image_model",
                os.getenv("GEMINI_IMAGE_MODEL", "gemini-2.0-flash-exp-image-generation"),
            )

            logger.info(f"Generating image with model: {model_name} and prompt: {prompt}")

            response = self.client.models.generate_images(
                model=model_name,
                prompt=prompt,
                config=genai.types.GenerateImagesConfig(
                    number_of_images=1,
                    safety_filter_level="block_low_and_above",
                    person_generation="allow_adult",
                    aspect_ratio="9:16",
                    output_mime_type="image/jpeg",
                ),
            )

            generated_image = response.generated_images[0].image
            image_bytes = generated_image.image_bytes
            image = Image.open(BytesIO(image_bytes))

            temp_file = tempfile.NamedTemporaryFile(
                suffix=".png", delete=False, dir=os.getenv("IMAGE_TEMP_DIR", "/tmp")
            )
            image.save(temp_file, format="PNG")
            temp_file.close()

            return None, temp_file.name

        except Exception as e:
            logger.error(f"Error generating image with Gemini: {e}")
            return f"Image generation error: {e.__class__.__name__}: {e}", None

    def _is_image_generation_request(self, message: str, ai_config: Dict[str, Any]) -> bool:
        return ai_config.get("enable_image_generation", False)
