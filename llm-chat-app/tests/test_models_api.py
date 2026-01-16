import pytest
from pathlib import Path
import sys
import json

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestModelsAPI:
    """Test /api/models endpoint returns correct model list"""

    def test_models_loaded_from_env(self):
        """Test MODELS variable loads correctly from .env"""
        from app import MODELS

        # Based on .env file: MODELS=claude-opus-4-5-20251101,gemini-3-pro-preview,deepseek-v3-250324
        assert len(MODELS) >= 3, f"Expected at least 3 models, got {len(MODELS)}: {MODELS}"
        assert "claude-opus-4-5-20251101" in MODELS, "Missing claude-opus-4-5-20251101"
        assert "gemini-3-pro-preview" in MODELS, "Missing gemini-3-pro-preview"
        assert "deepseek-v3-250324" in MODELS, "Missing deepseek-v3-250324"

    def test_models_api_endpoint_exists(self):
        """Test /api/models endpoint exists"""
        from app import app

        with app.test_client() as client:
            response = client.get('/api/models')
            assert response.status_code == 200, f"Expected 200, got {response.status_code}"

    def test_models_api_returns_json_list(self):
        """Test /api/models returns JSON array"""
        from app import app

        with app.test_client() as client:
            response = client.get('/api/models')
            assert response.content_type == 'application/json', \
                f"Expected JSON content type, got {response.content_type}"

            models = response.get_json()
            assert isinstance(models, list), f"Expected list, got {type(models)}"

    def test_models_api_returns_configured_models(self):
        """Test /api/models returns the models from MODELS config"""
        from app import app, MODELS

        with app.test_client() as client:
            response = client.get('/api/models')
            models = response.get_json()

            assert len(models) == len(MODELS), \
                f"Expected {len(MODELS)} models, got {len(models)}"

            for model in MODELS:
                assert model in models, f"Model {model} not in API response"

    def test_models_no_duplicates(self):
        """Test MODELS list has no duplicates"""
        from app import MODELS

        assert len(MODELS) == len(set(MODELS)), \
            f"MODELS contains duplicates: {MODELS}"
