"""
Tests for the configuration module.
"""

import json
import os
import tempfile

from mcp_gmail.config import Settings, get_settings


def test_default_settings():
    """Test that the default configuration is created correctly."""
    settings = get_settings()
    assert settings.credentials_path == "credentials.json"
    assert settings.token_path == "token.json"
    assert "gmail.readonly" in settings.scopes[0]
    assert settings.port == 8080
    assert settings.user_id == "me"
    assert settings.debug is False
    assert settings.max_results == 10


def test_settings_from_file():
    """Test loading configuration from a file."""
    # Create a temporary config file
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as temp_file:
        config_data = {
            "credentials_path": "custom_creds.json",
            "token_path": "custom_token.json",
            "port": 9000,
            "debug": True,
            "max_results": 20,
        }
        temp_file.write(json.dumps(config_data).encode("utf-8"))
        temp_path = temp_file.name

    try:
        # Load the config from file
        settings = get_settings(temp_path)

        # Check that values from file were loaded
        assert settings.credentials_path == "custom_creds.json"
        assert settings.token_path == "custom_token.json"
        assert settings.port == 9000
        assert settings.debug is True
        assert settings.max_results == 20

        # Check that default values are still present for unspecified fields
        assert "gmail.readonly" in settings.scopes[0]
        assert settings.user_id == "me"
    finally:
        # Clean up temp file
        os.unlink(temp_path)


def test_environment_variables(monkeypatch):
    """Test that environment variables override defaults."""
    # Set environment variables with the correct prefix
    monkeypatch.setenv("MCP_GMAIL_CREDENTIALS_PATH", "env_creds.json")
    monkeypatch.setenv("MCP_GMAIL_PORT", "7000")
    monkeypatch.setenv("MCP_GMAIL_DEBUG", "true")
    monkeypatch.setenv("MCP_GMAIL_MAX_RESULTS", "50")

    # Reload config to pick up environment variables
    settings = get_settings()

    # Check that environment variables were used
    assert settings.credentials_path == "env_creds.json"
    assert settings.port == 7000
    assert settings.debug is True
    assert settings.max_results == 50


def test_settings_direct_use():
    """Test using the Settings class directly."""
    # Create a model with custom values
    settings = Settings(
        credentials_path="direct_creds.json",
        token_path="direct_token.json",
        port=5000,
        debug=True,
        max_results=30,
    )

    # Validate model fields
    assert settings.credentials_path == "direct_creds.json"
    assert settings.token_path == "direct_token.json"
    assert settings.port == 5000
    assert settings.debug is True
    assert settings.max_results == 30

    # Export to dictionary
    model_dict = settings.model_dump()
    assert model_dict["credentials_path"] == "direct_creds.json"

    # Export to JSON
    model_json = settings.model_dump_json()
    assert "direct_creds.json" in model_json


def test_cached_settings(tmp_path):
    """Test that get_settings caches results properly."""
    # Create two different config files in tmp_path subdirectories
    config_dir1 = tmp_path / "config1"
    config_dir2 = tmp_path / "config2"
    config_dir1.mkdir()
    config_dir2.mkdir()

    config_file1 = config_dir1 / "settings.json"
    config_data1 = {"port": 1111, "debug": True}
    config_file1.write_text(json.dumps(config_data1))

    config_file2 = config_dir2 / "settings.json"
    config_data2 = {"port": 2222, "debug": False}
    config_file2.write_text(json.dumps(config_data2))

    # First call should load and cache the settings
    settings1 = get_settings(str(config_file1))
    assert settings1.port == 1111
    assert settings1.debug is True

    # Different file path should load different settings
    settings2 = get_settings(str(config_file2))
    assert settings2.port == 2222
    assert settings2.debug is False

    # Calling again with same path should return cached settings
    settings1_again = get_settings(str(config_file1))
    assert settings1_again is settings1  # Should be same instance due to caching

    # Clear the LRU cache to force a reload
    get_settings.cache_clear()

    # After clearing cache, should load fresh settings
    settings1_fresh = get_settings(str(config_file1))
    assert settings1_fresh is not settings1  # Should be different instance
    assert settings1_fresh.port == 1111  # But same values
