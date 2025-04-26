import logging
import os
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

logger = logging.getLogger(__name__)


class BrowserManager:
    """
    Manage browser sessions for WhatsApp and AI platforms.
    """
    
    def __init__(self, image_dir=None):
        """
        Initialize browser manager.
        
        Args:
            image_dir: Directory for downloading images
        """
        self.driver = None
        self.tabs = {}
        self.whatsapp_window = None
        self.image_dir = image_dir
    
    def setup_browser(self, whatsapp_url, ai_mappings, login_wait_delay=60):
        """
        Initialize Chrome and open tabs for WhatsApp and AI platforms.
        
        Args:
            whatsapp_url: URL for WhatsApp Web
            ai_mappings: Dict of AI platform configurations
            login_wait_delay: Seconds to wait for manual login
            
        Raises:
            ValueError: If Chrome profile path is not set
        """
        chrome_options = self._configure_chrome_options()
        
        # Initialize Chrome driver
        self.driver = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()),
            options=chrome_options
        )
        
        # Make the browser less detectable
        self._apply_anti_detection()
        
        # Open WhatsApp
        self.driver.get(whatsapp_url)
        self.whatsapp_window = self.driver.current_window_handle
        self.tabs["WhatsApp"] = self.whatsapp_window
        logger.info("Opened WhatsApp Web tab")
        
        # Open AI platform tabs
        for group, ai_config in ai_mappings.items():
            self.driver.execute_script("window.open('');")
            new_window = self.driver.window_handles[-1]
            self.driver.switch_to.window(new_window)
            self.driver.get(ai_config["url"])
            self.tabs[ai_config["tab_name"]] = new_window
            logger.info(f"Opened tab for {ai_config['tab_name']}")
            
        # Allow time for manual login
        logger.info(f"Please log in to all platforms. Waiting for {login_wait_delay} seconds...")
        time.sleep(login_wait_delay)
    
    def _configure_chrome_options(self):
        """
        Configure Chrome options for automation.
        
        Returns:
            Configured Chrome options
            
        Raises:
            ValueError: If Chrome profile path is not set
        """
        chrome_options = Options()
        
        # Make automation less detectable
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option("useAutomationExtension", False)
        
        # Configure download directory if specified
        if self.image_dir:
            chrome_options.add_experimental_option(
                "prefs", {
                    "download.default_directory": os.path.abspath(self.image_dir),
                    "download.prompt_for_download": False,
                    "download.directory_upgrade": True,
                    "safebrowsing.enabled": True
                }
            )
        
        # Load Chrome profile path from environment
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
        
        return chrome_options
    
    def _apply_anti_detection(self):
        """Apply anti-detection measures to the browser."""
        if not self.driver:
            return
            
        # Inject JavaScript to mask automation
        self.driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": """
                Object.defineProperty(navigator, 'webdriver', { get: () => false });
                Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3] });
                Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
            """
        })
    
    def switch_to_tab(self, tab_name):
        """
        Switch to specified browser tab.
        
        Args:
            tab_name: Name of the tab to switch to
            
        Returns:
            Boolean indicating success
        """
        window_handle = self.tabs.get(tab_name)
        if not window_handle:
            logger.error(f"Tab {tab_name} not found")
            return False
            
        try:
            self.driver.switch_to.window(window_handle)
            return True
        except Exception as e:
            logger.error(f"Error switching to tab {tab_name}: {e}")
            return False
    
    def refresh_tab(self, tab_name):
        """
        Refresh specified browser tab.
        
        Args:
            tab_name: Name of the tab to refresh
            
        Returns:
            Boolean indicating success
        """
        if not self.switch_to_tab(tab_name):
            return False
            
        try:
            self.driver.refresh()
            time.sleep(0.5)
            logger.info(f"Refreshed tab: {tab_name}")
            return True
        except Exception as e:
            logger.error(f"Error refreshing tab {tab_name}: {e}")
            return False
    
    def close(self):
        """Close browser and clean up."""
        if self.driver:
            try:
                self.driver.quit()
                logger.info("Browser closed")
            except Exception as e:
                logger.error(f"Error closing browser: {e}")