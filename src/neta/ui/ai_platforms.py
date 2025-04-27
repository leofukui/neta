import io  # For in-memory file handling
import logging
import os
import platform  # To check OS
import subprocess  # To run pngpaste
import time

from PIL import Image
from selenium.common.exceptions import (  # More specific exceptions
    NoSuchElementException,
    StaleElementReferenceException,
    TimeoutException,
    WebDriverException,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys  # Needed for Cmd+V
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

logger = logging.getLogger(__name__)


class AIPlatformUI:
    """
    Handle AI platform UI interactions.
    """

    def __init__(self, driver):
        """
        Initialize AI Platform UI handler.

        Args:
            driver: Selenium WebDriver instance
        """
        self.driver = driver

        # Load configuration from environment variables
        self.upload_delay = float(os.getenv("UPLOAD_DELAY", "2"))
        self.image_processing_delay = float(os.getenv("IMAGE_PROCESSING_DELAY", "2"))
        self.response_wait_time_text = float(os.getenv("RESPONSE_WAIT_TIME_TEXT", "2"))
        self.response_wait_time_image = float(os.getenv("RESPONSE_WAIT_TIME_IMAGE", "5"))
        self.upload_button_delay = float(os.getenv("UPLOAD_BUTTON_DELAY", "2"))
        self.max_response_wait = float(
            os.getenv("MAX_RESPONSE_WAIT", "30")
        )  # Maximum wait time for response

    def send_text_message(self, ai_config, message):
        """
        Send text message to AI platform using clipboard paste.

        Args:
            ai_config: Configuration for the AI platform
            message: Message to send

        Returns:
            AI response or None if failed
        """
        try:
            current_responses = self._get_current_responses(ai_config)
            prompt = f"Respond in 50 characters or fewer. If asked for translation, only translate (fully). If asked 'complete', write a full description suitable for whatsapp (no emoji and only ascii chars): {message}"

            # Find input field
            input_field = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ai_config["input_selector"]))
            )

            # Clear existing text and paste prompt
            input_field.clear()
            self._paste_text(input_field, prompt)  # Use clipboard paste
            input_field.send_keys(Keys.ENTER)

            logger.info(
                f"Sent text message to {ai_config['tab_name']} with prompt: {prompt[:50]}..."
            )

            return self._wait_for_new_response(ai_config, current_responses)

        except Exception as e:
            logger.error(f"Error sending text to {ai_config['tab_name']}: {e}")
            return None

    def _paste_text(self, element, text):
        """
        Copy text to clipboard and paste it into the given element.

        Args:
            element: Web element to paste into
            text: Text to copy and paste
        """
        try:
            # Copy text to clipboard
            pyperclip.copy(text)

            # Ensure element is focused
            element.click()
            self.driver.execute_script("arguments[0].focus();", element)

            # Paste using Cmd+V (macOS)
            actions = ActionChains(self.driver)
            actions.key_down(Keys.COMMAND).send_keys("v").key_up(Keys.COMMAND).perform()

            logger.debug("Pasted text using clipboard")
            time.sleep(0.1)  # Small delay to ensure paste completes
        except Exception as e:
            logger.error(f"Error pasting text: {e}")
            # Fallback to direct send_keys if clipboard fails
            element.send_keys(text)

    def send_image(self, ai_config, image_path):
        """
        Send image to AI platform and paste prompt using clipboard.

        Args:
            ai_config: Configuration for the AI platform
            image_path: Path to image file

        Returns:
            AI response or None if failed
        """
        try:
            current_responses = self._get_current_responses(ai_config)
            if not self._upload_image(ai_config, image_path):
                return None

            time.sleep(self.image_processing_delay)

            try:
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located(
                        (By.CSS_SELECTOR, ai_config.get("image_preview_selector", "img"))
                    )
                )
                logger.info("Image preview is visible on page")
            except Exception as e:
                logger.error(f"Image doesn't appear to be on page: {e}")

            input_field = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ai_config["input_selector"]))
            )

            prompt = "Describe the image in 60 characters or fewer, with useful detail (product name, model, specie). Do not use emojis or invalid characters (only ascii)."

            input_field.click()
            input_field.clear()
            self._paste_text(input_field, prompt)  # Use clipboard paste
            input_field.send_keys(Keys.ENTER)

            logger.info(f"Sent image prompt to {ai_config['tab_name']}")

            return self._wait_for_new_response(ai_config, current_responses)

        except Exception as e:
            logger.error(f"Error sending image to {ai_config['tab_name']}: {e}")
            return None

    def _get_current_responses(self, ai_config):
        """
        Get current response elements on the page.

        Args:
            ai_config: Configuration for the AI platform

        Returns:
            List of response elements
        """
        try:
            response_elements = self.driver.find_elements(
                By.CSS_SELECTOR, ai_config["response_selector"]
            )
            return response_elements
        except Exception as e:
            logger.error(f"Error getting current responses: {e}")
            return []

    def _wait_for_new_response(self, ai_config, previous_responses):
        """
        Wait for a new response to appear and be fully loaded.

        Args:
            ai_config: Configuration for the AI platform
            previous_responses: List of response elements before the message was sent

        Returns:
            New response text or None if failed
        """
        try:
            # Wait for a new response element to appear
            def new_response_appeared(driver):
                try:
                    current_responses = driver.find_elements(
                        By.CSS_SELECTOR, ai_config["response_selector"]
                    )
                    # Check if we have more responses than before
                    if len(current_responses) > len(previous_responses):
                        # Get the newest response
                        new_response = current_responses[-1]
                        # Try to get the text with stale element handling
                        try:
                            response_text = new_response.text
                            if response_text and len(response_text.strip()) > 0:
                                # Check if the response is still loading
                                loading_indicators = ["typing", "loading", "thinking", "..."]
                                if not any(
                                    indicator in response_text.lower()
                                    for indicator in loading_indicators
                                ):
                                    return new_response
                        except StaleElementReferenceException:
                            # If element is stale, return False to keep waiting
                            return False
                    return False
                except Exception:
                    # If any error occurs, return False to keep waiting
                    return False

            # Wait for new response with timeout
            response_element = WebDriverWait(self.driver, self.max_response_wait).until(
                new_response_appeared
            )

            # Wait for response to stabilize (ensure it's fully loaded)
            last_text = ""
            stable_count = 0
            max_stable_checks = 3  # Number of checks where text remains the same
            max_retries = 5  # Maximum number of retries to handle stale elements

            while stable_count < max_stable_checks and max_retries > 0:
                try:
                    # Get fresh reference to the element
                    current_responses = self.driver.find_elements(
                        By.CSS_SELECTOR, ai_config["response_selector"]
                    )
                    if not current_responses:
                        logger.error("No responses found during stability check")
                        break

                    response_element = current_responses[-1]
                    current_text = response_element.text

                    if current_text == last_text:
                        stable_count += 1
                    else:
                        stable_count = 0
                    last_text = current_text
                    time.sleep(0.5)  # Small delay between checks

                except StaleElementReferenceException:
                    # Element might have been updated, try to get it again
                    max_retries -= 1
                    stable_count = 0
                    time.sleep(0.5)  # Wait a bit before retrying
                    logger.debug(f"Stale element encountered. Retries left: {max_retries}")
                    continue

                except Exception as e:
                    logger.error(f"Error during stability check: {e}")
                    break

            # Clean and return the response
            try:
                if response_element and response_element.text:
                    return self._clean_response_text(response_element.text)
                else:
                    return "No response"
            except StaleElementReferenceException:
                # One last attempt to get the text
                try:
                    current_responses = self.driver.find_elements(
                        By.CSS_SELECTOR, ai_config["response_selector"]
                    )
                    if current_responses:
                        return self._clean_response_text(current_responses[-1].text)
                except Exception as e:
                    logger.error(f"Final attempt to get text failed: {e}")
                    return None

        except TimeoutException:
            logger.error("Timeout waiting for new response")
            return None
        except Exception as e:
            logger.error(f"Error waiting for new response: {e}")
            return None

    def _clean_response_text(self, raw_response):
        """
        Clean the response text.

        Args:
            raw_response: Raw response text from the AI platform

        Returns:
            Cleaned response text
        """
        import re

        # Remove citation numbers like [1], [2], etc.
        response = re.sub(r"\[\d+\]", "", raw_response)
        # Remove other potential artifacts like source attribution texts
        response = re.sub(r"Source: .*?$", "", response, flags=re.MULTILINE)
        # Remove citation numbers like [1], [2], etc.
        response = re.sub(r"\[\d+\]", "", raw_response)
        # Remove other potential artifacts like source attribution texts
        response = re.sub(r"Source: .*?$", "", response, flags=re.MULTILINE)
        # Ensure proper line breaks for bullet lists
        response = re.sub(r"([^\n])(- )", r"\1\n\2", response)

        # Final cleanup of any double spaces and trim
        response = re.sub(r"\s+", " ", response).strip()

        # Special handling for multiline responses
        lines = response.split("\n")
        cleaned_lines = []
        for line in lines:
            line = line.strip()
            if line:
                cleaned_lines.append(line)
        response = "\n".join(cleaned_lines)

        return response

    def _upload_image(self, ai_config, image_path):
        """
        Upload image to AI platform.

        Args:
            ai_config: Configuration for the AI platform
            image_path: Path to image file

        Returns:
            Boolean indicating success
        """
        try:
            # Check for configured upload selector
            upload_selector = ai_config.get("file_upload_selector")
            if upload_selector:
                return self._upload_with_selector(upload_selector, image_path)

            # Try common file input selectors
            common_selectors = [
                "input[type='file']",
                "input[accept='image/*']",
                "[data-testid='file-input']",
                ".file-input",
            ]

            for selector in common_selectors:
                try:
                    file_inputs = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    if file_inputs:
                        if not file_inputs[0].is_displayed():
                            self.driver.execute_script(
                                "arguments[0].style.display = 'block'; arguments[0].style.visibility = 'visible';",
                                file_inputs[0],
                            )
                        file_inputs[0].send_keys(os.path.abspath(image_path))
                        logger.info(f"Uploaded image using auto-detected selector: {selector}")
                        time.sleep(self.upload_delay)
                        return True
                except Exception as e:
                    logger.debug(f"Failed with selector {selector}: {e}")

            # Try finding upload buttons
            if self._try_upload_buttons(image_path):
                return True

            return self._try_to_paste_on_text_edit(ai_config, image_path)

        except Exception as e:
            logger.error(f"Error uploading image: {e}")
            return False

    def _upload_with_selector(self, selector, image_path):
        """
        Upload image using specified selector.

        Args:
            selector: CSS selector for file input
            image_path: Path to image file

        Returns:
            Boolean indicating success
        """
        try:
            file_input = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, selector))
            )

            # Make input visible if it's hidden
            if not file_input.is_displayed():
                self.driver.execute_script(
                    "arguments[0].style.display = 'block'; arguments[0].style.visibility = 'visible';",
                    file_input,
                )

            file_input.send_keys(os.path.abspath(image_path))
            logger.info("Uploaded image using specified selector")
            time.sleep(self.upload_delay)
            return True
        except Exception as e:
            logger.error(f"Error using specified upload selector: {e}")
            return False

    def _try_upload_buttons(self, image_path):
        """
        Try to find and use upload buttons.

        Args:
            image_path: Path to image file

        Returns:
            Boolean indicating success
        """
        try:
            # Look for buttons that might be for uploading
            upload_elements = self.driver.find_elements(
                By.XPATH,
                "//button[contains(@aria-label, 'upload') or contains(., 'upload') or contains(., 'Upload') or contains(., 'image') or contains(., 'Image')]"
                + "|//div[contains(@aria-label, 'upload') or contains(., 'upload') or contains(., 'Upload') or contains(., 'image') or contains(., 'Image')]"
                + "|//span[contains(@aria-label, 'upload') or contains(., 'upload') or contains(., 'Upload') or contains(., 'image') or contains(., 'Image')]",
            )

            if upload_elements:
                upload_elements[0].click()
                logger.info("Clicked on potential upload element")
                time.sleep(self.upload_button_delay)

                # Look for file inputs that might have appeared
                file_inputs = self.driver.find_elements(By.CSS_SELECTOR, "input[type='file']")
                if file_inputs:
                    file_inputs[0].send_keys(os.path.abspath(image_path))
                    logger.info("Uploaded image after clicking upload button")
                    time.sleep(self.upload_delay)
                    return True

            logger.error("Could not find any working file input")
            return False
        except Exception as e:
            logger.error(f"Error with upload buttons: {e}")
            return False

    def _copy_image_to_clipboard_macos(self, image_path):
        """
        Attempts to copy image data to the macOS clipboard using osascript and/or shell commands.

        Args:
            image_path: Absolute path to the image file.

        Returns:
            Boolean indicating success.
        """
        try:
            # Method 1: Using osascript with simplified approach
            applescript = f"""
            set theFile to POSIX file "{image_path}"
            set imageData to (read file theFile as TIFF picture)
            set the clipboard to imageData
            """

            result = subprocess.run(
                ["osascript", "-e", applescript], capture_output=True, text=True, timeout=10
            )

            if result.returncode == 0:
                logger.info("Image copied to clipboard successfully using AppleScript")
                return True
            else:
                logger.warning(f"AppleScript failed: {result.stderr}")

            # Method 2: Using hexdump and pbcopy
            cmd = f'hexdump -ve "1/1 \\"%.2x\\"" "{image_path}" | xxd -r -p | pbcopy'
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)

            if result.returncode == 0:
                logger.info("Image copied to clipboard using hexdump method")
                return True
            else:
                logger.warning(f"Hexdump method failed: {result.stderr}")

            # Method 3: Using Python's subprocess with image data
            try:
                with open(image_path, "rb") as f:
                    image_data = f.read()

                process = subprocess.Popen(["pbcopy"], stdin=subprocess.PIPE)
                process.communicate(image_data)

                if process.returncode == 0:
                    logger.info("Image copied to clipboard using direct pbcopy")
                    return True
            except Exception as e:
                logger.warning(f"Direct pbcopy method failed: {e}")

            # Method 4: Using osascript with file URL approach
            applescript = f"""
            set fileURL to POSIX file "{image_path}" as alias
            tell application "System Events"
                set the clipboard to (read fileURL as picture)
            end tell
            """

            result = subprocess.run(
                ["osascript", "-e", applescript], capture_output=True, text=True, timeout=10
            )

            if result.returncode == 0:
                logger.info("Image copied to clipboard using System Events")
                return True
            else:
                logger.error(f"All methods failed. Last error: {result.stderr}")
                return False

        except subprocess.TimeoutExpired:
            logger.error("Clipboard operation timed out")
            return False
        except Exception as e:
            logger.error(f"Error copying image to clipboard: {e}", exc_info=True)
            return False

    def _try_to_paste_on_text_edit(self, ai_config, image_path):
        """
        Tries to upload an image by pasting it into the text editor (macOS).

        Args:
            ai_config: Configuration for the AI platform
            image_path: Absolute path to image file

        Returns:
            Boolean indicating success
        """
        logger.info(f"Attempting paste upload for: {image_path}")

        # 1. Copy image to clipboard
        if not self._copy_image_to_clipboard_macos(image_path):
            logger.error("Failed to copy image to clipboard. Paste attempt aborted.")
            return False

        # 2. Find and interact with the text editor using input_selector from config
        try:
            input_selector = ai_config["input_selector"]
            logger.info(f"Using configured input selector: {input_selector}")

            text_editor = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, input_selector))
            )
            logger.info("Found text editor using configured selector")

        except KeyError:
            logger.error("No input_selector found in ai_config")
            return False
        except TimeoutException:
            logger.error(f"Could not find text editor with selector: {input_selector}")
            return False
        except Exception as e:
            logger.error(f"Error finding text editor: {e}")
            return False

        try:
            # 3. Click and ensure focus
            logger.info("Clicking text editor to ensure focus.")
            text_editor.click()
            time.sleep(0.5)

            # Try clicking again with JavaScript for double assurance
            self.driver.execute_script("arguments[0].focus();", text_editor)
            self.driver.execute_script("arguments[0].click();", text_editor)
            time.sleep(0.3)

            # 4. Paste using multiple methods
            logger.info("Sending Paste command (Cmd+V).")

            # Method 1: Direct Cmd+V
            try:
                text_editor.send_keys(Keys.COMMAND, "v")
                logger.info("Sent Cmd+V directly")
            except Exception as e:
                logger.warning(f"Direct Cmd+V failed: {e}")

                # Method 2: ActionChains
                try:
                    from selenium.webdriver.common.action_chains import ActionChains

                    actions = ActionChains(self.driver)
                    actions.move_to_element(text_editor)
                    actions.click()
                    actions.key_down(Keys.COMMAND).send_keys("v").key_up(Keys.COMMAND)
                    actions.perform()
                    logger.info("Used ActionChains for paste")
                except Exception as e2:
                    logger.warning(f"ActionChains paste failed: {e2}")

                    # Method 3: JavaScript paste event
                    try:
                        self.driver.execute_script(
                            """
                                var element = arguments[0];
                                var pasteEvent = new Event('paste', {
                                    bubbles: true,
                                    cancelable: true
                                });
                                element.dispatchEvent(pasteEvent);
                            """,
                            text_editor,
                        )
                        logger.info("Triggered paste event via JavaScript")
                    except Exception as e3:
                        logger.error(f"JavaScript paste event failed: {e3}")
                        return False

            # 5. Wait for image to appear
            logger.info(f"Waiting {self.upload_delay} seconds after paste...")
            time.sleep(self.upload_delay)

            # 6. Verify image appeared
            try:
                preview_selectors = [
                    "img[src*='blob:']",
                    "img[src*='data:']",
                    "[data-testid='image-preview']",
                    ".image-preview",
                    ai_config.get("image_preview_selector", ""),
                    "div[aria-label*='image']",
                    ".thumbnail",
                    "img:not([src=''])",
                ]

                image_found = False
                for selector in preview_selectors:
                    if not selector:
                        continue
                    try:
                        elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                        if elements:
                            logger.info(f"Image preview detected with selector: {selector}")
                            image_found = True
                            break
                    except:
                        continue

                if not image_found:
                    logger.warning("Could not verify if image was successfully pasted")
                    # Try to check if the input value changed
                    try:
                        input_value = text_editor.get_attribute("value") or text_editor.text
                        if input_value and len(input_value) > 0:
                            logger.info("Input field has content - paste may have succeeded")
                            return True
                    except:
                        pass

            except Exception as e:
                logger.warning(f"Error verifying image paste: {e}")

            logger.info("Paste command sequence completed.")
            return True

        except WebDriverException as e:
            logger.error(f"WebDriver error during paste attempt: {e}", exc_info=True)
            return False
        except Exception as e:
            logger.error(f"Unexpected error during paste attempt: {e}", exc_info=True)
            return False

    def refresh_page(self):
        """
        Refresh the current AI platform page.

        Returns:
            Boolean indicating success
        """
        try:
            self.driver.refresh()
            time.sleep(0.5)
            logger.info("Refreshed AI platform page")
            return True
        except Exception as e:
            logger.error(f"Error refreshing page: {e}")
            return False
