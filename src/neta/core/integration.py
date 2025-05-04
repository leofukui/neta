import logging
import os
import time
from typing import Any, Dict, Optional, Tuple

from ..api.claude import ClaudeClient
from ..api.gemini import GeminiClient
from ..api.grok import GrokClient
from ..api.openai import OpenAIClient
from ..api.perplexity import PerplexityClient

logger = logging.getLogger(__name__)


class IntegrationManager:
    """
    Manages API integrations for different AI platforms.
    """

    def __init__(self, config, driver=None):
        """
        Initialize integration manager.

        Args:
            config: Configuration instance
            driver: WebDriver instance (optional)
        """
        self.config = config
        self.driver = driver
        self.clients = {}
        self._initialize_clients()

    def _initialize_clients(self):
        """
        Initialize API clients for all platforms with API keys set.
        """
        # Initialize Claude client if API key is available
        claude_api_key = os.getenv("CLAUDE_API_KEY")
        if claude_api_key:
            self.clients["claude"] = ClaudeClient(claude_api_key)
            logger.info("Initialized Claude API client")

        # Initialize OpenAI client if API key is available
        openai_api_key = os.getenv("OPENAI_API_KEY")
        if openai_api_key:
            self.clients["openai"] = OpenAIClient(openai_api_key)
            logger.info("Initialized OpenAI API client")

        # Initialize Gemini client if API key is available
        gemini_api_key = os.getenv("GEMINI_API_KEY")
        if gemini_api_key:
            self.clients["gemini"] = GeminiClient(gemini_api_key)
            logger.info("Initialized Gemini API client")

        # Initialize Perplexity client if API key is available
        perplexity_api_key = os.getenv("PERPLEXITY_API_KEY")
        if perplexity_api_key:
            self.clients["perplexity"] = PerplexityClient(perplexity_api_key)
            logger.info("Initialized Perplexity API client")

        # Initialize Grok client if API key is available
        grok_api_key = os.getenv("GROK_API_KEY")
        if grok_api_key:
            self.clients["grok"] = GrokClient(grok_api_key)
            logger.info("Initialized Grok API client")

    def process_message(
        self, group_name: str, message: Any, message_type: str
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Process a message using the appropriate API client.

        Args:
            group_name: Name of the WhatsApp group
            message: Message content (text or image path)
            message_type: Type of message ('text' or 'image')

        Returns:
            Tuple of (text_response, image_path) where image_path may be None if no image is generated
        """
        # Get AI configuration for this group
        ai_config = self.config.get_ai_config(group_name)
        if not ai_config:
            logger.warning(f"No AI mapping found for group: {group_name}")
            return None, None

        # Get platform name from config
        platform_name = ai_config.get("api_platform", "").lower()
        if not platform_name:
            logger.error("No API platform specified in config")
            return None, None

        # Check if we have a client for this platform
        if platform_name not in self.clients:
            logger.error(f"No API client initialized for platform: {platform_name}")
            return None, None

        # Get the appropriate client
        client = self.clients[platform_name]

        # Process based on message type
        if message_type == "text":
            logger.info(f"Processing text message for {group_name} using {platform_name} API")
            return client.send_text_message(message, ai_config)
        else:  # message_type == "image"
            logger.info(f"Processing image message for {group_name} using {platform_name} API")
            return client.send_image(message, ai_config)
