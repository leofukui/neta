from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


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
    def send_text_message(
        self, message: str, ai_config: Dict[str, Any]
    ) -> tuple[Optional[str], Optional[str]]:
        """
        Send text message to AI service API.

        Args:
            message: Message text to send
            ai_config: AI configuration dictionary with platform settings

        Returns:
            Tuple of (AI response text, image_path) where image_path is None if no image was generated
        """
        pass

    @abstractmethod
    def send_image(
        self, image_path: str, ai_config: Dict[str, Any]
    ) -> tuple[Optional[str], Optional[str]]:
        """
        Send image to AI service API.

        Args:
            image_path: Path to image file
            ai_config: AI configuration dictionary with platform settings

        Returns:
            Tuple of (AI response text, image_path) where image_path is None if no image was generated
        """
        pass
