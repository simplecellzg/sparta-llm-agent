import pytest
import os
from pathlib import Path
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import after adding to path
import app as app_module


class TestAPIKeyValidation:
    """Test API key validation and format"""

    def test_api_key_no_whitespace(self):
        """Test API key has no leading/trailing whitespace"""
        # This will test the actual loaded API_KEY from app.py
        from app import API_KEY

        assert API_KEY == API_KEY.strip(), "API key contains whitespace"
        assert len(API_KEY) > 0, "API key is empty"

    def test_api_key_format(self):
        """Test API key has correct format (starts with sk-)"""
        from app import API_KEY

        assert API_KEY.startswith('sk-'), f"API key should start with 'sk-', got: {API_KEY[:10]}..."
        assert len(API_KEY) >= 20, f"API key too short: {len(API_KEY)} characters"

    def test_api_url_format(self):
        """Test API URL has correct format"""
        from app import API_URL

        assert API_URL.startswith('https://'), f"API URL should use HTTPS, got: {API_URL}"
        assert not API_URL.endswith('/'), f"API URL should not end with slash, got: {API_URL}"

    def test_chat_completions_endpoint(self):
        """Test chat completions endpoint path is correct"""
        from app import API_URL

        endpoint = f"{API_URL}/chat/completions"
        assert "/v1/chat/completions" in endpoint, f"Missing /chat/completions path in: {endpoint}"


class TestAuthorizationHeader:
    """Test Authorization header construction"""

    def test_authorization_header_format(self):
        """Test Authorization header has correct Bearer format"""
        from app import API_KEY

        # Simulate how the header is constructed in app.py
        auth_header = f"Bearer {API_KEY}"

        assert auth_header.startswith("Bearer sk-"), \
            f"Authorization header format incorrect: {auth_header[:20]}..."
        assert " " in auth_header, "Missing space between Bearer and token"
        assert auth_header.count(" ") == 1, "Too many spaces in Authorization header"


class TestConfigValidation:
    """Test config validation function"""

    def test_validate_env_config_exists(self):
        """Test that validate_env_config function exists"""
        # This test will fail until we implement the function
        assert hasattr(app_module, 'validate_env_config'), \
            "validate_env_config function not found in app module"

    def test_validate_env_config_returns_bool(self):
        """Test that validate_env_config returns boolean"""
        # Reload to get fresh config
        result = app_module.validate_env_config()

        assert isinstance(result, bool), \
            f"validate_env_config should return bool, got {type(result)}"

    def test_validate_env_config_checks_api_key(self):
        """Test that validation catches empty API key"""
        # This will test the validation logic
        # We'll temporarily modify the config to test
        import app

        original_key = app.API_KEY
        try:
            # Test with invalid key
            app.API_KEY = "  "  # Whitespace only
            result = app.validate_env_config()
            assert result == False, "Should reject API key with only whitespace"

            app.API_KEY = ""  # Empty
            result = app.validate_env_config()
            assert result == False, "Should reject empty API key"
        finally:
            # Restore original
            app.API_KEY = original_key

    def test_validate_env_config_checks_https(self):
        """Test that validation requires HTTPS for API URL"""
        import app

        original_url = app.API_URL
        try:
            # Test with HTTP (insecure)
            app.API_URL = "http://api.example.com/v1"
            result = app.validate_env_config()
            assert result == False, "Should reject HTTP URLs (require HTTPS)"
        finally:
            app.API_URL = original_url

    def test_validate_env_config_checks_models(self):
        """Test that validation requires non-empty MODELS list"""
        import app

        original_models = app.MODELS
        try:
            # Test with empty models
            app.MODELS = []
            result = app.validate_env_config()
            assert result == False, "Should reject empty MODELS list"
        finally:
            app.MODELS = original_models

    def test_validate_env_config_passes_with_valid_config(self):
        """Test that validation passes with valid configuration"""
        import app

        # Assuming current config is valid
        result = app.validate_env_config()
        assert result == True, "Should pass with valid configuration"
