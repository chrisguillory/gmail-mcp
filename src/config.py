"""Configuration settings for the Gmail MCP server."""

import json
import os

from pydantic_settings import BaseSettings, SettingsConfigDict

# Default settings
DEFAULT_CREDENTIALS_PATH = 'credentials.json'
DEFAULT_TOKEN_PATH = 'token.json'
DEFAULT_USER_ID = 'me'

# Gmail API scopes
GMAIL_SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/gmail.send',
    'https://www.googleapis.com/auth/gmail.compose',
    'https://www.googleapis.com/auth/gmail.labels',
]

# For simpler testing
GMAIL_MODIFY_SCOPE = ['https://www.googleapis.com/auth/gmail.modify']


class Settings(BaseSettings):
    """
    Settings model for Gmail MCP server configuration.

    Automatically reads from environment variables with MCP_GMAIL_ prefix.
    """

    credentials_path: str = DEFAULT_CREDENTIALS_PATH
    token_path: str = DEFAULT_TOKEN_PATH
    scopes: list[str] = GMAIL_SCOPES
    user_id: str = DEFAULT_USER_ID
    max_results: int = 10

    # Configure environment variable settings
    model_config = SettingsConfigDict(
        env_prefix='MCP_GMAIL_',
        env_file='.env',
        env_file_encoding='utf-8',
        extra='ignore',
        case_sensitive=False,
    )


def get_settings(config_file: str | None = None) -> Settings:
    """
    Get settings instance, optionally loaded from a config file.

    Args:
        config_file: Path to a JSON configuration file (optional)

    Returns:
        Settings instance
    """
    if config_file is None:
        return Settings()

    # Override with config file if provided
    if config_file and os.path.exists(config_file):
        with open(config_file, 'r') as f:
            file_config = json.load(f)
            settings = Settings.model_validate(file_config)
            return settings

    return Settings()


# Create a default settings instance
settings = get_settings()
