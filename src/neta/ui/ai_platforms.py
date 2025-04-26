"""AI platform UI interaction module for NETA."""

import logging
import os
import time
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import TimeoutException

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
            # Create prompt with character limit guidance
            prompt = f"Respond in 50 characters or fewer, if I ask for translation only give me it translated. if I mention to be completed can be a comoplete message suitable for whatsapp: {message}"
            
            # Find input field
            input_field = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ai_config["input_selector"]))
            )
            
            # Clear existing text and send new message
            input_field.clear()
            self._type_text_gradually(input_field, prompt)
            input_field.send_keys(Keys.ENTER)
            
            logger.info(f"Sent text message to {ai_config['tab_name']} with prompt: {prompt[:50]}...")
            
            # Wait for response
            time.sleep(self.response_wait_time_text)
            
            # Get response
            return self._get_response(ai_config)
            
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
            # Upload image
            if not self._upload_image(ai_config, image_path):
                return None
                
            # Wait for image processing
            time.sleep(self.image_processing_delay)
            
            # Verify image appears on page
            try:
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, ai_config.get("image_preview_selector", "img")))
                )
                logger.info("Image preview is visible on page")
            except Exception as e:
                logger.error(f"Image doesn't appear to be on page: {e}")
            
            # Add prompt for image description
            input_field = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ai_config["input_selector"]))
            )
            
            prompt = "Describe this image in 60 characters or fewer (short but give detail as I am trying to get proper info from it), if there is no image and I finish it with 'complete' you can give me a description that is good for a complete whatsapp message about it, if it a image describe what it is, give it back. If I ask for translation never put emoji or any other invalid characters:"
            
            input_field.click()
            input_field.clear()
            self._type_text_gradually(input_field, prompt)
            input_field.send_keys(Keys.ENTER)
            
            logger.info(f"Sent image prompt to {ai_config['tab_name']}")
            
            # Wait for response
            time.sleep(self.response_wait_time_image)
            
            # Get response
            return self._get_response(ai_config)
            
        except Exception as e:
            logger.error(f"Error sending image to {ai_config['tab_name']}: {e}")
            return None
    
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
                ".file-input"
            ]
            
            for selector in common_selectors:
                try:
                    file_inputs = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    if file_inputs:
                        if not file_inputs[0].is_displayed():
                            self.driver.execute_script(
                                "arguments[0].style.display = 'block'; arguments[0].style.visibility = 'visible';", 
                                file_inputs[0]
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
                    file_input
                )
                
            file_input.send_keys(os.path.abspath(image_path))
            logger.info(f"Uploaded image using specified selector")
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
            upload_elements = self.driver.find_elements(By.XPATH, 
                "//button[contains(@aria-label, 'upload') or contains(., 'upload') or contains(., 'Upload') or contains(., 'image') or contains(., 'Image')]" +
                "|//div[contains(@aria-label, 'upload') or contains(., 'upload') or contains(., 'Upload') or contains(., 'image') or contains(., 'Image')]" +
                "|//span[contains(@aria-label, 'upload') or contains(., 'upload') or contains(., 'Upload') or contains(., 'image') or contains(., 'Image')]"
            )
            
            if upload_elements:
                upload_elements[0].click()
                logger.info(f"Clicked on potential upload element")
                time.sleep(self.upload_button_delay)
                
                # Look for file inputs that might have appeared
                file_inputs = self.driver.find_elements(By.CSS_SELECTOR, "input[type='file']")
                if file_inputs:
                    file_inputs[0].send_keys(os.path.abspath(image_path))
                    logger.info(f"Uploaded image after clicking upload button")
                    time.sleep(self.upload_delay)
                    return True
            
            logger.error("Could not find any working file input")
            return False
        except Exception as e:
            logger.error(f"Error with upload buttons: {e}")
            return False
    
    def _get_response(self, ai_config):
        """
        Get response from AI platform.
        
        Args:
            ai_config: Configuration for the AI platform
            
        Returns:
            Cleaned response text or None if failed
        """
        try:
            # Wait for response element
            response_element = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ai_config["response_selector"]))
            )
            
            if response_element:
                raw_response = response_element.text
                
                # Clean the response
                import re
                # Remove citation numbers like [1], [2], etc.
                response = re.sub(r'\[\d+\]', '', raw_response)
                # Remove other potential artifacts like source attribution texts
                response = re.sub(r'Source: .*?$', '', response, flags=re.MULTILINE)
                # Remove any numbered footnotes like ¹, ², ³
                response = re.sub(r'[¹²³⁴⁵⁶⁷⁸⁹⁰]', '', response)
                # Final cleanup of any double spaces and trim
                response = re.sub(r'\s+', ' ', response).strip()
                
                logger.info(f"Received response: {response[:50]}...")
                return response
            else:
                return "No response"
                
        except TimeoutException:
            logger.error(f"Timeout waiting for response")
            return None
        except Exception as e:
            logger.error(f"Error getting response: {e}")
            return None
    
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