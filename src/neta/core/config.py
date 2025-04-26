import json
import os
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()


class Config:
    """
    Configuration manager for NETA.
    """
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize configuration.
        
        Args:
            config_path: Path to configuration file (default: from environment or config.json)
        """
        self.config_path = config_path or os.getenv("CONFIG_PATH", "config.json")
        self.config = self.load_config()
        
        # Load delay configurations from environment variables
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
    
    def load_config(self) -> Dict[str, Any]:
        """
        Load configuration from JSON file.
        
        Returns:
            Dictionary with configuration settings
            
        Raises:
            FileNotFoundError: If config file doesn't exist
            json.JSONDecodeError: If config file is invalid JSON
        """
        try:
            # Check if file exists
            if not Path(self.config_path).exists():
                logger.error(f"Config file not found: {self.config_path}")
                raise FileNotFoundError(f"Config file not found: {self.config_path}")
                
            with open(self.config_path, "r") as f:
                config = json.load(f)
                logger.info(f"Loaded configuration from {self.config_path}")
                return config
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in config file: {e}")
            raise
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            raise
    
    def get_ai_config(self, group_name: str) -> Optional[Dict[str, Any]]:
        """
        Get AI configuration for a specific group.
        
        Args:
            group_name: Name of the WhatsApp group
            
        Returns:
            AI configuration dict or None if not found
        """
        return self.config.get("ai_mappings", {}).get(group_name)
    
    def get_whatsapp_url(self) -> str:
        """
        Get WhatsApp Web URL.
        
        Returns:
            WhatsApp Web URL
        """
        return self.config.get("whatsapp_url", "https://web.whatsapp.com/")
    
    def get_ai_mappings(self) -> Dict[str, Dict[str, Any]]:
        """
        Get all AI mappings.
        
        Returns:
            Dictionary of AI mappings
        """
        return self.config.get("ai_mappings", {})