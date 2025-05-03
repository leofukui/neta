import logging
import os
from typing import Optional

from .base import APIClient
from .claude import ClaudeClient
from .gemini import GeminiClient
from .grok import GrokClient
from .openai import OpenAIClient
from .perplexity import PerplexityClient

logger = logging.getLogger(__name__)


class APIClientFactory:
    """
    Factory for creating API clients based on configuration.
    """

    @staticmethod
    def create_client(platform: str, **kwargs) -> Optional[APIClient]:
        """
        Create and return an API client for the specified platform.

        Args:
            platform: Platform name (e.g., "openai", "gemini", "perplexity")
            **kwargs: Additional configuration parameters

        Returns:
            APIClient instance or None if not available
        """
        try:
            platform = platform.lower()

            # Get common parameters from environment
            max_tokens = int(os.getenv(f"{platform.upper()}_MAX_TOKENS", "100"))
            temperature = float(os.getenv(f"{platform.upper()}_TEMPERATURE", "0.7"))
            max_image_size_kb = int(os.getenv("MAX_IMAGE_SIZE_KB", "500"))

            # Common settings for all clients
            client_settings = {
                "max_tokens": max_tokens,
                "temperature": temperature,
                "max_image_size_kb": max_image_size_kb,
                **kwargs,
            }

            # Create client based on platform
            if platform == "openai":
                return OpenAIClient(**client_settings)
            elif platform == "claude":
                return ClaudeClient(**client_settings)
            elif platform == "gemini":
                return GeminiClient(**client_settings)
            elif platform == "perplexity":
                return PerplexityClient(**client_settings)
            elif platform == "grok":
                return GrokClient(**client_settings)
            else:
                logger.error(f"Unsupported API platform: {platform}")
                return None

        except Exception as e:
            logger.error(f"Error creating API client for {platform}: {e}")
            return None
