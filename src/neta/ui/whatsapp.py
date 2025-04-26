"""WhatsApp UI interaction module for NETA."""

import logging
import time
import pyperclip
import os
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import TimeoutException, NoSuchElementException

logger = logging.getLogger(__name__)


class WhatsAppUI:
    """
    Handle WhatsApp Web UI interactions.
    """
    
    def __init__(self, driver, image_manager=None):
        """
        Initialize WhatsApp UI handler.
        
        Args:
            driver: Selenium WebDriver instance
            image_manager: ImageManager instance for handling images
        """
        self.driver = driver
        self.image_manager = image_manager
        self.current_chat = None
        self.image_download_delay = float(os.getenv("IMAGE_DOWNLOAD_DELAY", "2"))
        self.viewer_load_delay = float(os.getenv("VIEWER_LOAD_DELAY", "1"))
        self.viewer_close_delay = float(os.getenv("VIEWER_CLOSE_DELAY", "1"))
    
    def select_chat(self, group_name):
        """
        Select or verify the specified chat.
        
        Args:
            group_name: Name of the WhatsApp group
            
        Returns:
            Boolean indicating success
        """
        try:
            if self.current_chat != group_name:
                # Find and click the chat with the given group name
                chat_elements = self.driver.find_elements(By.CSS_SELECTOR, "div[role='listitem']")
                for chat in chat_elements:
                    try:
                        title_element = chat.find_element(By.CSS_SELECTOR, "span[title]")
                        chat_title = title_element.get_attribute("title")
                        if chat_title == group_name:
                            chat.click()
                            self.current_chat = group_name
                            logger.info(f"Selected chat: {group_name}")
                            return True
                    except NoSuchElementException:
                        continue
                logger.error(f"Could not find chat: {group_name}")
                return False
            return True
        except Exception as e:
            logger.error(f"Error selecting chat: {e}")
            return False
    
    def get_new_messages(self, group_names, message_cache):
        """
        Check for new messages in WhatsApp groups.
        
        Args:
            group_names: List of WhatsApp group names to check
            message_cache: MessageCache instance for tracking processed messages
            
        Returns:
            Tuple of (group_name, message, message_type) or (None, None, None) if no new messages
        """
        try:
            # Wait for the chat list to load
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div[role='listitem']"))
            )
            
            # Check each configured group
            for group_name in group_names:
                if not self.select_chat(group_name):
                    logger.warning(f"Skipping group {group_name} due to selection failure")
                    continue
                    
                # Wait for messages to load
                WebDriverWait(self.driver, 5).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "div.message-in, div.message-out"))
                )
                
                # Get all message containers
                message_containers = self.driver.find_elements(By.CSS_SELECTOR, "div.message-in, div.message-out")
                if not message_containers:
                    logger.debug(f"No messages found in {group_name}")
                    continue
                    
                # Check if the most recent message is from the current user (message-out)
                latest_container = message_containers[-1]
                message_type_divs = latest_container.find_elements(By.CSS_SELECTOR, "div.message-in, div.message-out")
                if message_type_divs and "message-out" in message_type_divs[0].get_attribute("class"):
                    logger.debug(f"Most recent message in {group_name} is from current user, skipping")
                    continue
                    
                # If we're here, the latest message is an incoming message (message-in)
                
                # Check for images in the latest incoming message
                result = self._check_for_image(latest_container, group_name, message_cache)
                if result:
                    return result
                
                # Check for text messages
                result = self._check_for_text(latest_container, group_name, message_cache)
                if result:
                    return result
            
            logger.debug("No new messages found in any group")
            return None, None, None
        except Exception as e:
            logger.error(f"Error fetching WhatsApp messages: {e}")
            return None, None, None
    
    def _check_for_image(self, container, group_name, message_cache):
        """
        Check for images in message container.
        
        Args:
            container: Message container element
            group_name: Name of the WhatsApp group
            message_cache: MessageCache instance
            
        Returns:
            Tuple of (group_name, image_path, "image") or None if no new image
        """
        try:
            # Prioritize blob: images, then data:image
            image_elements = container.find_elements(By.CSS_SELECTOR, "img[src^='blob:']")
            if not image_elements:
                image_elements = container.find_elements(By.CSS_SELECTOR, "img[src^='data:image']")
            
            if image_elements:
                # Use the first image element (preferably blob:)
                image_element = image_elements[0]
                img_src = image_element.get_attribute("src")
                if not img_src:
                    logger.error(f"No src attribute found for image in {group_name}, skipping")
                    return None
                
                # Hash the src for caching
                if message_cache.is_cached(img_src, group_name):
                    logger.debug(f"Image in {group_name} already processed")
                    return None
                
                image_path = self._download_image(image_element)
                if image_path:
                    time.sleep(self.image_download_delay)
                    message_cache.cache_content(img_src, group_name)
                    logger.info(f"New image detected in {group_name}")
                    return group_name, image_path, "image"
        except Exception as e:
            logger.error(f"Error checking for images in {group_name}: {e}")
        
        return None
    
    def _check_for_text(self, container, group_name, message_cache):
        """
        Check for text messages in message container.
        
        Args:
            container: Message container element
            group_name: Name of the WhatsApp group
            message_cache: MessageCache instance
            
        Returns:
            Tuple of (group_name, message_text, "text") or None if no new text
        """
        try:
            message_elements = container.find_elements(By.CSS_SELECTOR, "span.selectable-text")
            if message_elements:
                latest_message = message_elements[0].text
                if latest_message:
                    if message_cache.is_cached(latest_message, group_name):
                        logger.debug(f"Text message in {group_name} already processed")
                        return None
                    
                    # Cache the incoming text message before processing
                    message_cache.cache_content(latest_message, group_name)
                    logger.info(f"New text message detected in {group_name}: {latest_message[:50]}...")
                    return group_name, latest_message, "text"
        except Exception as e:
            logger.error(f"Error checking for text messages in {group_name}: {e}")
        
        return None
    
    def _download_image(self, img_element):
        """
        Download the full-resolution image by opening the image viewer.
        
        Args:
            img_element: Image element to download
            
        Returns:
            Path to downloaded image or None if download failed
        """
        try:
            logger.info("Attempting to download image...")
            
            # First attempt: Try clicking directly
            try:
                # Try clicking with multiple methods
                try:
                    # Method 1: Normal click
                    img_element.click()
                    logger.info("Clicked image directly")
                except Exception as e1:
                    logger.debug(f"Direct click failed: {e1}")
                    try:
                        # Method 2: JavaScript click
                        self.driver.execute_script("arguments[0].click();", img_element)
                        logger.info("Clicked image using JavaScript")
                    except Exception as e2:
                        logger.debug(f"JavaScript click failed: {e2}")
                        try:
                            # Method 3: Actions click
                            ActionChains(self.driver).move_to_element(img_element).click().perform()
                            logger.info("Clicked image using ActionChains")
                        except Exception as e3:
                            logger.debug(f"ActionChains click failed: {e3}")
                            # Method 4: Try click parent container
                            try:
                                parent_container = img_element.find_element(By.XPATH, "./ancestor::div[@role='button']")
                                parent_container.click()
                                logger.info("Clicked parent container")
                            except Exception as e4:
                                logger.error(f"All click methods failed: {e4}")
                                raise Exception("Failed to click image with all methods")
                
                # Wait for viewer to load
                time.sleep(self.viewer_load_delay)
                
                # Look for full image in viewer
                full_image = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "img[src^='blob:'], img.image-viewer"))
                )
                logger.info("Found full image in viewer")
                
                # Get the blob URL
                blob_src = full_image.get_attribute("src")
                if not blob_src:
                    logger.error("No src attribute found for full image")
                    raise Exception("No src attribute on full image")
                    
                # Fetch the blob content using script
                fetch_script = """
                async function fetchImage(url) {
                    try {
                        const response = await fetch(url);
                        const blob = await response.blob();
                        return new Promise(resolve => {
                            const reader = new FileReader();
                            reader.onloadend = () => resolve(reader.result);
                            reader.readAsDataURL(blob);
                        });
                    } catch (e) {
                        console.error('Error fetching image:', e);
                        return null;
                    }
                }
                return fetchImage(arguments[0]);
                """
                logger.info(f"Fetching image from blob URL: {blob_src[:50]}...")
                blob_data_url = self.driver.execute_script(fetch_script, blob_src)
                
                if blob_data_url and blob_data_url.startswith("data:image"):
                    # Save image
                    if self.image_manager:
                        img_path = self.image_manager.save_image_from_blob(blob_data_url)
                        
                        # Find download button (if available)
                        try:
                            download_buttons = self.driver.find_elements(By.XPATH, 
                                "//div[contains(@aria-label, 'Download') or contains(@title, 'Download')]" +
                                "|//button[contains(@aria-label, 'Download') or contains(@title, 'Download')]" +
                                "|//span[contains(@aria-label, 'Download') or contains(@title, 'Download')]"
                            )
                            if download_buttons:
                                download_buttons[0].click()
                                logger.info("Clicked download button in viewer")
                                time.sleep(1)  # Wait for download to start
                        except Exception as e:
                            logger.debug(f"No download button found or couldn't click it: {e}")
                        
                        # Close the image viewer
                        self._close_image_viewer()
                        return img_path
                    else:
                        logger.error("Image manager not available")
                        self._close_image_viewer()
                        return None
                else:
                    logger.error("Failed to fetch blob content from viewer")
                    self._close_image_viewer()
                    
            except Exception as e:
                logger.error(f"Error in primary download attempt: {e}")
                self._close_image_viewer()
            
            # Fallback to original image source if viewer method fails
            logger.info("Falling back to original image source")
            img_src = img_element.get_attribute("src")
            if img_src and img_src.startswith("data:image") and self.image_manager:
                logger.info("Using data:image source as fallback")
                img_path = self.image_manager.save_image_from_base64(img_src)
                return img_path
            
            logger.error("All download attempts failed")
            return None
            
        except Exception as e:
            logger.error(f"Error in download_image: {e}")
            self._close_image_viewer()  # Make sure viewer is closed
            return None
    
    def _close_image_viewer(self):
        """
        Helper method to close the image viewer if it's open.
        
        Returns:
            Boolean indicating success
        """
        try:
            # Try multiple selectors for close buttons
            selectors = [
                "button[aria-label='Close']", 
                "div[aria-label='Close']",
                "span[aria-label='Close']",
                "button.close-button",
                "svg[data-icon='close']",
                "div.modal-close-button"
            ]
            
            for selector in selectors:
                try:
                    close_buttons = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    if close_buttons:
                        close_buttons[0].click()
                        logger.info(f"Closed image viewer using selector: {selector}")
                        time.sleep(self.viewer_close_delay)
                        return True
                except Exception:
                    continue
                    
            # Fallback: Try escape key
            try:
                ActionChains(self.driver).send_keys(Keys.ESCAPE).perform()
                logger.info("Attempted to close viewer with ESC key")
                time.sleep(self.viewer_close_delay)
                return True
            except Exception as e:
                logger.debug(f"ESC key failed: {e}")
                
            return False
        except Exception as e:
            logger.error(f"Error closing image viewer: {e}")
            return False
    
    def send_message(self, message):
        """
        Send a message to the current WhatsApp chat.
        
        Args:
            message: Message text to send
            
        Returns:
            Boolean indicating success
        """
        try:
            # Ensure we're in the correct chat
            if not self.current_chat:
                logger.error("No active chat selected")
                return False
                
            # Use clipboard to handle special characters reliably
            pyperclip.copy(message)
            
            # Find and interact with the input field
            input_field = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div[aria-label='Type a message']"))
            )
            input_field.click()
            
            # Paste message using keyboard shortcut
            actions = ActionChains(self.driver)
            actions.key_down(Keys.COMMAND).send_keys('v').key_up(Keys.COMMAND).perform()
            
            # Send message
            input_field.send_keys(Keys.ENTER)
            logger.info(f"Sent message to WhatsApp: {message[:50]}...")
            
            return True
        except Exception as e:
            logger.error(f"Error sending to WhatsApp: {e}")
            return False