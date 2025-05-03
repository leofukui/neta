import logging
import os
import tempfile
from io import BytesIO
from typing import Any, Dict, Optional, Tuple

# Import google.genai module (latest name in documentation)
import google.genai as genai
from PIL import Image

from .base import APIClient

logger = logging.getLogger(__name__)


class GeminiClient(APIClient):
    """
    Gemini API client implementation that follows the latest google-genai SDK.
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

        # Initialize the client with the API key
        self.client = genai.Client(api_key=self.api_key)

        # Log the version of google.genai being used
        logger.info(
            f"Initialized Gemini API client with google.genai version: {getattr(genai, '__version__', 'unknown')}"
        )

    def send_text_message(
        self, message: str, ai_config: Dict[str, Any]
    ) -> Tuple[Optional[str], Optional[str]]:
        """Send text message to Gemini API."""
        try:
            # Check if this is an image generation request
            is_image_generation = self._is_image_generation_request(message, ai_config)

            if is_image_generation:
                logger.info("Image generation request detected")
                # Process as image generation request
                return self._generate_image(message, ai_config)

            # Standard text processing
            # Get model from config or environment
            model_name = ai_config.get(
                "api_model", os.getenv("GEMINI_MODEL", "gemini-2.0-flash-001")
            )

            # Get prompt template from config
            prompt_template = ai_config.get("text_prompt_template")
            if not prompt_template:
                logger.warning("No text prompt template found in config, using raw message")
                prompt = message
            else:
                # Format prompt with message
                prompt = prompt_template.format(message=message)

            # Create generation config using the types module
            generation_config = genai.types.GenerateContentConfig(
                max_output_tokens=self.max_tokens,
                temperature=self.temperature,
            )

            # Generate content using the updated API
            response = self.client.models.generate_content(
                model=model_name, contents=prompt, config=generation_config
            )

            # Extract response text
            response_text = response.text.strip()
            logger.info(f"Received response from Gemini API: {response_text[:50]}...")

            return response_text, None

        except Exception as e:
            logger.error(f"Error sending text to Gemini API: {e}")
            return None, None

    def send_image(
        self, image_path: str, ai_config: Dict[str, Any]
    ) -> Tuple[Optional[str], Optional[str]]:
        """Send image to Gemini API using vision capabilities."""
        try:
            # Compress image before sending
            compressed_image_path = self._compress_image_for_api(image_path, self.max_image_size_kb)

            # After compression, content type is always JPEG
            content_type = "image/jpeg"

            # Get vision model from config or environment
            model_name = ai_config.get(
                "api_vision_model", os.getenv("GEMINI_VISION_MODEL", "gemini-2.0-flash-001")
            )

            # Read image file as bytes
            with open(compressed_image_path, "rb") as image_file:
                image_data = image_file.read()

            # Get prompt from config
            prompt = ai_config.get("image_prompt_template")
            if not prompt:
                logger.warning("No image prompt template found in config, using default")
                prompt = "Describe this image briefly."

            # Create generation config
            generation_config = genai.types.GenerateContentConfig(
                max_output_tokens=60,
                temperature=self.temperature,
            )

            # Create content with image part
            contents = [
                prompt,
                genai.types.Part.from_bytes(data=image_data, mime_type=content_type),
            ]

            # Generate content
            response = self.client.models.generate_content(
                model=model_name, contents=contents, config=generation_config
            )

            # Extract response text
            response_text = response.text.strip()
            logger.info(f"Received image description from Gemini API: {response_text}")

            return response_text, None

        except Exception as e:
            logger.error(f"Error sending image to Gemini API: {e}")
            return None, None

    def _is_image_generation_request(self, message: str, ai_config: Dict[str, Any]) -> bool:
        """Determine if a message is requesting image generation."""
        # Check if image generation is enabled in config
        if not ai_config.get("enable_image_generation", False):
            return False

        # Simplistic check - if message starts with "draw", "generate image", etc.
        image_request_prefixes = [
            "draw",
            "generate image",
            "create image",
            "make image",
            "imagen",
            "gerar imagem",
            "criar imagem",
            "desenhe",
        ]

        lower_message = message.lower().strip()
        for prefix in image_request_prefixes:
            if lower_message.startswith(prefix):
                return True

        return False

    def _generate_image(
        self, prompt: str, ai_config: Dict[str, Any]
    ) -> Tuple[Optional[str], Optional[str]]:
        """Generate an image using Gemini API."""
        try:
            # Clean up the image generation prompt by removing common prefixes
            image_prompt = self._clean_image_prompt(prompt)

            # Get the image generation model from config or use default
            model_name = ai_config.get(
                "api_image_model", os.getenv("GEMINI_IMAGE_MODEL", "imagen-3.0-generate-002")
            )

            logger.info(f"Generating image with model: {model_name} and prompt: {image_prompt}")

            # Updated parameters based on the new documentation
            response = self.client.models.generate_images(
                model=model_name,
                prompt=image_prompt,
                config=genai.types.GenerateImagesConfig(
                    number_of_images=1,
                    safety_filter_level="block_low_and_above",
                    person_generation="allow_adult",
                    aspect_ratio="3:4",
                    output_mime_type="image/jpeg",
                ),
            )

            # Extract the generated image
            generated_image = response.generated_images[0].image

            # Convert to PIL image and save to temp file
            image_bytes = generated_image.image_bytes
            image = Image.open(BytesIO(image_bytes))

            # Save the image to a temporary file
            temp_file = tempfile.NamedTemporaryFile(
                suffix=".png", delete=False, dir=os.getenv("IMAGE_TEMP_DIR", "/tmp")
            )
            image.save(temp_file, format="PNG")
            temp_file.close()

            return "Image generated successfully.", temp_file.name

        except Exception as e:
            logger.error(f"Error generating image with Gemini: {e}")
            return f"Image generation error: {e.__class__.__name__}: {e}", None

    def _clean_image_prompt(self, prompt: str) -> str:
        """
        Clean up the image generation prompt by removing common prefixes.

        Args:
            prompt: Original prompt from user

        Returns:
            Cleaned prompt for image generation
        """
        lower_prompt = prompt.lower()

        # List of prefixes to remove
        prefixes = [
            "draw ",
            "generate image of ",
            "create image of ",
            "make image of ",
            "draw me ",
            "generate an image of ",
            "create an image of ",
            "make an image of ",
            "imagen de ",
            "gerar imagem de ",
            "criar imagem de ",
            "desenhe ",
            "desenhe-me ",
        ]

        # Try each prefix and remove if found at start
        for prefix in prefixes:
            if lower_prompt.startswith(prefix):
                return prompt[len(prefix) :].strip()

        # If no prefix matched, return original
        return prompt.strip()
