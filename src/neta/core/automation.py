import asyncio
import os
from typing import Dict, Optional, Tuple

from ..core.config import Config
from ..core.integration import IntegrationManager
from ..ui.browser import BrowserManager
from ..ui.whatsapp import WhatsAppUI
from ..utils.cache import MessageCache
from ..utils.files import ImageManager
from ..utils.logging import setup_logger

logger = setup_logger()


class NetaAutomation:
    """
    Main automation class for Neta with asyncio support,
    using a global browser_lock to serialize all UI interactions.
    """

    def __init__(self, config_path: Optional[str] = None):
        logger.info("Initializing Neta automation with asyncio support")

        self.config = Config(config_path)
        logger.info("Loaded configuration")

        cache_file = os.getenv("CACHE_FILE_PATH", ".cache.json")
        self.message_cache = MessageCache(cache_file)
        logger.info(f"Initialized message cache: {cache_file}")

        self.image_manager = ImageManager()
        logger.info(f"Initialized image manager: {self.image_manager.image_dir}")

        self.browser_manager = BrowserManager(self.image_manager.image_dir)

        self.whatsapp_ui: Optional[WhatsAppUI] = None
        self.integration_manager: Optional[IntegrationManager] = None

        # Single lock to serialize all WhatsApp UI operations
        self.browser_lock = asyncio.Lock()

        # Track messages in flight
        self.processing_messages: Dict[str, set] = {}

        # Event loop reference, set in run_async
        self.loop: Optional[asyncio.AbstractEventLoop] = None

        # Running tasks
        self.tasks: list = []

        # Signal to stop polling
        self.shutdown_event = asyncio.Event()

    async def setup(self) -> bool:
        try:
            logger.info("Setting up browser")
            self.browser_manager.setup_browser(
                self.config.get_whatsapp_url(),
                {},
                self.config.login_wait_delay,
            )

            self.whatsapp_ui = WhatsAppUI(
                self.browser_manager.driver,
                self.image_manager,
            )

            self.integration_manager = IntegrationManager(
                self.config,
                self.browser_manager.driver,
            )

            logger.info("Setup completed successfully")
            return True
        except Exception as e:
            logger.error(f"Setup failed: {e}")
            return False

    async def process_message(
        self, group_name: str, message: str, message_type: str
    ) -> Tuple[Optional[str], Optional[str]]:
        # No lock here: back-end processing can run fully in parallel
        try:
            logger.info(f"Processing {message_type} message for {group_name}")

            ai_config = self.config.get_ai_config(group_name)
            if not ai_config:
                logger.warning(f"No AI mapping found for group: {group_name}")
                return None, None

            platform_name = ai_config.get("api_platform", "").lower()
            if platform_name:
                logger.info(
                    f"Using API integration for {group_name} ({platform_name})"
                )
                return await self.loop.run_in_executor(
                    None,
                    lambda: self.integration_manager.process_message(
                        group_name, message, message_type
                    ),
                )
            return None, None

        except Exception as e:
            logger.error(f"Error processing message: {e}")
            return None, None

    async def check_messages(
        self, group_names: list
    ) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        # Serialize UI read operations
        async with self.browser_lock:
            try:
                tab_ok = await self.loop.run_in_executor(
                    None,
                    lambda: self.browser_manager.switch_to_tab("WhatsApp"),
                )
                if not tab_ok:
                    logger.error("Failed to switch to WhatsApp tab")
                    return None, None, None

                # Use ultra-fast batch preview check for all groups at once
                batch_previews = await self.loop.run_in_executor(
                    None,
                    lambda: self.whatsapp_ui.get_batch_chat_previews(group_names)
                )

                # Check if any group has new messages
                for group_name, has_new, message_preview, message_type in batch_previews:
                    if has_new:
                        logger.info(f"Batch preview detected new message in {group_name}, switching to detailed check")
                        # Now do detailed check for this specific group
                        return await self.loop.run_in_executor(
                            None,
                            lambda: self.whatsapp_ui.get_new_messages(
                                [group_name], self.message_cache
                            ),
                        )

                # If no batch preview found, do full check as fallback
                return await self.loop.run_in_executor(
                    None,
                    lambda: self.whatsapp_ui.get_new_messages(
                        group_names, self.message_cache
                    ),
                )
            except Exception as e:
                logger.error(f"Error checking messages: {e}")
                return None, None, None

    async def send_response(
        self,
        response_data: Tuple[Optional[str], Optional[str]],
        group_name: str,
    ) -> bool:
        # Serialize UI write operations
        async with self.browser_lock:
            try:
                # switch to WhatsApp tab
                if not await self.loop.run_in_executor(
                    None,
                    lambda: self.browser_manager.switch_to_tab("WhatsApp"),
                ):
                    logger.error("Failed to switch to WhatsApp tab")
                    return False

                # select the chat
                if not await self.loop.run_in_executor(
                    None,
                    lambda: self.whatsapp_ui.select_chat(group_name),
                ):
                    logger.error(f"Failed to select chat: {group_name}")
                    return False

                text_response, image_path = response_data

                # send message
                success = await self.loop.run_in_executor(
                    None,
                    lambda: self.whatsapp_ui.send_message(
                        text_response, image_path
                    ),
                )

                if success:
                    if text_response:
                        self.message_cache.cache_content(text_response, group_name)
                    if image_path:
                        self.message_cache.cache_content(
                            f"image:{image_path}", group_name
                        )
                    logger.info(f"Sent and cached response to {group_name}")

                return success
            except Exception as e:
                logger.error(f"Error sending response: {e}")
                return False

    async def cleanup_temp_files(self):
        await self.loop.run_in_executor(
            None, self.image_manager.cleanup_old_files
        )
        logger.info("Cleaned up temporary files")

    async def handle_message(
        self, group_name: str, message: str, message_type: str
    ):
        msg_id = f"{message_type}:{message}"
        self.processing_messages.setdefault(group_name, set())
        if msg_id in self.processing_messages[group_name]:
            logger.warning(
                f"Message '{msg_id[:30]}...' in {group_name} is already processing, skipping"
            )
            return

        self.processing_messages[group_name].add(msg_id)
        try:
            logger.info(f"Started handling {message_type} message in {group_name}")

            # Process message with AI (this is the potentially slow part)
            response = await self.process_message(
                group_name, message, message_type
            )

            if response and (response[0] or response[1]):
                # Send response immediately after getting AI response
                success = await self.send_response(response, group_name)
                if success:
                    logger.info(f"Completed handling message in {group_name}")
                else:
                    logger.error(f"Failed to send response to {group_name}")
            else:
                logger.warning(
                    f"No valid response obtained for message in {group_name}"
                )
        except Exception as e:
            logger.error(f"Error handling message for {group_name}: {e}")
        finally:
            self.processing_messages[group_name].remove(msg_id)

    async def message_poller(self):
        cleanup_counter = 0
        group_names = list(self.config.get_ai_mappings().keys())
        for group in group_names:
            self.processing_messages[group] = set()

        while not self.shutdown_event.is_set():
            try:
                # Check each group sequentially - one at a time
                for group_name in group_names:
                    # Check for new messages in this specific group
                    result = await self.check_messages([group_name])

                    if result[0] and (result[1] or result[2] == "image"):
                        logger.info(f"Found new message in {group_name}, processing...")

                        # Process this message and wait for AI response
                        task = asyncio.create_task(
                            self.handle_message(group_name, result[1], result[2])
                        )
                        self.tasks.append(task)

                        # Wait for this specific message to complete before moving to next group
                        await task
                        logger.info(f"Completed processing message in {group_name}, moving to next group...")

                    # Minimal delay between checking groups - reduced for faster scanning
                    await asyncio.sleep(0.01)

                cleanup_counter += 1
                if cleanup_counter >= 120:
                    await self.cleanup_temp_files()
                    cleanup_counter = 0

                # Prune done tasks
                self.tasks = [t for t in self.tasks if not t.done()]

                # Minimal throttle poll - reduced for faster response
                await asyncio.sleep(max(0.1, self.config.loop_interval_delay * 0.5))

            except asyncio.CancelledError:
                logger.info("Message poller cancelled")
                break
            except Exception as e:
                logger.error(f"Error in message poller: {e}")
                await asyncio.sleep(5)

    async def run_async(self):
        self.loop = asyncio.get_running_loop()
        try:
            if not await self.setup():
                logger.error("Setup failed, exiting")
                return

            logger.info("Starting async message monitor")
            poller = asyncio.create_task(self.message_poller())
            await self.shutdown_event.wait()
            poller.cancel()
            try:
                await poller
            except asyncio.CancelledError:
                pass

            if self.tasks:
                logger.info(
                    f"Waiting for {len(self.tasks)} active tasks to complete"
                )
                done, pending = await asyncio.wait(
                    self.tasks, timeout=10
                )
                for t in pending:
                    t.cancel()
        except Exception as e:
            logger.error(f"Unexpected error in run_async: {e}")
        finally:
            await self.cleanup_async()

    async def cleanup_async(self):
        async with self.browser_lock:
            if self.browser_manager:
                await self.loop.run_in_executor(
                    None, self.browser_manager.close
                )
        logger.info("Async cleanup completed")

    def run(self):
        try:
            asyncio.run(self.run_async())
        except KeyboardInterrupt:
            logger.info("Shutting down...")
        except Exception as e:
            logger.error(f"Unexpected error in run: {e}")
            self.cleanup()

    def cleanup(self):
        if self.browser_manager:
            self.browser_manager.close()
        logger.info("Cleanup completed")

    def signal_shutdown(self):
        if self.loop and self.shutdown_event:
            self.loop.call_soon_threadsafe(self.shutdown_event.set)
            logger.info("Shutdown signaled")
