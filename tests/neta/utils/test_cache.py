"""Tests for the cache module."""

import os
import json
import tempfile
import pytest
from src.neta.utils.cache import MessageCache


class TestMessageCache:
    """Test MessageCache class."""
    
    @pytest.fixture
    def temp_cache_file(self):
        """Create a temporary cache file for testing."""
        fd, path = tempfile.mkstemp(suffix='.json')
        os.close(fd)
        yield path
        os.unlink(path)
    
    def test_init_creates_cache_file(self, temp_cache_file):
        """Test that initializing creates an empty cache file if it doesn't exist."""
        # Remove the file to test creation
        os.unlink(temp_cache_file)
        
        # Initialize cache
        cache = MessageCache(temp_cache_file)
        
        # Check that file was created
        assert os.path.exists(temp_cache_file)
        
        # Check that file contains empty dict
        with open(temp_cache_file, 'r') as f:
            assert json.load(f) == {}
    
    def test_hash_content(self, temp_cache_file):
        """Test content hashing."""
        cache = MessageCache(temp_cache_file)
        
        # Hash should be the same for equivalent content
        hash1 = cache.hash_content("test content")
        hash2 = cache.hash_content("test content")
        assert hash1 == hash2
        
        # Hash should be different for different content
        hash3 = cache.hash_content("different content")
        assert hash1 != hash3
        
        # Hash should normalize whitespace and case
        hash4 = cache.hash_content("  TEST CONTENT  ")
        assert hash1 == hash4
    
    def test_cache_operations(self, temp_cache_file):
        """Test caching operations."""
        cache = MessageCache(temp_cache_file)
        
        # Initially content should not be cached
        assert not cache.is_cached("test content", "group1")
        
        # After caching, it should be cached
        cache.cache_content("test content", "group1")
        assert cache.is_cached("test content", "group1")
        
        # Different group should not be cached
        assert not cache.is_cached("test content", "group2")
        
        # Same content should persist after reloading cache
        new_cache = MessageCache(temp_cache_file)
        assert new_cache.is_cached("test content", "group1")
        assert not new_cache.is_cached("test content", "group2")