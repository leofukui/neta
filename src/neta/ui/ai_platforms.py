import logging
import os
import time

from selenium.common.exceptions import StaleElementReferenceException, TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
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
        Send text message to AI platform.

        Args:
            ai_config: Configuration for the AI platform
            message: Message to send

        Returns:
            AI response or None if failed
        """
        try:
            # Get current responses before sending message
            current_responses = self._get_current_responses(ai_config)

            # Create prompt with character limit guidance
            prompt = f"Respond in 50 characters or fewer. If asked for translation, only translate (fully). If asked 'complete', write a full description suitable for whatsapp (no emoji and only ascii chars): {message}"

            # Find input field
            input_field = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ai_config["input_selector"]))
            )

            # Clear existing text and send new message
            input_field.clear()
            self._type_text_gradually(input_field, prompt)
            input_field.send_keys(Keys.ENTER)

            logger.info(
                f"Sent text message to {ai_config['tab_name']} with prompt: {prompt[:50]}..."
            )

            # Wait for and get new response
            return self._wait_for_new_response(ai_config, current_responses)

        except Exception as e:
            logger.error(f"Error sending text to {ai_config['tab_name']}: {e}")
            return None

    def send_image(self, ai_config, image_path):
        """
        Send image to AI platform.

        Args:
            ai_config: Configuration for the AI platform
            image_path: Path to image file

        Returns:
            AI response or None if failed
        """
        try:
            # Get current responses before sending image
            current_responses = self._get_current_responses(ai_config)

            # Upload image
            if not self._upload_image(ai_config, image_path):
                return None

            # Wait for image processing
            time.sleep(self.image_processing_delay)

            # Verify image appears on page
            try:
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located(
                        (By.CSS_SELECTOR, ai_config.get("image_preview_selector", "img"))
                    )
                )
                logger.info("Image preview is visible on page")
            except Exception as e:
                logger.error(f"Image doesn't appear to be on page: {e}")

            # Add prompt for image description
            input_field = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ai_config["input_selector"]))
            )

            prompt = "Describe the image in 60 characters or fewer, with useful detail (product name, model, specie). Do not use emojis or invalid characters (only ascii)."

            input_field.click()
            input_field.clear()
            self._type_text_gradually(input_field, prompt)
            input_field.send_keys(Keys.ENTER)

            logger.info(f"Sent image prompt to {ai_config['tab_name']}")

            # Wait for and get new response
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
                current_responses = driver.find_elements(
                    By.CSS_SELECTOR, ai_config["response_selector"]
                )
                # Check if we have more responses than before
                if len(current_responses) > len(previous_responses):
                    # Get the newest response
                    new_response = current_responses[-1]
                    # Check if the new response has content
                    if new_response.text and len(new_response.text.strip()) > 0:
                        # Check if the response is still loading
                        # Look for loading indicators (customize based on the AI platform)
                        loading_indicators = ["typing", "loading", "thinking", "..."]
                        response_text = new_response.text.lower()
                        if not any(indicator in response_text for indicator in loading_indicators):
                            return new_response
                return False

            # Wait for new response with timeout
            response_element = WebDriverWait(self.driver, self.max_response_wait).until(
                new_response_appeared
            )

            # Wait for response to stabilize (ensure it's fully loaded)
            last_text = ""
            stable_count = 0
            max_stable_checks = 3  # Number of checks where text remains the same

            while stable_count < max_stable_checks:
                try:
                    current_text = response_element.text
                    if current_text == last_text:
                        stable_count += 1
                    else:
                        stable_count = 0
                    last_text = current_text
                    time.sleep(0.5)  # Small delay between checks
                except StaleElementReferenceException:
                    # Element might have been updated, try to get it again
                    response_element = self.driver.find_elements(
                        By.CSS_SELECTOR, ai_config["response_selector"]
                    )[-1]
                    stable_count = 0
                except Exception as e:
                    logger.error(f"Error during stability check: {e}")
                    break

            # Clean and return the response
            if response_element:
                return self._clean_response_text(response_element.text)
            else:
                return "No response"

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

    def _type_text_gradually(self, element, text):
        """
        Type text gradually to simulate human typing.

        Args:
            element: Element to type into
            text: Text to type
        """
        for char in text:
            element.send_keys(char)
            time.sleep(0.000001)  # Very small delay between characters

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
            return self._try_upload_buttons(image_path)

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
