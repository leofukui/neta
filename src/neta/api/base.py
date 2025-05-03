from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from ..utils.image_processing import compress_image


class APIClient(ABC):
    """
    Base abstract class for API clients.
    Each AI service API implementation should inherit from this.
    """

    @abstractmethod
    def __init__(self, api_key: str, **kwargs):
        """
        Initialize API client with API key and additional parameters.

        Args:
            api_key: API key for authentication
            **kwargs: Additional configuration parameters
        """
        pass

    @abstractmethod
    def send_text_message(self, message: str, ai_config: Dict[str, Any]) -> Optional[str]:
        """
        Send text message to AI service API.

        Args:
            message: Message text to send
            ai_config: AI configuration dictionary with platform settings

        Returns:
            AI response text or None if failed
        """
        pass

    @abstractmethod
    def send_image(self, image_path: str, ai_config: Dict[str, Any]) -> Optional[str]:
        """
        Send image to AI service API.

        Args:
            image_path: Path to image file
            ai_config: AI configuration dictionary with platform settings

        Returns:
            AI response text or None if failed
        """
        pass

    def _compress_image_for_api(self, image_path: str, max_size_kb: int = 500) -> str:
        """
        Compress an image before sending to API to reduce bandwidth and costs.

        Args:
            image_path: Path to the original image file
            max_size_kb: Maximum desired file size in kilobytes

        Returns:
            Path to the compressed image file (or original if compression fails)
        """
        return compress_image(image_path, max_size_kb)
