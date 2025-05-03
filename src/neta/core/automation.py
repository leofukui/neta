import os
import time

from ..core.config import Config
from ..core.integration import IntegrationManager
from ..ui.ai_platforms import AIPlatformUI
from ..ui.browser import BrowserManager
from ..ui.whatsapp import WhatsAppUI
from ..utils.cache import MessageCache
from ..utils.files import ImageManager
from ..utils.logging import setup_logger

logger = setup_logger()


class NetaAutomation:
    """
    Main automation class for Neta.
    """

    def __init__(self, config_path=None):
        """
        Initialize Neta automation.

        Args:
            config_path: Path to configuration file (default: from environment or config.json)
        """
        logger.info("Initializing Neta automation")

        # Load configuration
        self.config = Config(config_path)
        logger.info("Loaded configuration")

        # Set up cache system
        cache_file = os.getenv("CACHE_FILE_PATH", ".cache.json")
        self.message_cache = MessageCache(cache_file)
        logger.info(f"Initialized message cache: {cache_file}")

        # Set up image manager
        self.image_manager = ImageManager()
        logger.info(f"Initialized image manager: {self.image_manager.image_dir}")

        # Check if we need browser for AI interactions based on config
        self.use_browser_for_ai = self._check_if_browser_needed_for_ai()

        # Initialize browser manager
        self.browser_manager = BrowserManager(self.image_manager.image_dir)

        # UI components will be initialized when browser is ready
        self.whatsapp_ui = None
        self.ai_platform_ui = None
        self.integration_manager = None

    def _check_if_browser_needed_for_ai(self):
        """
        Check if browser is needed for any AI platform based on configuration.

        Returns:
            Boolean indicating if browser is needed for any AI platform
        """
        # Get all AI mappings from config
        ai_mappings = self.config.get_ai_mappings()

        # For each mapping, check if it requires browser
        for group_name, ai_config in ai_mappings.items():
            # Get platform name
            platform_name = ai_config.get("api_platform", "").lower()
            if not platform_name:
                # If api_platform not specified, browser is needed
                logger.info(f"Browser needed because {group_name} has no api_platform defined")
                return True

            # Check if API is enabled for this platform
            platform_upper = platform_name.upper()
            use_api = os.getenv(f"USE_{platform_upper}_API", "false").lower() == "true"

            # If any platform is not using API, we need browser
            if not use_api:
                logger.info(f"Browser needed because {platform_name} is not using API")
                return True

        logger.info("All AI platforms are using APIs, no browser needed for AI")
        return False

    def setup(self):
        """Set up browser and UI components."""
        try:
            # Set up browser with WhatsApp and AI platform tabs if needed
            logger.info("Setting up browser")

            # If using browser for AI, include AI tabs in setup
            if self.use_browser_for_ai:
                self.browser_manager.setup_browser(
                    self.config.get_whatsapp_url(),
                    self.config.get_ai_mappings(),
                    self.config.login_wait_delay,
                )
            else:
                # Only set up WhatsApp tab
                self.browser_manager.setup_browser(
                    self.config.get_whatsapp_url(),
                    {},  # No AI mappings needed
                    self.config.login_wait_delay,
                )

            # Initialize WhatsApp UI
            self.whatsapp_ui = WhatsAppUI(self.browser_manager.driver, self.image_manager)

            # Initialize AI platform UI if needed
            if self.use_browser_for_ai:
                self.ai_platform_ui = AIPlatformUI(self.browser_manager.driver)

            # Initialize integration manager
            self.integration_manager = IntegrationManager(
                self.config,
                self.browser_manager.driver,
                self.ai_platform_ui if self.use_browser_for_ai else None,
            )

            logger.info("Setup completed successfully")
            return True
        except Exception as e:
            logger.error(f"Setup failed: {e}")
            return False

    def process_message(self, group_name, message, message_type):
        """
        Process a message by sending it to appropriate AI platform and returning response.

        Args:
            group_name: Name of the WhatsApp group
            message: Message content (text or image path)
            message_type: Type of message ('text' or 'image')

        Returns:
            Tuple of (text_response, image_path) or (None, None) if failed
        """
        try:
            # Get AI configuration for this group
            ai_config = self.config.get_ai_config(group_name)
            if not ai_config:
                logger.warning(f"No AI mapping found for group: {group_name}")
                return None, None

            # Get platform name from config
            platform_name = ai_config.get("api_platform", "").lower()

            # Check if using API for this platform
            use_api = os.getenv(f"USE_{platform_name.upper()}_API", "false").lower() == "true"

            if use_api and platform_name:
                # Use integration manager to handle API request
                logger.info(f"Using API integration for {group_name} ({platform_name})")
                return self.integration_manager.process_message(group_name, message, message_type)
            else:
                # Use browser automation (original method)
                logger.info(f"Using browser automation for {group_name}")

                # Switch to AI platform tab
                tab_name = ai_config["tab_name"]
                if not self.browser_manager.switch_to_tab(tab_name):
                    logger.error(f"Failed to switch to tab: {tab_name}")
                    return None, None

                # Send message to AI platform
                if message_type == "text":
                    logger.info(f"Processing text message for {group_name}")
                    response = self.ai_platform_ui.send_text_message(ai_config, message)
                    # Browser UI doesn't support image generation yet
                    return response, None
                else:  # message_type == "image"
                    logger.info(f"Processing image message for {group_name}")
                    response = self.ai_platform_ui.send_image(ai_config, message)
                    return response, None

                # Refresh AI page to prepare for next interaction
                if response:
                    self.ai_platform_ui.refresh_page()

        except Exception as e:
            logger.error(f"Error processing message: {e}")
            return None, None

    def send_response(self, response_data, group_name):
        """
        Send AI response back to WhatsApp.

        Args:
            response_data: Response from AI (can be text or tuple of (text, image_path))
            group_name: WhatsApp group to send to

        Returns:
            Boolean indicating success
        """
        try:
            # Switch to WhatsApp tab
            if not self.browser_manager.switch_to_tab("WhatsApp"):
                logger.error("Failed to switch to WhatsApp tab")
                return False

            # Select chat
            if not self.whatsapp_ui.select_chat(group_name):
                logger.error(f"Failed to select chat: {group_name}")
                return False

            # Handle different response formats
            text_response = None
            image_path = None

            if isinstance(response_data, tuple) and len(response_data) == 2:
                # Tuple format: (text_response, image_path)
                text_response, image_path = response_data
            elif isinstance(response_data, str):
                # String format: just text response
                text_response = response_data

            # Send message and cache sent response
            success = self.whatsapp_ui.send_message(text_response, image_path)
            if success:
                # Cache the text response
                if text_response:
                    self.message_cache.cache_content(text_response, group_name)
                # Cache the image path if there is one
                if image_path:
                    self.message_cache.cache_content(f"image:{image_path}", group_name)
                logger.info("Sent and cached response")

            return success
        except Exception as e:
            logger.error(f"Error sending response: {e}")
            return False

    def cleanup_temp_files(self):
        """Clean up temporary image files."""
        self.image_manager.cleanup_old_files()

    def run(self):
        """
        Run the main automation loop.

        This method continuously monitors WhatsApp chats for new messages,
        processes them with the appropriate AI platform, and sends responses.
        """
        try:
            if not self.setup():
                logger.error("Setup failed, exiting")
                return

            logger.info("Starting message monitoring loop")
            cleanup_counter = 0

            while True:
                try:
                    # Switch to WhatsApp tab
                    if not self.browser_manager.switch_to_tab("WhatsApp"):
                        logger.error("Failed to switch to WhatsApp tab")
                        time.sleep(self.config.loop_interval_delay)
                        continue

                    # Check for new messages in configured groups
                    group_names = list(self.config.get_ai_mappings().keys())
                    group_name, message, message_type = self.whatsapp_ui.get_new_messages(
                        group_names, self.message_cache
                    )

                    # Process new message if found
                    if group_name and (message or message_type == "image"):
                        logger.info(f"New {message_type} message in {group_name}")

                        # Process with appropriate AI
                        response = self.process_message(group_name, message, message_type)

                        # Send response back to WhatsApp
                        if response and (
                            response[0] or response[1]
                        ):  # If text or image is returned
                            self.send_response(response, group_name)

                    # Periodically cleanup temp files
                    cleanup_counter += 1
                    if cleanup_counter >= 120:  # Every ~10 minutes (with 5s delay)
                        self.cleanup_temp_files()
                        cleanup_counter = 0

                    # Delay before next check
                    time.sleep(self.config.loop_interval_delay)

                except KeyboardInterrupt:
                    raise
                except Exception as e:
                    logger.error(f"Error in main loop: {e}")
                    time.sleep(self.config.loop_interval_delay)

        except KeyboardInterrupt:
            logger.info("Shutting down...")
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
        finally:
            self.cleanup()

    def cleanup(self):
        """Close browser and perform cleanup."""
        if self.browser_manager:
            self.browser_manager.close()
        logger.info("Cleanup completed")
