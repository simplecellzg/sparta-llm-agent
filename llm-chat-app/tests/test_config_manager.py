import pytest
import os
from pathlib import Path
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from config_manager import ConfigManager

@pytest.fixture
def temp_env_file(tmp_path):
    """Create a temporary .env file for testing"""
    env_file = tmp_path / ".env"
    env_file.write_text("""
API_URL=https://api.example.com/v1
API_KEY=test-key-123
LLM_MODEL=claude-opus-4-5
RAG_ENABLED=true
MAX_TOKENS=4096
    """.strip())
    return env_file

def test_config_manager_loads_from_env(temp_env_file):
    """Test ConfigManager loads configuration from .env file"""
    config_mgr = ConfigManager(str(temp_env_file))

    assert config_mgr.get('API_URL') == 'https://api.example.com/v1'
    assert config_mgr.get('API_KEY') == 'test-key-123'
    assert config_mgr.get('LLM_MODEL') == 'claude-opus-4-5'
    assert config_mgr.get('RAG_ENABLED') == 'true'
    assert config_mgr.get('MAX_TOKENS') == '4096'

def test_config_manager_get_with_default(temp_env_file):
    """Test ConfigManager.get() with default value"""
    config_mgr = ConfigManager(str(temp_env_file))

    assert config_mgr.get('NONEXISTENT_KEY', 'default') == 'default'
    assert config_mgr.get('API_URL', 'default') == 'https://api.example.com/v1'

def test_set_runtime_override(temp_env_file):
    """Test setting runtime overrides"""
    config_mgr = ConfigManager(str(temp_env_file))

    original_url = config_mgr.get('API_URL')
    assert original_url == 'https://api.example.com/v1'

    # Set runtime override
    config_mgr.set_runtime('API_URL', 'https://custom.api.com/v1')

    assert config_mgr.get('API_URL') == 'https://custom.api.com/v1'

    # Original .env file unchanged
    config_mgr.load()
    assert config_mgr.get('API_URL') == 'https://api.example.com/v1'

def test_save_and_load_runtime_overrides(temp_env_file):
    """Test persisting runtime overrides to settings.json"""
    config_mgr = ConfigManager(str(temp_env_file))

    config_mgr.set_runtime('API_URL', 'https://override.com')
    config_mgr.set_runtime('CUSTOM_SETTING', 'custom_value')
    config_mgr.save_runtime_overrides()

    # Create new instance - should load overrides
    config_mgr2 = ConfigManager(str(temp_env_file))
    assert config_mgr2.get('API_URL') == 'https://override.com'
    assert config_mgr2.get('CUSTOM_SETTING') == 'custom_value'

def test_update_env_file(temp_env_file):
    """Test updating .env file with new values"""
    config_mgr = ConfigManager(str(temp_env_file))

    updates = {
        'API_URL': 'https://new-api.com/v1',
        'NEW_KEY': 'new_value'
    }
    config_mgr.update_env_file(updates)

    # Verify updates applied
    assert config_mgr.get('API_URL') == 'https://new-api.com/v1'
    assert config_mgr.get('NEW_KEY') == 'new_value'
    assert config_mgr.get('API_KEY') == 'test-key-123'  # Unchanged

    # Verify file contents
    content = temp_env_file.read_text()
    assert 'API_URL=https://new-api.com/v1' in content
    assert 'NEW_KEY=new_value' in content
