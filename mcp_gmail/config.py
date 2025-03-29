"""
Configuration settings for the MCP Gmail server.
"""

import json
import os
from functools import lru_cache
from typing import List, Optional

from pydantic_settings import BaseSettings, SettingsConfigDict

# Import default settings from gmail module
from mcp_gmail.gmail import (
    DEFAULT_CREDENTIALS_PATH,
    DEFAULT_TOKEN_PATH,
    DEFAULT_USER_ID,
    GMAIL_SCOPES,
)


class Settings(BaseSettings):
    """
    Settings model for MCP Gmail server configuration.

    Automatically reads from environment variables with MCP_GMAIL_ prefix.
    """

    credentials_path: str = DEFAULT_CREDENTIALS_PATH
    token_path: str = DEFAULT_TOKEN_PATH
    scopes: List[str] = GMAIL_SCOPES
    port: int = 8080
    user_id: str = DEFAULT_USER_ID
    debug: bool = False
    max_results: int = 10

    # Configure environment variable settings
    model_config = SettingsConfigDict(
        env_prefix="MCP_GMAIL_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )


@lru_cache()
def get_settings(config_file: Optional[str] = None) -> Settings:
    """
    Get settings instance, optionally loaded from a config file.
    Uses LRU cache for performance.

    Args:
        config_file: Path to a JSON configuration file (optional)

    Returns:
        Settings instance
    """
    # Start with environment variables
    settings = Settings()

    # Override with config file if provided
    if config_file and os.path.exists(config_file):
        with open(config_file, "r") as f:
            file_config = json.load(f)
            # Update settings with values from config file
            settings = Settings.model_validate(file_config)

    return settings


# Create a default settings instance
settings = get_settings()
