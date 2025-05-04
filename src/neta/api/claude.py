import base64
import logging
import os
from typing import Any, Dict, Optional

from anthropic import Anthropic

from .base import APIClient

logger = logging.getLogger(__name__)


class ClaudeClient(APIClient):
    """
    Claude API client implementation.
    """

    def __init__(self, api_key: str, **kwargs):
        self.api_key = api_key
        self.max_tokens = kwargs.get("max_tokens", 700)
        self.temperature = kwargs.get("temperature", 0.7)
        self.max_history_messages = kwargs.get("max_history_messages", 10)

        self.conversation_history: list[dict[str, Any]] = []

        self.client = Anthropic(api_key=self.api_key)
        logger.info("Initialized Claude API client")

    def send_text_message(self, message: str, ai_config: Dict[str, Any]) -> tuple[Optional[str], Optional[str]]:
        """
        Send text message to Claude API.
        """
        try:
            model = ai_config.get("api_model", os.getenv("CLAUDE_MODEL", "claude-3-opus-20240229"))

            prompt_template = ai_config.get("text_prompt_template")
            prompt = prompt_template.format(message=message) if prompt_template else message

            self.conversation_history.append({"role": "user", "content": prompt})

            response = self.client.messages.create(
                model=model,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                messages=self.conversation_history,
            )

            response_text = response.content[0].text
            self.conversation_history.append({"role": "assistant", "content": response_text})

            if len(self.conversation_history) > self.max_history_messages:
                self.conversation_history = self.conversation_history[-self.max_history_messages :]

            logger.info(f"Received response from Claude API: {response_text[:50]}...")
            return response_text, None

        except Exception as e:
            logger.error(f"Error sending text to Claude API: {e}")
            return None, None

    def send_image(self, image_path: str, ai_config: Dict[str, Any]) -> tuple[Optional[str], Optional[str]]:
        """
        Send image to Claude API using vision capabilities, with context simulated via text.
        """
        try:
            content_type = "image/jpeg"

            model = ai_config.get("api_model", os.getenv("CLAUDE_MODEL", "claude-3-opus-20240229"))

            with open(image_path, "rb") as image_file:
                image_data = image_file.read()
                base64_image = base64.b64encode(image_data).decode("utf-8")

            prompt = ai_config.get("image_prompt_template") or "Describe this image briefly."

            chat_context = ""
            for msg in self.conversation_history[-self.max_history_messages :]:
                role = msg["role"]
                content = msg["content"]
                chat_context += f"{role.upper()}: {content}\n"

            full_prompt = f"{chat_context.strip()}\nUSER: {prompt}"

            self.conversation_history.append({"role": "user", "content": prompt})

            response = self.client.messages.create(
                model=model,
                max_tokens=60,
                temperature=self.temperature,
                messages=[
                    {
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
                            {"type": "text", "text": full_prompt},
                        ],
                    }
                ],
            )

            response_text = response.content[0].text
            self.conversation_history.append({"role": "assistant", "content": response_text})

            if len(self.conversation_history) > self.max_history_messages:
                self.conversation_history = self.conversation_history[-self.max_history_messages :]

            logger.info(f"Received image description from Claude API: {response_text}")
            return response_text, None

        except Exception as e:
            logger.error(f"Error sending image to Claude API: {e}")
            return None, None
