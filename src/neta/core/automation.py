import asyncio
import os
from typing import Dict

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
    Main automation class for Neta with asyncio support.
    """

    def __init__(self, config_path=None):
        """
        Initialize Neta automation.

        Args:
            config_path: Path to configuration file (default: from environment or config.json)
        """
        logger.info("Initializing Neta automation with asyncio support")

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

        # Locks for group chats to prevent race conditions
        self.group_locks: Dict[str, asyncio.Lock] = {}

        # Track which messages are currently being processed
        self.processing_messages: Dict[str, set] = {}

        # Event loop for asyncio
        self.loop = None

        # Active tasks
        self.tasks = []

        # Shutdown flag
        self.shutdown_event = asyncio.Event()

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

    async def setup(self):
        """Set up browser and UI components asynchronously."""
        try:
            # Set up browser with WhatsApp and AI platform tabs if needed
            logger.info("Setting up browser")

            # Create locks for each group chat
            for group_name in self.config.get_ai_mappings().keys():
                self.group_locks[group_name] = asyncio.Lock()
                logger.debug(f"Created lock for group: {group_name}")

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

    async def process_message(self, group_name, message, message_type):
        """
        Process a message by sending it to appropriate AI platform and returning response.
        This method now includes locking to prevent race conditions.

        Args:
            group_name: Name of the WhatsApp group
            message: Message content (text or image path)
            message_type: Type of message ('text' or 'image')

        Returns:
            Tuple of (text_response, image_path) or (None, None) if failed
        """
        # Acquire lock for this group to prevent race conditions
        async with self.group_locks[group_name]:
            try:
                logger.info(f"Processing {message_type} message for {group_name}")

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

                    # Note: If integration_manager.process_message is blocking,
                    # we should run it in a thread pool executor
                    return await self.loop.run_in_executor(
                        None, lambda: self.integration_manager.process_message(group_name, message, message_type)
                    )
                else:
                    # Use browser automation (original method)
                    logger.info(f"Using browser automation for {group_name}")

                    # Switch to AI platform tab
                    tab_name = ai_config["tab_name"]
                    tab_switch_success = await self.loop.run_in_executor(
                        None, lambda: self.browser_manager.switch_to_tab(tab_name)
                    )

                    if not tab_switch_success:
                        logger.error(f"Failed to switch to tab: {tab_name}")
                        return None, None

                    # Send message to AI platform
                    if message_type == "text":
                        response = await self.loop.run_in_executor(
                            None, lambda: self.ai_platform_ui.send_text_message(ai_config, message)
                        )
                        # Browser UI doesn't support image generation yet
                        return response, None
                    else:  # message_type == "image"
                        response = await self.loop.run_in_executor(
                            None, lambda: self.ai_platform_ui.send_image(ai_config, message)
                        )
                        return response, None

            except Exception as e:
                logger.error(f"Error processing message: {e}")
                return None, None

    async def send_response(self, response_data, group_name):
        """
        Send AI response back to WhatsApp with locking.

        Args:
            response_data: Response from AI (can be text or tuple of (text, image_path))
            group_name: WhatsApp group to send to

        Returns:
            Boolean indicating success
        """
        # Acquire lock for this group to prevent race conditions
        async with self.group_locks[group_name]:
            try:
                # Switch to WhatsApp tab
                tab_switch_success = await self.loop.run_in_executor(
                    None, lambda: self.browser_manager.switch_to_tab("WhatsApp")
                )

                if not tab_switch_success:
                    logger.error("Failed to switch to WhatsApp tab")
                    return False

                # Select chat
                chat_select_success = await self.loop.run_in_executor(
                    None, lambda: self.whatsapp_ui.select_chat(group_name)
                )

                if not chat_select_success:
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

                # Switch back to WhatsApp tab and select chat (in case of any tab changes during processing)
                tab_switch_success = await self.loop.run_in_executor(
                    None, lambda: self.browser_manager.switch_to_tab("WhatsApp")
                )

                if not tab_switch_success:
                    logger.error("Failed to switch to WhatsApp tab")
                    return False

                chat_select_success = await self.loop.run_in_executor(
                    None, lambda: self.whatsapp_ui.select_chat(group_name)
                )

                if not chat_select_success:
                    logger.error(f"Failed to select chat: {group_name}")
                    return False

                # Send message
                success = await self.loop.run_in_executor(
                    None, lambda: self.whatsapp_ui.send_message(text_response, image_path)
                )

                if success:
                    # Cache the text response
                    if text_response:
                        self.message_cache.cache_content(text_response, group_name)
                    # Cache the image path if there is one
                    if image_path:
                        self.message_cache.cache_content(f"image:{image_path}", group_name)
                    logger.info(f"Sent and cached response to {group_name}")

                return success
            except Exception as e:
                logger.error(f"Error sending response: {e}")
                return False

    async def check_messages(self, group_names):
        """
        Check for new messages in WhatsApp groups asynchronously.

        Args:
            group_names: List of WhatsApp group names to check

        Returns:
            Tuple of (group_name, message, message_type) or (None, None, None) if no new messages
        """
        try:
            # Switch to WhatsApp tab
            tab_switch_success = await self.loop.run_in_executor(
                None, lambda: self.browser_manager.switch_to_tab("WhatsApp")
            )

            if not tab_switch_success:
                logger.error("Failed to switch to WhatsApp tab")
                return None, None, None

            # Get list of groups that don't have active locks (not being processed)
            available_groups = []
            for group in group_names:
                if group in self.group_locks and not self.group_locks[group].locked():
                    available_groups.append(group)
                else:
                    logger.debug(f"Skipping check for {group} as it's currently being processed")

            if not available_groups:
                # All groups are being processed, skip this polling cycle
                logger.debug("All groups are currently being processed, skipping check")
                return None, None, None

            # Run get_new_messages in executor since it's a blocking operation
            # Only check groups that aren't currently locked
            result = await self.loop.run_in_executor(
                None, lambda: self.whatsapp_ui.get_new_messages(available_groups, self.message_cache)
            )

            # If we got a result, immediately acquire the lock to prevent double-processing
            if result and result[0]:
                group_name = result[0]
                # Try to acquire the lock without waiting
                if not self.group_locks[group_name].locked():
                    # Mark that we're going to process this message
                    # The actual lock acquisition happens in handle_message
                    logger.info(f"Reserving message from {group_name} for processing")
                else:
                    # Another task just grabbed this message, skip it
                    logger.warning(f"Race condition detected for {group_name}, skipping message")
                    return None, None, None

            return result
        except Exception as e:
            logger.error(f"Error checking messages: {e}")
            return None, None, None

    async def cleanup_temp_files(self):
        """Clean up temporary image files asynchronously."""
        await self.loop.run_in_executor(None, self.image_manager.cleanup_old_files)
        logger.info("Cleaned up temporary files")

    async def handle_message(self, group_name, message, message_type):
        """
        Handle a single message processing workflow.

        Args:
            group_name: Name of the WhatsApp group
            message: Message content
            message_type: Type of message ('text' or 'image')
        """
        # Create a unique message identifier
        message_id = f"{message_type}:{message}"

        # Check if this exact message is already being processed
        if group_name in self.processing_messages and message_id in self.processing_messages[group_name]:
            logger.warning(
                f"Message '{message_id[:30]}...' in {group_name} is already being processed, skipping duplicate"
            )
            return

        # Mark this message as being processed
        if group_name not in self.processing_messages:
            self.processing_messages[group_name] = set()
        self.processing_messages[group_name].add(message_id)

        try:
            logger.info(f"Started handling {message_type} message in {group_name}")

            # Process with appropriate AI
            response = await self.process_message(group_name, message, message_type)

            # Send response back to WhatsApp if we got something
            if response and (response[0] or response[1]):  # If text or image is returned
                await self.send_response(response, group_name)
                logger.info(f"Completed handling message in {group_name}")
            else:
                logger.warning(f"No valid response obtained for message in {group_name}")
        except Exception as e:
            logger.error(f"Error handling message for {group_name}: {e}")
        finally:
            # Mark message as no longer being processed
            if group_name in self.processing_messages and message_id in self.processing_messages[group_name]:
                self.processing_messages[group_name].remove(message_id)
                logger.debug(f"Removed message '{message_id[:30]}...' from processing list for {group_name}")

    async def message_poller(self):
        """
        Poll for new messages and spawn tasks to handle them.
        This runs continuously until shutdown is requested.
        """
        cleanup_counter = 0
        group_names = list(self.config.get_ai_mappings().keys())

        # Initialize the processing tracking dict for each group
        for group_name in group_names:
            self.processing_messages[group_name] = set()

        # Set polling delay based on system load
        base_delay = self.config.loop_interval_delay
        min_delay = max(1.0, base_delay / 2)  # Never poll faster than once per second

        while not self.shutdown_event.is_set():
            try:
                # Adjust polling delay based on active tasks
                current_task_count = len(self.tasks)
                # Slow down polling if we have many active tasks
                adjusted_delay = min(base_delay * (1 + 0.2 * current_task_count), base_delay * 3)
                # But don't slow down too much
                actual_delay = max(min_delay, adjusted_delay)

                if current_task_count > 0:
                    logger.debug(f"Currently processing {current_task_count} messages, poll delay: {actual_delay:.2f}s")

                # Check for new messages in groups that aren't currently locked
                group_name, message, message_type = await self.check_messages(group_names)

                # Process new message if found
                if group_name and (message or message_type == "image"):
                    # Create a message identifier
                    message_id = f"{message_type}:{message}"

                    # Check if this message is already being processed
                    if message_id in self.processing_messages.get(group_name, set()):
                        logger.warning(f"Duplicate message detected in {group_name}, skipping")
                        continue

                    logger.info(f"New {message_type} message in {group_name}")

                    # Create a task to handle this message
                    task = asyncio.create_task(self.handle_message(group_name, message, message_type))
                    self.tasks.append(task)

                    # Clean up finished tasks
                    self.tasks = [t for t in self.tasks if not t.done()]

                # Periodically cleanup temp files
                cleanup_counter += 1
                if cleanup_counter >= 120:  # Every ~10 minutes (with 5s delay)
                    await self.cleanup_temp_files()
                    cleanup_counter = 0

                    # Also log stats about processing
                    logger.info(
                        f"Status: {len(self.tasks)} active tasks, "
                        + f"{sum(len(msgs) for msgs in self.processing_messages.values())} messages being processed"
                    )

                # Adaptive delay before next check
                await asyncio.sleep(actual_delay)

            except asyncio.CancelledError:
                logger.info("Message poller task was cancelled")
                break
            except Exception as e:
                logger.error(f"Error in message poller: {e}")
                await asyncio.sleep(base_delay * 2)  # Longer delay on error

    async def run_async(self):
        """
        Run the main automation loop with asyncio.
        """
        self.loop = asyncio.get_running_loop()

        try:
            # Setup browser and UI components
            setup_success = await self.setup()
            if not setup_success:
                logger.error("Setup failed, exiting")
                return

            logger.info("Starting async message monitoring")

            # Start the message poller
            poller_task = asyncio.create_task(self.message_poller())

            # Wait for shutdown signal (e.g., KeyboardInterrupt handled by run())
            await self.shutdown_event.wait()

            # Cancel the poller task
            poller_task.cancel()
            try:
                await poller_task
            except asyncio.CancelledError:
                pass

            # Wait for any remaining tasks to complete (with timeout)
            if self.tasks:
                logger.info(f"Waiting for {len(self.tasks)} active tasks to complete...")
                done, pending = await asyncio.wait(self.tasks, timeout=10)

                # Cancel any tasks that didn't complete within timeout
                for task in pending:
                    task.cancel()

        except Exception as e:
            logger.error(f"Unexpected error in run_async: {e}")
        finally:
            await self.cleanup_async()

    async def cleanup_async(self):
        """Close browser and perform cleanup asynchronously."""
        if self.browser_manager:
            await self.loop.run_in_executor(None, self.browser_manager.close)
        logger.info("Async cleanup completed")

    def run(self):
        """
        Entry point for the application.
        Sets up asyncio event loop and handles signals.
        """
        try:
            # Run the async application
            asyncio.run(self.run_async())
        except KeyboardInterrupt:
            logger.info("Shutting down...")
        except Exception as e:
            logger.error(f"Unexpected error in run: {e}")
            # Attempt synchronous cleanup as fallback
            self.cleanup()

    def cleanup(self):
        """Synchronous fallback cleanup method."""
        if self.browser_manager:
            self.browser_manager.close()
        logger.info("Cleanup completed")

    def signal_shutdown(self):
        """Signal all async tasks to shut down."""
        if self.loop and self.shutdown_event:
            # Use call_soon_threadsafe for thread safety
            self.loop.call_soon_threadsafe(self.shutdown_event.set)
            logger.info("Shutdown signaled")
