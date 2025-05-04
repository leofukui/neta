import asyncio
import logging
import os
import time

from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException, StaleElementReferenceException, TimeoutException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

logger = logging.getLogger(__name__)


class BrowserManager:
    """
    Manage browser sessions for WhatsApp and AI platforms with enhanced tab verification.
    """

    def __init__(self, image_dir=None):
        """
        Initialize browser manager.

        Args:
            image_dir: Directory for downloading images
        """
        self.driver = None
        self.tabs = {}
        self.tab_titles = {}  # Track expected titles for verification
        self.tab_urls = {}  # Track expected URLs for verification
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
        self.driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
        self._apply_anti_detection()

        # Open WhatsApp tab
        self.driver.get(whatsapp_url)
        self.whatsapp_window = self.driver.current_window_handle
        self.tabs["WhatsApp"] = self.whatsapp_window
        self.tab_urls["WhatsApp"] = whatsapp_url
        self.tab_titles["WhatsApp"] = "WhatsApp"
        logger.info("Opened WhatsApp Web tab")

        # Open AI platform tabs
        for group, ai_config in ai_mappings.items():
            self.driver.execute_script("window.open('');")
            new_window = self.driver.window_handles[-1]
            self.driver.switch_to.window(new_window)
            self.driver.get(ai_config["url"])

            tab_name = ai_config["tab_name"]
            self.tabs[tab_name] = new_window
            self.tab_urls[tab_name] = ai_config["url"]
            self.tab_titles[tab_name] = tab_name  # Default to tab_name, will be updated after login

            logger.info(f"Opened tab for {tab_name}")

        # Switch back to WhatsApp tab
        self.switch_to_tab("WhatsApp")

        logger.info(f"Please log in to all platforms. Waiting for {login_wait_delay} seconds...")
        time.sleep(login_wait_delay)

        # After login delay, capture actual tab titles for better verification
        self._update_tab_information()

    def _update_tab_information(self):
        """Update tab titles and URLs after login to ensure accurate verification."""
        current_handle = self.driver.current_window_handle

        for tab_name, handle in self.tabs.items():
            try:
                self.driver.switch_to.window(handle)
                time.sleep(0.5)  # Brief pause to ensure page is loaded

                # Update title and URL information
                self.tab_titles[tab_name] = self.driver.title
                self.tab_urls[tab_name] = self.driver.current_url

                logger.debug(
                    f"Updated tab info for {tab_name}: Title={self.tab_titles[tab_name]}, URL={self.tab_urls[tab_name]}"
                )
            except Exception as e:
                logger.error(f"Error updating tab information for {tab_name}: {e}")

        # Return to original tab
        self.driver.switch_to.window(current_handle)

    def _configure_chrome_options(self):
        """
        Configure Chrome options for automation.

        Returns:
            Configured Chrome options

        Raises:
            ValueError: If Chrome profile path is not set
        """
        chrome_options = Options()
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option("useAutomationExtension", False)

        if self.image_dir:
            chrome_options.add_experimental_option(
                "prefs",
                {
                    "download.default_directory": os.path.abspath(self.image_dir),
                    "download.prompt_for_download": False,
                    "download.directory_upgrade": True,
                    "safebrowsing.enabled": True,
                },
            )

        chrome_profile_path = os.getenv("CHROME_PROFILE_PATH")
        if not chrome_profile_path:
            logger.error("CHROME_PROFILE_PATH not set in .env file. Please configure it.")
            raise ValueError("CHROME_PROFILE_PATH is required in .env file")

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
        self.driver.execute_cdp_cmd(
            "Page.addScriptToEvaluateOnNewDocument",
            {
                "source": """
                Object.defineProperty(navigator, 'webdriver', { get: () => false });
                Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3] });
                Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
            """
            },
        )

    def switch_to_tab(self, tab_name):
        """
        Switch to specified browser tab with robust validation.

        Args:
            tab_name: Name of the tab to switch to

        Returns:
            Boolean indicating success
        """
        max_attempts = 3

        for attempt in range(max_attempts):
            try:
                # First try the mapped window handle
                if tab_name in self.tabs:
                    window_handle = self.tabs[tab_name]
                    self.driver.switch_to.window(window_handle)

                    # Give page a moment to stabilize
                    time.sleep(0.5)
                else:
                    logger.warning(f"Tab '{tab_name}' not in tab map, attempting fallback...")
                    if not self._switch_to_tab_by_content(tab_name):
                        return False

                # Verify the tab is correct
                if self.verify_active_tab(tab_name):
                    return True

                # If verification failed but we have more attempts
                if attempt < max_attempts - 1:
                    logger.warning(
                        f"Tab verification failed for '{tab_name}', retrying... (attempt {attempt+1}/{max_attempts})"
                    )
                    # Try refreshing the page for next attempt
                    try:
                        self.driver.refresh()
                        time.sleep(1)  # Wait for refresh
                    except Exception as e:
                        logger.error(f"Error refreshing page: {e}")
                else:
                    logger.error(f"Failed to switch to tab '{tab_name}' after {max_attempts} attempts")
                    return False

            except Exception as e:
                logger.error(f"Error switching to tab '{tab_name}' on attempt {attempt+1}: {e}")
                if attempt < max_attempts - 1:
                    time.sleep(1)
                else:
                    return False

        return False

    def _switch_to_tab_by_content(self, tab_name):
        """
        Fallback method to switch to a tab by looking at tab content.

        Args:
            tab_name: Name of the tab to find

        Returns:
            Boolean indicating success
        """
        title_keywords = {
            "WhatsApp": ["WhatsApp", "WhatsApp Web", "WhatsApp Business"],
            # Add mappings for other platforms as needed
        }

        url_keywords = {
            "WhatsApp": ["web.whatsapp.com"],
            # Add mappings for other platforms as needed
        }

        try:
            # Get current window handles
            window_handles = self.driver.window_handles

            # Look through all tabs
            for handle in window_handles:
                self.driver.switch_to.window(handle)
                time.sleep(0.5)  # Give page time to load

                current_title = self.driver.title
                current_url = self.driver.current_url

                # Check if this tab matches by title
                keywords = title_keywords.get(tab_name, [tab_name])
                for keyword in keywords:
                    if keyword in current_title:
                        # Update our tab mappings
                        self.tabs[tab_name] = handle
                        self.tab_titles[tab_name] = current_title
                        self.tab_urls[tab_name] = current_url
                        logger.info(f"Found tab '{tab_name}' by title: {current_title}")
                        return True

                # Check if this tab matches by URL
                url_keys = url_keywords.get(tab_name, [])
                for url_key in url_keys:
                    if url_key in current_url:
                        # Update our tab mappings
                        self.tabs[tab_name] = handle
                        self.tab_titles[tab_name] = current_title
                        self.tab_urls[tab_name] = current_url
                        logger.info(f"Found tab '{tab_name}' by URL: {current_url}")
                        return True

            logger.error(f"Could not find tab '{tab_name}' by content")
            return False

        except Exception as e:
            logger.error(f"Error in _switch_to_tab_by_content for '{tab_name}': {e}")
            return False

    def verify_active_tab(self, tab_name):
        """
        Verify that we're on the correct tab after switching.

        Args:
            tab_name: Name of the tab to verify

        Returns:
            Boolean indicating if verification passed
        """
        try:
            current_url = self.driver.current_url
            current_title = self.driver.title

            # Special handling for WhatsApp
            if tab_name == "WhatsApp":
                try:
                    # Check for WhatsApp-specific elements
                    selectors = [
                        "div[data-testid='chat-list']",
                        "div[aria-label='Chat list']",
                        "div[data-testid='app']",
                        "header[data-testid='chat-list-header']",
                    ]
                    for selector in selectors:
                        try:
                            WebDriverWait(self.driver, 5).until(
                                EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                            )
                            if "web.whatsapp.com" in current_url:
                                logger.debug(f"WhatsApp tab verified by {selector} and URL")
                                return True
                            break
                        except TimeoutException:
                            continue

                    # Check for QR code page
                    qr_code = self.driver.find_elements(By.CSS_SELECTOR, "div[data-testid='qrcode']")
                    if qr_code:
                        logger.error("WhatsApp tab is on QR code login page")
                        return False

                    logger.warning(f"WhatsApp tab verification failed. URL: {current_url}, Title: {current_title}")
                    return False

                except TimeoutException:
                    logger.error("WhatsApp tab verification failed - no UI elements found")
                    return False

            # General verification for other tabs
            expected_title = self.tab_titles.get(tab_name)
            expected_url = self.tab_urls.get(tab_name)

            # URL verification
            if expected_url and expected_url not in current_url:
                logger.warning(
                    f"Tab URL verification failed for {tab_name}. Expected URL to contain: {expected_url}, Got: {current_url}"
                )
                return False

            # Title verification
            if expected_title:
                if expected_title in current_title or tab_name in current_title:
                    logger.debug(f"Tab verification passed for {tab_name}")
                    return True
                else:
                    logger.warning(
                        f"Tab title verification failed for {tab_name}. Expected: {expected_title}, Got: {current_title}"
                    )
                    return False

            logger.debug(f"Tab verification passed for {tab_name} by URL only")
            return True

        except Exception as e:
            logger.error(f"Error verifying tab {tab_name}: {e}")
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
            time.sleep(1.5)  # Longer wait to ensure page loads

            # Verify we're still on the right tab after refresh
            if not self.verify_active_tab(tab_name):
                logger.error(f"Tab verification failed after refreshing {tab_name}")
                return False

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


class TabLock:
    """
    An enhanced async lock mechanism for browser tabs with timeout and ownership tracking.
    """

    def __init__(self):
        self.tab_locks = {}
        self.lock_owners = {}  # Track which task owns each lock
        self.lock_times = {}  # Track when locks were acquired

    def get_lock(self, tab_name):
        """Get the lock for a specific tab, creating it if it doesn't exist."""
        if tab_name not in self.tab_locks:
            self.tab_locks[tab_name] = asyncio.Lock()
        return self.tab_locks[tab_name]

    async def acquire(self, tab_name, timeout=30):
        """
        Acquire the lock for a specific tab with a timeout.

        Args:
            tab_name: Name of the tab to lock
            timeout: Maximum seconds to wait for lock (default: 30)

        Returns:
            True if lock acquired successfully, False if timed out

        Raises:
            asyncio.TimeoutError: If lock cannot be acquired within timeout period
        """
        lock = self.get_lock(tab_name)

        # Check for potential deadlocks
        if tab_name in self.lock_times:
            lock_duration = time.time() - self.lock_times.get(tab_name, 0)
            if lock_duration > 60:
                owner = self.lock_owners.get(tab_name, "unknown")
                logger.warning(f"Force releasing lock for {tab_name} held by {owner} for {lock_duration:.2f}s")
                self.release(tab_name)

        try:
            # Wait for lock with timeout
            await asyncio.wait_for(lock.acquire(), timeout=timeout)
            current_task = asyncio.current_task()
            task_id = f"Task-{id(current_task)}"
            self.lock_owners[tab_name] = task_id
            self.lock_times[tab_name] = time.time()
            logger.debug(f"Acquired lock for tab: {tab_name} by {task_id} at {time.strftime('%Y-%m-%d %H:%M:%S')}")
            return True
        except asyncio.TimeoutError:
            logger.error(
                f"Timeout acquiring lock for {tab_name} after {timeout}s. Current owner: {self.get_owner(tab_name)}"
            )
            return False

    def release(self, tab_name):
        """
        Release the lock for a specific tab and clean up tracking data.
        """
        if tab_name in self.tab_locks:
            try:
                if self.tab_locks[tab_name].locked():
                    # Log duration held if we have timing data
                    if tab_name in self.lock_times:
                        duration = time.time() - self.lock_times[tab_name]
                        owner = self.lock_owners.get(tab_name, "unknown")
                        logger.debug(f"Lock for {tab_name} held by {owner} for {duration:.2f}s")

                    # Release the lock
                    self.tab_locks[tab_name].release()
                    logger.debug(f"Released lock for tab: {tab_name}")

                    # Clean up tracking data
                    self.lock_owners.pop(tab_name, None)
                    self.lock_times.pop(tab_name, None)
                else:
                    # Lock was not acquired or already released
                    logger.warning(f"Attempted to release an unlocked tab: {tab_name}")
            except RuntimeError as e:
                # Handle potential errors during release
                logger.warning(f"Error releasing lock for {tab_name}: {e}")

    def is_locked(self, tab_name):
        """Check if a tab is currently locked."""
        return tab_name in self.tab_locks and self.tab_locks[tab_name].locked()

    def get_owner(self, tab_name):
        """Get the ID of the task that owns the lock."""
        return self.lock_owners.get(tab_name, None)

    def recover_whatsapp_tab(self):
        """
        Attempt to recover the WhatsApp tab if it's in a bad state.

        Returns:
            Boolean indicating success
        """
        try:
            logger.info("Attempting to recover WhatsApp tab")

            # Switch to WhatsApp tab
            if not self.switch_to_tab("WhatsApp"):
                logger.error("Failed to switch to WhatsApp tab for recovery")
                return False

            # Refresh the tab
            self.driver.refresh()
            time.sleep(3)  # Wait for page to reload

            # Check if we're on the QR code page
            try:
                WebDriverWait(self.driver, 5).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "div[data-testid='qrcode']"))
                )
                logger.error("WhatsApp requires re-login. Please scan QR code.")
                return False
            except TimeoutException:
                pass

            # Verify WhatsApp UI is loaded
            try:
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "div[data-testid='chat-list']"))
                )
                logger.info("WhatsApp tab recovered successfully")
                return True
            except TimeoutException:
                logger.error("Failed to recover WhatsApp tab - UI elements not found")
                return False

        except Exception as e:
            logger.error(f"Error recovering WhatsApp tab: {e}")
            return False
