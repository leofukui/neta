import json
import logging
import time
import os
import base64
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException, ElementClickInterceptedException
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
import pyperclip
import hashlib
import tempfile

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("automation.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class WhatsAppAIAutomation:
    def __init__(self):
        logger.info("Entering __init__")
        try:
            self.config = self.load_config(os.getenv("CONFIG_PATH", "config.json"))
            self.cache_file = os.getenv("CACHE_FILE_PATH", ".cache.json")
            logger.info(f"Initialized cache_file: {self.cache_file}")

            self.driver = None
            self.tabs = {}
            self.whatsapp_window = None

            # Ensure cache file directory exists
            cache_dir = os.path.dirname(self.cache_file) if os.path.dirname(self.cache_file) else "."
            if not os.path.exists(cache_dir):
                os.makedirs(cache_dir, exist_ok=True)
                logger.info(f"Created cache directory: {cache_dir}")

            self.message_cache = self.load_cache()  # Load persistent cache
            self.image_dir = os.path.join(tempfile.gettempdir(), "whatsapp_temp_images")
            self.current_chat = None  # Track current chat

            # Load delay configurations from .env with defaults
            self.upload_delay = float(os.getenv("UPLOAD_DELAY", "2"))
            self.image_processing_delay = float(os.getenv("IMAGE_PROCESSING_DELAY", "2"))
            self.response_wait_time_text = float(os.getenv("RESPONSE_WAIT_TIME_TEXT", "2"))
            self.response_wait_time_image = float(os.getenv("RESPONSE_WAIT_TIME_IMAGE", "5"))
            self.image_download_delay = float(os.getenv("IMAGE_DOWNLOAD_DELAY", "2"))
            self.viewer_load_delay = float(os.getenv("VIEWER_LOAD_DELAY", "1"))
            self.viewer_close_delay = float(os.getenv("VIEWER_CLOSE_DELAY", "1"))
            self.upload_button_delay = float(os.getenv("UPLOAD_BUTTON_DELAY", "2"))
            self.login_wait_delay = float(os.getenv("LOGIN_WAIT_DELAY", "1"))
            self.loop_interval_delay = float(os.getenv("LOOP_INTERVAL_DELAY", "5"))

            # Create directory for temporary image storage
            if not os.path.exists(self.image_dir):
                os.makedirs(self.image_dir)

            logger.info("Completed __init__ successfully")
        except Exception as e:
            logger.error(f"Error in __init__: {e}")
            raise

    def load_config(self, config_path):
        try:
            with open(config_path, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            raise

    def load_cache(self):
        """Load message cache from JSON file, create file if it doesn't exist"""
        try:
            if not os.path.exists(self.cache_file):
                logger.info(f"Cache file not found at {self.cache_file}, creating new cache file")
                with open(self.cache_file, 'w') as f:
                    json.dump({}, f)
                logger.info(f"Created new cache file at {self.cache_file}")
                return {}
            
            with open(self.cache_file, 'r') as f:
                cache = json.load(f)
                logger.info(f"Loaded cache from {self.cache_file} with {len(cache)} entries")
                return cache
        except Exception as e:
            logger.error(f"Failed to load cache from {self.cache_file}: {e}")
            return {}

    def save_cache(self):
        """Save message cache to JSON file"""
        try:
            with open(self.cache_file, 'w') as f:
                json.dump(self.message_cache, f)
            logger.info(f"Saved cache to {self.cache_file} with {len(self.message_cache)} entries")
        except Exception as e:
            logger.error(f"Failed to save cache to {self.cache_file}: {e}")

    def setup_browser(self):
        """Initialize Chrome and open tabs in a single window with persistent profile."""
        chrome_options = Options()
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option("useAutomationExtension", False)
        
        # Set download directory to temporary folder
        chrome_options.add_experimental_option(
            "prefs", {
                "download.default_directory": os.path.abspath(self.image_dir),
                "download.prompt_for_download": False,
                "download.directory_upgrade": True,
                "safebrowsing.enabled": True
            }
        )
        
        # Load Chrome profile path from .env
        chrome_profile_path = os.getenv("CHROME_PROFILE_PATH")
        if not chrome_profile_path:
            logger.error("CHROME_PROFILE_PATH not set in .env file. Please configure it.")
            raise ValueError("CHROME_PROFILE_PATH is required in .env file")
        
        # Check and create Chrome profile directory
        if not os.path.exists(chrome_profile_path):
            logger.info(f"Chrome profile directory {chrome_profile_path} does not exist. Creating it...")
            os.makedirs(chrome_profile_path, exist_ok=True)
        
        chrome_options.add_argument(f"--user-data-dir={chrome_profile_path}")
        chrome_options.add_argument("--profile-directory=Profile 1")
        
        self.driver = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()),
            options=chrome_options
        )
        self.driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": """
                Object.defineProperty(navigator, 'webdriver', { get: () => false });
                Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3] });
                Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
            """
        })
        # Open WhatsApp
        self.driver.get(self.config["whatsapp_url"])
        self.whatsapp_window = self.driver.current_window_handle
        self.tabs["WhatsApp"] = self.whatsapp_window
        logger.info("Opened WhatsApp Web tab")
        # Open AI platform tabs
        for group, ai_config in self.config["ai_mappings"].items():
            self.driver.execute_script("window.open('');")
            new_window = self.driver.window_handles[-1]
            self.driver.switch_to.window(new_window)
            self.driver.get(ai_config["url"])
            self.tabs[ai_config["tab_name"]] = new_window
            logger.info(f"Opened tab for {ai_config['tab_name']}")
        logger.info(f"Please log in to all platforms. Waiting for {self.login_wait_delay} seconds...")
        time.sleep(self.login_wait_delay)

    def hash_content(self, content):
        """Create a hash of the content (text or image src)"""
        # Normalize content by stripping whitespace and converting to lowercase
        normalized_content = content.strip().lower()
        return hashlib.md5(normalized_content.encode()).hexdigest()

    def is_cached(self, content_key, group_name):
        """Check if content has been processed before"""
        cache_key = f"{group_name}:{content_key}"
        is_cached = cache_key in self.message_cache
        logger.debug(f"Checking cache for {cache_key}: {'cached' if is_cached else 'not cached'}")
        return is_cached

    def cache_content(self, content_key, group_name):
        """Add content to cache and save to file"""
        cache_key = f"{group_name}:{content_key}"
        self.message_cache[cache_key] = time.time()
        logger.debug(f"Caching content with key: {cache_key}")
        self.save_cache()

    def download_image(self, img_element):
        """Download the full-resolution image by opening the image viewer"""
        try:
            logger.info("Attempting to download image...")
            
            # First attempt: Try clicking directly with a more robust approach
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
                    
                # Fetch the blob content using more reliable script
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
                    # Extract base64 data and save
                    img_data = blob_data_url.split(",")[1]
                    img_bytes = base64.b64decode(img_data)
                    img_path = os.path.join(self.image_dir, f"whatsapp_image_{int(time.time())}.png")
                    with open(img_path, "wb") as img_file:
                        img_file.write(img_bytes)
                    logger.info(f"Successfully saved full image to {img_path}")
                    
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
                    self.close_image_viewer()
                    return img_path
                else:
                    logger.error("Failed to fetch blob content from viewer")
                    self.close_image_viewer()
                    
            except Exception as e:
                logger.error(f"Error in primary download attempt: {e}")
                self.close_image_viewer()
            
            # Fallback to original image source if viewer method fails
            logger.info("Falling back to original image source")
            img_src = img_element.get_attribute("src")
            if img_src and img_src.startswith("data:image"):
                logger.info("Using data:image source as fallback")
                img_data = img_src.split(",")[1]
                img_bytes = base64.b64decode(img_data)
                img_path = os.path.join(self.image_dir, f"whatsapp_image_{int(time.time())}.png")
                with open(img_path, "wb") as img_file:
                    img_file.write(img_bytes)
                logger.info(f"Saved image from original data URL to {img_path}")
                return img_path
                
            # If all attempts failed, try accessing download attribute directly
            download_url = img_element.get_attribute("data-download")
            if download_url:
                logger.info("Found direct download URL, attempting to use it")
                try:
                    response = requests.get(download_url)
                    if response.status_code == 200:
                        img_path = os.path.join(self.image_dir, f"whatsapp_image_{int(time.time())}.png")
                        with open(img_path, "wb") as img_file:
                            img_file.write(response.content)
                        logger.info(f"Downloaded image from direct URL to {img_path}")
                        return img_path
                except Exception as e:
                    logger.error(f"Failed to download from direct URL: {e}")
            
            logger.error("All download attempts failed")
            return None
            
        except Exception as e:
            logger.error(f"Error in download_image: {e}")
            self.close_image_viewer()  # Make sure viewer is closed
            return None

    def close_image_viewer(self):
        """Helper method to close the image viewer if it's open"""
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
            except Exception as e:
                logger.debug(f"ESC key failed: {e}")
                
            return False
        except Exception as e:
            logger.error(f"Error closing image viewer: {e}")
            return False


    def select_chat(self, group_name):
        """Select or verify the specified chat"""
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
    
    def get_whatsapp_messages(self):
        try:
            self.driver.switch_to.window(self.tabs["WhatsApp"])
            
            # Wait for the chat list to load
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div[role='listitem']"))
            )
            
            # Get group name from config (we'll process only mapped groups)
            for group_name in self.config["ai_mappings"].keys():
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
                # Find message-in or message-out within the container
                message_type_divs = latest_container.find_elements(By.CSS_SELECTOR, "div.message-in, div.message-out")
                if message_type_divs and "message-out" in message_type_divs[0].get_attribute("class"):
                    logger.debug(f"Most recent message in {group_name} is from current user, skipping")
                    continue
                    
                # If we're here, the latest message is an incoming message (message-in)
                
                # Check for images in the latest incoming message
                try:
                    # Prioritize blob: images, then data:image
                    image_elements = latest_container.find_elements(By.CSS_SELECTOR, "img[src^='blob:']")
                    if not image_elements:
                        image_elements = latest_container.find_elements(By.CSS_SELECTOR, "img[src^='data:image']")
                    
                    if image_elements:
                        # Use the first image element (preferably blob:)
                        image_element = image_elements[0]
                        img_src = image_element.get_attribute("src")
                        if not img_src:
                            logger.error(f"No src attribute found for image in {group_name}, skipping")
                            continue
                        
                        # Hash the src for caching
                        content_key = self.hash_content(img_src)
                        if self.is_cached(content_key, group_name):
                            logger.debug(f"Image with src hash {content_key} in {group_name} already processed")
                            continue
                        
                        image_path = self.download_image(image_element)
                        if image_path:
                            time.sleep(self.image_download_delay)  # Configurable delay for image processing
                            self.cache_content(content_key, group_name)
                            logger.info(f"New image detected in {group_name}, src hash: {content_key}")
                            return group_name, image_path, "image"
                except Exception as e:
                    logger.error(f"Error checking for images in {group_name}: {e}")

                # Check for text messages
                try:
                    message_elements = latest_container.find_elements(By.CSS_SELECTOR, "span.selectable-text")
                    if message_elements:
                        latest_message = message_elements[0].text
                        if latest_message:
                            content_key = self.hash_content(latest_message)
                            if self.is_cached(content_key, group_name):
                                logger.debug(f"Text message in {group_name} with hash {content_key} already processed")
                                continue
                            
                            # Cache the incoming text message before processing
                            self.cache_content(content_key, group_name)
                            logger.info(f"New text message detected in {group_name}: {latest_message[:50]}...")
                            return group_name, latest_message, "text"
                except Exception as e:
                    logger.error(f"Error checking for text messages in {group_name}: {e}")
            
            logger.debug("No new messages found in any group")
            return None, None, None
        except Exception as e:
            logger.error(f"Error fetching WhatsApp messages: {e}")
            return None, None, None
        
    def upload_image_to_ai(self, ai_config, image_path):
        """Upload image to AI platform by using file input"""
        try:
            upload_selector = ai_config.get("file_upload_selector")
            if not upload_selector:
                logger.warning(f"No file upload selector defined for {ai_config['tab_name']}")
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
                            logger.info(f"Uploaded image using auto-detected selector: {image_path}")
                            time.sleep(self.upload_delay)  # Configurable delay
                            return True
                    except Exception as e:
                        logger.debug(f"Failed with selector {selector}: {e}")
                
                try:
                    upload_elements = self.driver.find_elements(By.XPATH, 
                        "//button[contains(@aria-label, 'upload') or contains(., 'upload') or contains(., 'Upload') or contains(., 'image') or contains(., 'Image')]" +
                        "|//div[contains(@aria-label, 'upload') or contains(., 'upload') or contains(., 'Upload') or contains(., 'image') or contains(., 'Image')]" +
                        "|//span[contains(@aria-label, 'upload') or contains(., 'upload') or contains(., 'Upload') or contains(., 'image') or contains(., 'Image')]"
                    )
                    if upload_elements:
                        upload_elements[0].click()
                        logger.info(f"Clicked on potential upload element in {ai_config['tab_name']}")
                        time.sleep(self.upload_button_delay)
                        file_inputs = self.driver.find_elements(By.CSS_SELECTOR, "input[type='file']")
                        if file_inputs:
                            file_inputs[0].send_keys(os.path.abspath(image_path))
                            logger.info(f"Uploaded image after clicking upload button: {image_path}")
                            time.sleep(self.upload_delay)  # Configurable delay
                            return True
                except Exception as e:
                    logger.error(f"Failed to detect upload button: {e}")
                
                logger.error(f"Could not find any working file input for {ai_config['tab_name']}")
                return False
                
            try:
                file_input = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, upload_selector))
                )
                if not file_input.is_displayed():
                    self.driver.execute_script(
                        "arguments[0].style.display = 'block'; arguments[0].style.visibility = 'visible';", 
                        file_input
                    )
                file_input.send_keys(os.path.abspath(image_path))
                logger.info(f"Uploaded image {image_path} to {ai_config['tab_name']}")
                time.sleep(self.upload_delay)  # Configurable delay
                return True
            except Exception as e:
                logger.error(f"Error uploading file: {e}")
                try:
                    upload_buttons = self.driver.find_elements(By.XPATH, 
                        "//button[contains(@aria-label, 'upload') or contains(., 'upload') or contains(., 'Upload') or contains(., 'image') or contains(., 'Image')]"
                    )
                    if upload_buttons:
                        upload_buttons[0].click()
                        logger.info("Clicked on upload button")
                        time.sleep(self.upload_button_delay)
                        file_inputs = self.driver.find_elements(By.XPATH, "//input[@type='file']")
                        if file_inputs:
                            file_inputs[0].send_keys(os.path.abspath(image_path))
                            logger.info(f"Uploaded image using alternative method: {image_path}")
                            time.sleep(self.upload_delay)  # Configurable delay
                            return True
                except Exception as e2:
                    logger.error(f"Alternative upload method failed: {e2}")
                return False
                
        except Exception as e:
            logger.error(f"Error in upload_image_to_ai: {e}")
            return False

    def send_to_ai(self, group_name, message, message_type):
        ai_config = self.config["ai_mappings"].get(group_name)
        if not ai_config:
            logger.warning(f"No AI mapping found for group: {group_name}")
            return None
        
        tab_name = ai_config["tab_name"]
        window_handle = self.tabs.get(tab_name)
        
        if not window_handle:
            logger.error(f"Tab {tab_name} not found")
            return None
        
        try:
            self.driver.switch_to.window(window_handle)
            
            if message_type == "text":
                prompt = f"Respond in 50 characters or fewer, if I ask for translation only give me it translated. if I mention to be completed can be a comopelte message suitable for whatsapp: {message}"
                input_field = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, ai_config["input_selector"]))
                )
                input_field.clear()
                for char in prompt:
                    input_field.send_keys(char)
                    time.sleep(0.00001)
                input_field.send_keys(Keys.ENTER)
                logger.info(f"Sent text message to {tab_name} with prompt: {prompt}")
                
            else: 
                # 1. Make sure upload function works correctly
                upload_success = self.upload_image_to_ai(ai_config, message)
                if not upload_success:
                    logger.error(f"Failed to upload image to {tab_name}")
                    return None

                # 2. Increase the wait time after upload
                time.sleep(self.image_processing_delay)
                logger.info(f"Waited for image processing in {tab_name}")

                # 3. Check if image actually appears on the page
                try:
                    # Add a check to verify image is visible on the page
                    image_element = WebDriverWait(self.driver, 10).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, ai_config.get("image_preview_selector", "img")))
                    )
                    logger.info("Image preview is visible on page")
                except Exception as e:
                    logger.error(f"Image doesn't appear to be on page: {str(e)}")

                # 4. Use a more reliable method for text input
                input_field = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, ai_config["input_selector"]))
                )
                prompt = "Describe this image in 60 characters or fewer (short but give detail as I am trying to get proper info from it), if there is no image and I finish it with 'complete' you can give me a description that is good for a complete whatsapp message about it, if it a image describe what it is, give it back. If I ask for translation never put emoji or any other invalid characters:"

                # Click to focus
                input_field.click()
                input_field.clear()

                # Back to reliable but slower method
                for char in prompt:
                    input_field.send_keys(char)
                    time.sleep(0.000001)

                # Make sure to end with Enter
                input_field.send_keys(Keys.ENTER)
                logger.info(f"Sent image prompt to {tab_name}: {prompt}")
            
            wait_time = float(self.response_wait_time_image if message_type == "image" else self.response_wait_time_text)

            time.sleep(wait_time)
            
            response_element = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ai_config["response_selector"]))
            )
            
            # Extract and clean response to remove citation numbers
            if response_element:
                raw_response = response_element.text
                
                # Clean the response using regex to remove citation numbers and source attributions
                import re
                # Remove citation numbers like [1], [2], etc.
                response = re.sub(r'\[\d+\]', '', raw_response)
                # Remove other potential artifacts like source attribution texts
                response = re.sub(r'Source: .*?$', '', response, flags=re.MULTILINE)
                # Remove any numbered footnotes like ¹, ², ³
                response = re.sub(r'[¹²³⁴⁵⁶⁷⁸⁹⁰]', '', response)
                # Final cleanup of any double spaces and trim
                response = re.sub(r'\s+', ' ', response).strip()
            else:
                response = "No response"
                
            logger.info(f"Received response from {tab_name}: {response[:50]}...")
            return response
            
        except Exception as e:
            logger.error(f"Error interacting with {tab_name}: {e}")
            return None

    def refresh_ai_page(self, group_name):
        ai_config = self.config["ai_mappings"].get(group_name)
        if not ai_config:
            logger.warning(f"No AI mapping found for group: {group_name}")
            return None
        
        tab_name = ai_config["tab_name"]
        window_handle = self.tabs.get(tab_name)
        
        if not window_handle:
            logger.error(f"Tab {tab_name} not found")
            return None
        
        self.driver.switch_to.window(window_handle)
        self.driver.refresh()
        time.sleep(0.5)
        logger.info(f"Refreshed AI tab: {tab_name}")

    def send_to_whatsapp(self, message):
        try:
            self.driver.switch_to.window(self.tabs["WhatsApp"])
            # Ensure we're in the correct chat
            if self.current_chat:
                self.select_chat(self.current_chat)
            pyperclip.copy(message)
            input_field = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div[aria-label='Type a message']"))
            )
            input_field.click()
            actions = ActionChains(self.driver)
            actions.key_down(Keys.COMMAND).send_keys('v').key_up(Keys.COMMAND).perform()
            input_field.send_keys(Keys.ENTER)
            logger.info(f"Sent response to WhatsApp: {message[:50]}...")
            # Cache the sent response
            content_key = self.hash_content(message)
            self.cache_content(content_key, self.current_chat)
            logger.info(f"Cached sent response with hash: {content_key}")
        except Exception as e:
            logger.error(f"Error sending to WhatsApp: {e}")

    def cleanup_temp_files(self):
        """Clean up temporary image files older than 1 hour"""
        try:
            current_time = time.time()
            for filename in os.listdir(self.image_dir):
                file_path = os.path.join(self.image_dir, filename)
                if os.path.isfile(file_path):
                    file_age = current_time - os.path.getmtime(file_path)
                    if file_age > 3600:
                        os.remove(file_path)
                        logger.info(f"Deleted old temporary file: {filename}")
        except Exception as e:
            logger.error(f"Error cleaning up temp files: {e}")

    def run(self):
        try:
            self.setup_browser()
            logger.info("Starting message monitoring loop")
            cleanup_counter = 0
            
            while True:
                group_name, message, message_type = self.get_whatsapp_messages()
                if group_name and (message or message_type == "image"):
                    if message_type == "text":
                        logger.info(f"New text message in {group_name}: {message[:50]}...")
                    else:
                        logger.info(f"New image message in {group_name}: {message}")
                    
                    response = self.send_to_ai(group_name, message, message_type)

                    if response:
                        self.refresh_ai_page(group_name) 
                        self.send_to_whatsapp(response)
                
                cleanup_counter += 1
                if cleanup_counter >= 120:
                    self.cleanup_temp_files()
                    cleanup_counter = 0
                    
                time.sleep(self.loop_interval_delay)

        except KeyboardInterrupt:
            logger.info("Shutting down...")
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
        finally:
            self.cleanup()

    def cleanup(self):
        if self.driver:
            self.driver.quit()
        logger.info("Browser closed")


if __name__ == "__main__":
    automation = WhatsAppAIAutomation()
    automation.run()