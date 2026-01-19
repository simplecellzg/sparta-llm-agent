"""
Tests for API utility functions
"""
import pytest
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestAPIKeyMasking:
    """Test API key masking functionality"""

    def test_mask_normal_length_key(self):
        """Should mask middle characters, showing first 5 and last 4"""
        key = "sk-LGxrZUW3xh6ULiH736B3Ee9dB29a4917822b5d78612bE12d"
        from api_utils import mask_api_key

        result = mask_api_key(key)

        # Should show first 5 chars
        assert result.startswith("sk-LG")
        # Should show last 4 chars
        assert result.endswith("E12d")
        # Should have asterisks in the middle
        assert "*" in result
        # Total length should match original
        assert len(result) == len(key)

    def test_mask_short_key(self):
        """Should return *** for keys shorter than 9 characters"""
        from api_utils import mask_api_key

        assert mask_api_key("short") == "***"
        assert mask_api_key("12345678") == "***"

    def test_mask_exactly_9_chars(self):
        """Should return *** for keys exactly 9 characters"""
        from api_utils import mask_api_key

        assert mask_api_key("123456789") == "***"

    def test_mask_10_chars(self):
        """Should mask 10 char key correctly (first 5 + 1 asterisk + last 4)"""
        from api_utils import mask_api_key

        result = mask_api_key("1234567890")

        assert result == "12345*7890"

    def test_mask_preserves_prefix(self):
        """Should preserve common API key prefixes"""
        from api_utils import mask_api_key

        # Anthropic key
        anthropic_key = "sk-ant-api03-abcdefghijklmnopqrstuvwxyz1234567890"
        result = mask_api_key(anthropic_key)
        assert result.startswith("sk-an")

        # OpenAI-style key
        openai_key = "sk-proj-abcdefghijklmnopqrstuvwxyz1234567890"
        result = mask_api_key(openai_key)
        assert result.startswith("sk-pr")
