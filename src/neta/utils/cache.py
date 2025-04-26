import json
import logging
import os
import time
import hashlib
from pathlib import Path

logger = logging.getLogger(__name__)


class MessageCache:
    """
    Cache system for tracking processed messages to avoid duplicates.
    """

    def __init__(self, cache_file=".cache.json"):
        """
        Initialize message cache.

        Args:
            cache_file: Path to cache file (default: .cache.json)
        """
        self.cache_file = cache_file

        # Ensure cache file directory exists
        cache_dir = Path(cache_file).parent
        if cache_dir != Path(".") and not cache_dir.exists():
            os.makedirs(cache_dir, exist_ok=True)
            logger.info(f"Created cache directory: {cache_dir}")

        self..cache.json = self.load_cache()

    def load_cache(self):
        """
        Load message cache from JSON file, create file if it doesn't exist.

        Returns:
            Dict containing cache data
        """
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
        """Save message cache to JSON file."""
        try:
            with open(self.cache_file, 'w') as f:
                json.dump(self..cache.json, f)
            logger.info(f"Saved cache to {self.cache_file} with {len(self..cache.json)} entries")
        except Exception as e:
            logger.error(f"Failed to save cache to {self.cache_file}: {e}")

    def hash_content(self, content):
        """
        Create a hash of the content (text or image src).

        Args:
            content: Content to hash

        Returns:
            MD5 hash of normalized content
        """
        # Normalize content by stripping whitespace and converting to lowercase
        normalized_content = content.strip().lower()
        return hashlib.md5(normalized_content.encode()).hexdigest()

    def is_cached(self, content, group_name):
        """
        Check if content has been processed before.

        Args:
            content: Content to check (text or image src)
            group_name: Name of the chat group

        Returns:
            Boolean indicating if content is cached
        """
        content_key = self.hash_content(content)
        cache_key = f"{group_name}:{content_key}"
        is_cached = cache_key in self..cache.json
        logger.debug(f"Checking cache for {cache_key}: {'cached' if is_cached else 'not cached'}")
        return is_cached

    def cache_content(self, content, group_name):
        """
        Add content to cache and save to file.

        Args:
            content: Content to cache (text or image src)
            group_name: Name of the chat group

        Returns:
            Cache key
        """
        content_key = self.hash_content(content)
        cache_key = f"{group_name}:{content_key}"
        self..cache.json[cache_key] = time.time()
        logger.debug(f"Caching content with key: {cache_key}")
        self.save_cache()
        return content_key
