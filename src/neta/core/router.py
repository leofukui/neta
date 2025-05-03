import logging
import os
from typing import Any, Dict, Optional, Tuple

from neta.api.client_factory import APIClientFactory

logger = logging.getLogger(__name__)


class MessageRouter:
    """
    Routes messages between UI automation and API clients based on configuration.
    """

    def __init__(self, driver=None, ui_handler=None):
        """
        Initialize the message router.

        Args:
            driver: Selenium WebDriver instance for UI automation
            ui_handler: AIPlatformUI instance
        """
        self.driver = driver
        self.ui_handler = ui_handler
        self.api_clients = {}  # Cache for API clients

    def _get_platform_config(self, platform_name: str) -> Dict[str, Any]:
        """
        Get configuration for a platform based on environment variables.

        Args:
            platform_name: Platform name (e.g., "openai", "gemini")

        Returns:
            Configuration dictionary
        """
        platform_upper = platform_name.upper()
        return {
            "use_api": os.getenv(f"USE_{platform_upper}_API", "false").lower() == "true",
            "api_key": os.getenv(f"{platform_upper}_API_KEY", ""),
            "max_tokens": int(os.getenv(f"{platform_upper}_MAX_TOKENS", "100")),
            "temperature": float(os.getenv(f"{platform_upper}_TEMPERATURE", "0.7")),
            "max_image_size_kb": int(os.getenv("MAX_IMAGE_SIZE_KB", "500")),
        }

    def _get_api_client(self, platform_name: str) -> Optional[Any]:
        """
        Get or create an API client for the specified platform.

        Args:
            platform_name: Platform name (e.g., "openai", "gemini")

        Returns:
            API client instance or None if not available
        """
        # Return cached client if available
        if platform_name in self.api_clients:
            return self.api_clients[platform_name]

        # Create new client
        config = self._get_platform_config(platform_name)
        client = APIClientFactory.create_client(platform_name, **config)

        # Cache client if created successfully
        if client:
            self.api_clients[platform_name] = client

        return client

    def process_message(
        self, ai_config: Dict[str, Any], message: str, message_type: str
    ) -> Optional[str]:
        """
        Route a message to either UI automation or API client based on configuration.

        Args:
            ai_config: AI configuration from configuration file
            message: Message content (text or image path)
            message_type: Type of message ('text' or 'image')

        Returns:
            AI response or None if failed
        """
        try:
            # Get platform name directly from config
            platform_name = ai_config.get("api_platform", "").lower()

            logger.info(f"Processing {message_type} message for platform: {platform_name}")

            # Get platform configuration
            platform_config = self._get_platform_config(platform_name)

            # Determine whether to use API or UI
            use_api = platform_config.get("use_api", False)

            if use_api:
                # Use API client
                logger.info(f"Using API for {platform_name}")
                client = self._get_api_client(platform_name)

                if not client:
                    logger.error(f"API client not available for {platform_name}")
                    return None

                # Send message based on type
                if message_type == "text":
                    return client.send_text_message(message, ai_config)
                else:  # message_type == "image"
                    return client.send_image(message, ai_config)
            else:
                # Use UI automation
                if not self.ui_handler:
                    logger.error("UI handler not available for browser automation")
                    return None

                logger.info(f"Using UI automation for {platform_name}")

                # Send message based on type
                if message_type == "text":
                    return self.ui_handler.send_text_message(ai_config, message)
                else:  # message_type == "image"
                    return self.ui_handler.send_image(ai_config, message)

        except Exception as e:
            logger.error(f"Error in message router: {e}")
            return None
