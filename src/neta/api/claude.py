import base64
import logging
import os
from typing import Any, Dict, Optional

from anthropic import Anthropic

from .base import APIClient

logger = logging.getLogger(__name__)


class ClaudeClient(APIClient):
    """
    Claude API client implementation with persistent system prompt.
    """

    def __init__(self, api_key: str, **kwargs):
        self.api_key = api_key
        self.max_tokens = kwargs.get("max_tokens", 700)
        self.temperature = kwargs.get("temperature", 0.7)
        self.max_history_messages = kwargs.get("max_history_messages", 10)

        # Regular conversation history without system prompt
        self.conversation_history: list[dict[str, Any]] = []

        self.client = Anthropic(api_key=self.api_key)
        logger.info("Initialized Claude API client")

    def send_text_message(self, message: str, ai_config: Dict[str, Any]) -> tuple[Optional[str], Optional[str]]:
        """
        Send text message to Claude API.
        """
        try:
            model = ai_config.get("api_model", os.getenv("CLAUDE_MODEL", "claude-3-opus-20240229"))
            system_prompt = ai_config.get("system_prompt", "")

            # Add user message to history
            self.conversation_history.append({"role": "user", "content": message})

            # Create full messages list with system prompt + conversation history
            full_messages = []

            # Add system message if it exists
            if system_prompt:
                full_messages.append({"role": "system", "content": system_prompt})

            # Add conversation history
            full_messages.extend(self.conversation_history)

            response = self.client.messages.create(
                model=model,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                messages=full_messages,  # Use the combined messages
            )

            response_text = response.content[0].text
            self.conversation_history.append({"role": "assistant", "content": response_text})

            # Only trim the conversation history, not the system prompt
            if len(self.conversation_history) > self.max_history_messages:
                self.conversation_history = self.conversation_history[-self.max_history_messages :]

            logger.info(f"Received response from Claude API: {response_text[:50]}...")
            return response_text, None

        except Exception as e:
            logger.error(f"Error sending text to Claude API: {e}")
            return None, None

    def send_image(self, image_path: str, ai_config: Dict[str, Any]) -> tuple[Optional[str], Optional[str]]:
        """
        Send image to Claude API using vision capabilities.
        """
        try:
            content_type = "image/jpeg"
            model = ai_config.get("api_model", os.getenv("CLAUDE_MODEL", "claude-3-opus-20240229"))
            system_prompt = ai_config.get("system_prompt", "")
            prompt = ai_config.get("image_prompt_template", "Describe this image briefly.")

            with open(image_path, "rb") as image_file:
                image_data = image_file.read()
                base64_image = base64.b64encode(image_data).decode("utf-8")

            # Add user message (image prompt) to history
            self.conversation_history.append({"role": "user", "content": prompt})

            # Create full messages list with system prompt + conversation history
            full_messages = []

            # Add system message if it exists
            if system_prompt:
                full_messages.append({"role": "system", "content": system_prompt})

            # Create user message with image
            user_message = {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": content_type,
                            "data": base64_image,
                        },
                    },
                    {"type": "text", "text": prompt},
                ],
            }

            # Replace the last user message in full_messages with the image message
            # (we've already added the text-only version to conversation_history)
            full_messages.extend(self.conversation_history[:-1])  # All but last message
            full_messages.append(user_message)  # Add image message

            response = self.client.messages.create(
                model=model,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                messages=full_messages,
            )

            response_text = response.content[0].text
            self.conversation_history.append({"role": "assistant", "content": response_text})

            # Only trim the conversation history, not the system prompt
            if len(self.conversation_history) > self.max_history_messages:
                self.conversation_history = self.conversation_history[-self.max_history_messages :]

            logger.info(f"Received image description from Claude API: {response_text}")
            return response_text, None

        except Exception as e:
            logger.error(f"Error sending image to Claude API: {e}")
            return None, None
