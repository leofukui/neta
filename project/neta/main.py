import json
import logging
import time
import os
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException, StaleElementReferenceException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
import pyperclip

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
    def __init__(self, config_path=None):
        self.config = self.load_config(config_path or os.getenv("CONFIG_PATH", "config.json"))
        self.driver = None
        self.tabs = {}
        self.whatsapp_window = None
        self.last_message = None

    def load_config(self, config_path):
        try:
            with open(config_path, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            raise

    def setup_browser(self):
        """Initialize Chrome and open tabs in a single window with persistent profile."""
        chrome_options = Options()
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option("useAutomationExtension", False)
        
        # Load Chrome profile path from .env
        chrome_profile_path = os.getenv("CHROME_PROFILE_PATH")
        if not chrome_profile_path:
            logger.error("CHROME_PROFILE_PATH not set in .env file. Please configure it.")
            raise ValueError("CHROME_PROFILE_PATH is required in .env file")
        
        # Check and create Chrome profile directory if it doesn't exist
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
        logger.info("Please log in to all platforms. Waiting for 60 seconds...")
        time.sleep(3)

    def get_whatsapp_messages(self):
        try:
            self.driver.switch_to.window(self.tabs["WhatsApp"])
            
            # Wait for the chat list to load
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div[role='listitem']"))
            )
            
            # Get all chat list items (conversations)
            chat_list = self.driver.find_elements(By.CSS_SELECTOR, "div[role='listitem']")
            if not chat_list:
                logger.info("No chats found in the chat list.")
                return None, None

            # Click on the first chat (most recent) to open it
            latest_chat = chat_list[0]
            try:
                latest_chat.click()
                logger.info("Clicked on the latest chat.")
            except StaleElementReferenceException:
                logger.warning("Stale element reference for chat list. Retrying...")
                chat_list = self.driver.find_elements(By.CSS_SELECTOR, "div[role='listitem']")
                if chat_list:
                    chat_list[0].click()
                    logger.info("Clicked on the latest chat after retry.")
                else:
                    logger.error("No chats available after retry.")
                    return None, None

            # Wait for the chat to load and get the group/chat name
            try:
                group_element = WebDriverWait(self.driver, 5).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "#main > header div[role='button'] span:not([title])"))
                )
                group_name = group_element.text if group_element else "Unknown"
            except TimeoutException:
                logger.warning("Could not find group/chat name.")
                group_name = "Unknown"

            # Wait for messages to load
            WebDriverWait(self.driver, 5).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div.message-in"))
            )

            # Get all incoming messages
            message_elements = self.driver.find_elements(By.CSS_SELECTOR, "div.message-in span.selectable-text")
            if not message_elements:
                logger.info("No new messages found in the selected chat.")
                return None, None

            # Get the latest message
            latest_message = message_elements[-1].text
            if not latest_message:
                logger.info("Latest message is empty.")
                return None, None

            # Check if the message is new
            if latest_message != self.last_message:
                self.last_message = latest_message
                logger.info(f"New message detected in {group_name}: {latest_message[:50]}...")
                return group_name, latest_message
            else:
                logger.debug("No new messages (same as last message).")
                return None, None
        except Exception as e:
            logger.error(f"Error fetching WhatsApp messages: {e}")
            return None, None

    def send_to_ai(self, group_name, message):
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
            prompt = f"Respond in 350 characters or fewer: {message}"
            input_field = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ai_config["input_selector"]))
            )
            input_field.clear()
            for char in prompt:  # Simulate typing
                input_field.send_keys(char)
                time.sleep(0.01)
            input_field.send_keys(Keys.ENTER)
            logger.info(f"Sent message to {tab_name}: {prompt}")
            time.sleep(5)  # Wait for response
            response_element = self.driver.find_element(By.CSS_SELECTOR, ai_config["response_selector"])
            response = response_element.text if response_element else "No response"
            logger.info(f"Received response from {tab_name}: {response[:50]}...")
            return response
        except Exception as e:
            logger.error(f"Error interacting with {tab_name}: {e}")
            return None

    def send_to_whatsapp(self, message):
        try:
            self.driver.switch_to.window(self.tabs["WhatsApp"])
            pyperclip.copy(message)
            input_field = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div[aria-label='Type a message']"))
            )
            input_field.click()
            input_field.send_keys(Keys.COMMAND + "v")
            input_field.send_keys(Keys.ENTER)
            logger.info(f"Sent response to WhatsApp: {message[:50]}...")
        except Exception as e:
            logger.error(f"Error sending to WhatsApp: {e}")

    def run(self):
        try:
            self.setup_browser()
            logger.info("Starting message monitoring loop")
            while True:
                group_name, message = self.get_whatsapp_messages()
                if group_name and message:
                    logger.info(f"New message in {group_name}: {message[:50]}...")
                    response = self.send_to_ai(group_name, message)
                    if response:
                        self.send_to_whatsapp(response)
                time.sleep(30)

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
