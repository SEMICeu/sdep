"""Configuration settings"""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Settings priority:
#
# - Arguments passed when instantiating Settings(...)
# - Environment variables from the OS
# - .env file (if configured via SettingsConfigDict(env_file=...))
# - Default values in this class


class Settings(BaseSettings):
    """Application settings with environment variable support."""

    model_config = SettingsConfigDict(
        env_file="../.env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application settings
    APP_NAME: str = "Single Digital Entrypoint"

    # OS settings
    DTAP: str = Field(
        default="DEV",
        description="DTAP environment (DEV/tests/ACC/PROD)",
    )
    IMAGE_TAG: str = Field(
        default="undefined",
        description="Image tag from container build",
    )

    # Backend settings
    BACKEND_BASE_URL: str = Field(
        default="http://localhost:8000",
        description="Base URL for the API (used in OpenAPI token URLs)",
    )

    # Keycloak settings
    KC_BASE_URL: str = Field(
        default="",
        description="Keycloak server URL for token endpoint",
    )

    # Database settings
    POSTGRES_HOST: str = Field(
        default="localhost",
        description="PostgreSQL server",
    )
    POSTGRES_PORT: int = Field(default=5432, description="Database port")
    POSTGRES_DB_NAME: str = Field(default="sdep", description="Database name")

    # Database credentials
    POSTGRES_DB_USER: str = Field(
        default="undefined", description="Database application user"
    )
    POSTGRES_DB_PASSWORD: str = Field(
        default="undefined", description="Database application password"
    )


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Global settings instance
settings = get_settings()
