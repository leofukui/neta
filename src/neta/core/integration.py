import logging
from typing import Optional

from neta.core.config import Config
from neta.core.router import MessageRouter

logger = logging.getLogger(__name__)


class IntegrationManager:
    """
    Manages integration with various AI platforms through API or UI automation.
    """

    def __init__(self, config: Config, driver=None, ui_handler=None):
        """
        Initialize integration manager.

        Args:
            config: Application configuration
            driver: Selenium WebDriver instance
            ui_handler: AIPlatformUI instance
        """
        self.config = config
        self.router = MessageRouter(driver, ui_handler)
        self.logger = logging.getLogger(__name__)

    def process_message(self, group_name: str, message: str, message_type: str) -> Optional[str]:
        """
        Process a message by sending it to appropriate AI platform.

        Args:
            group_name: Name of the WhatsApp group
            message: Message content (text or image path)
            message_type: Type of message ('text' or 'image')

        Returns:
            AI response or None if failed
        """
        try:
            # Get AI configuration for this group
            ai_config = self.config.get_ai_config(group_name)
            if not ai_config:
                self.logger.warning(f"No AI mapping found for group: {group_name}")
                return None

            # Process message using router
            return self.router.process_message(ai_config, message, message_type)

        except Exception as e:
            self.logger.error(f"Error processing message: {e}")
            return None
