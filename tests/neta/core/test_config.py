"""Tests for the configuration module."""

import os
import json
import tempfile
import pytest
from src.neta.core.config import Config


class TestConfig:
    """Test Config class."""

    @pytest.fixture
    def temp_config_file(self):
        """Create a temporary config file for testing."""
        fd, path = tempfile.mkstemp(suffix='.json')
        os.close(fd)

        # Write test configuration
        config_data = {
            "ai_mappings": {
                "Test Chat": {
                    "url": "https://test.ai",
                    "tab_name": "Test AI",
                }
            },
            "whatsapp_url": "https://web.whatsapp.com/"
        }

        with open(path, 'w') as f:
            json.dump(config_data, f)

        yield path
        os.unlink(path)

    def test_load_config(self, temp_config_file):
        """Test loading configuration from file."""
        config = Config(temp_config_file)
        assert config.config is not None
        assert "ai_mappings" in config.config
        assert "whatsapp_url" in config.config

    def test_get_ai_config(self, temp_config_file):
        """Test retrieving AI configuration for a specific group."""
        config = Config(temp_config_file)

        # Existing chat
        ai_config = config.get_ai_config("Test Chat")
        assert ai_config is not None
        assert ai_config["url"] == "https://test.ai"
        assert ai_config["tab_name"] == "Test AI"

        # Non-existent chat
        assert config.get_ai_config("Nonexistent Chat") is None

    def test_get_whatsapp_url(self, temp_config_file):
        """Test retrieving WhatsApp URL."""
        config = Config(temp_config_file)
        assert config.get_whatsapp_url() == "https://web.whatsapp.com/"

    def test_get_ai_mappings(self, temp_config_file):
        """Test retrieving all AI mappings."""
        config = Config(temp_config_file)
        mappings = config.get_ai_mappings()
        assert len(mappings) == 1
        assert "Test Chat" in mappings

    def test_load_config_file_not_found(self):
        """Test FileNotFoundError is raised for non-existent config file."""
        with pytest.raises(FileNotFoundError):
            Config("/nonexistent/path/config.json")
