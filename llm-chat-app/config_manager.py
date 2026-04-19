import os
from pathlib import Path
from typing import Dict, Optional, Any
import json

class ConfigManager:
    """Manages application configuration from .env and settings.json"""

    def __init__(self, env_file_path: str = '.env'):
        self.env_file_path = Path(env_file_path)
        self.settings_file_path = self.env_file_path.parent / 'settings.json'
        self.config: Dict[str, str] = {}
        self.runtime_overrides: Dict[str, Any] = {}

        self.load()

    def load(self):
        """Load configuration from .env file"""
        if not self.env_file_path.exists():
            raise FileNotFoundError(f".env file not found: {self.env_file_path}")

        self.config = {}
        # Clear runtime overrides before reloading
        self.runtime_overrides = {}

        with open(self.env_file_path, 'r') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue

                if '=' in line:
                    key, value = line.split('=', 1)
                    self.config[key.strip()] = value.strip()

        # Load runtime overrides from settings.json if exists
        if self.settings_file_path.exists():
            with open(self.settings_file_path, 'r') as f:
                self.runtime_overrides = json.load(f)

    def get(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """Get configuration value with optional default"""
        # Check runtime overrides first
        if key in self.runtime_overrides:
            return str(self.runtime_overrides[key])

        # Then check .env config
        return self.config.get(key, default)

    def set_runtime(self, key: str, value: Any):
        """Set a runtime override (doesn't modify .env)"""
        self.runtime_overrides[key] = value

    def save_runtime_overrides(self):
        """Save runtime overrides to settings.json"""
        with open(self.settings_file_path, 'w') as f:
            json.dump(self.runtime_overrides, f, indent=2)

    def get_all(self) -> Dict[str, str]:
        """Get all configuration as dictionary"""
        result = self.config.copy()
        # Apply runtime overrides
        for key, value in self.runtime_overrides.items():
            result[key] = str(value)
        return result

    def update_env_file(self, updates: Dict[str, str]):
        """Update .env file with new values (careful operation)"""
        # Read existing lines
        lines = []
        if self.env_file_path.exists():
            with open(self.env_file_path, 'r') as f:
                lines = f.readlines()

        # Update existing keys or add new ones
        updated_keys = set()
        new_lines = []

        for line in lines:
            stripped = line.strip()
            if not stripped or stripped.startswith('#'):
                new_lines.append(line)
                continue

            if '=' in stripped:
                key, _ = stripped.split('=', 1)
                key = key.strip()

                if key in updates:
                    new_lines.append(f"{key}={updates[key]}\n")
                    updated_keys.add(key)
                else:
                    new_lines.append(line)
            else:
                new_lines.append(line)

        # Ensure last line ends with newline before adding new keys
        if new_lines and not new_lines[-1].endswith('\n'):
            new_lines[-1] += '\n'

        # Add new keys that weren't in file
        for key, value in updates.items():
            if key not in updated_keys:
                new_lines.append(f"{key}={value}\n")

        # Write back
        with open(self.env_file_path, 'w') as f:
            f.writelines(new_lines)

        # Reload config
        self.load()

# Global instance
_config_manager = None

def get_config_manager(env_file_path: str = '.env') -> ConfigManager:
    """Get or create singleton ConfigManager instance"""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager(env_file_path)
    return _config_manager
