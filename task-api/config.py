"""
Configuration management for Task Management API.

This module loads environment variables and provides typed configuration
for the entire application. Settings are cached to avoid repeated file reads.
"""

from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import Optional


class Settings(BaseSettings):
    """Application settings from environment variables.

    Attributes:
        database_url: PostgreSQL connection string (required)
        debug: Enable debug mode (default: True)
        api_title: API title for documentation (default: Task Management API)
        api_version: API version string (default: 1.0.0)
        host: Server bind address (default: 0.0.0.0)
        port: Server port (default: 8000)

    Raises:
        ValidationError: If DATABASE_URL is not set
    """

    # Required settings - will raise error if not provided
    database_url: str

    # Optional settings with defaults
    debug: bool = True
    api_title: str = "Task Management API"
    api_version: str = "1.0.0"
    host: str = "0.0.0.0"
    port: int = 8000

    class Config:
        """Pydantic configuration for settings."""
        env_file = ".env"
        case_sensitive = False


@lru_cache
def get_settings() -> Settings:
    """Get cached application settings.

    This function is cached using @lru_cache to load settings only once.
    Subsequent calls return the cached settings without re-reading the .env file.

    Returns:
        Settings: Cached application settings instance

    Example:
        >>> settings = get_settings()
        >>> db_url = settings.database_url
    """
    return Settings()


# For easy import: from config import settings
settings = get_settings()
