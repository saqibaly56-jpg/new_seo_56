import os
import pytest
from unittest import mock
from config.settings import get_env_var, Settings

def test_app_boots():
    """Smoke test to ensure the test suite runs and imports work."""
    assert True

def test_config_loader_fails_fast_on_missing_key():
    """Ensure missing required env vars raise ValueError immediately."""
    with mock.patch.dict(os.environ, {}, clear=True):
        with pytest.raises(ValueError, match="CRITICAL ERROR: Required environment variable 'OPENROUTER_API_KEY' is missing or empty."):
            settings = Settings()
            _ = settings.openrouter_api_key

def test_config_loader_passes_when_configured():
    """Ensure config loader works when all required vars are present."""
    mock_env = {
        "OPENROUTER_API_KEY": "test_key",
        "WP_URL": "http://test",
        "WP_USERNAME": "test_user",
        "WP_APP_PASSWORD": "test_password",
        "CASINO_DATA_API_KEY": "test_casino_key"
    }
    with mock.patch.dict(os.environ, mock_env, clear=True):
        settings = Settings()
        assert settings.openrouter_api_key == "test_key"
        assert settings.wp_url == "http://test"
        assert settings.wp_username == "test_user"
        assert settings.wp_app_password == "test_password"
        assert settings.casino_data_api_key == "test_casino_key"
