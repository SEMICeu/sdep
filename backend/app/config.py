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

    # Audit log settings
    AUDITLOG_RETENTION: int = Field(
        default=1,
        description="Audit log retention in days",
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

    # App connection pool settings
    #
    # Each HTTP request that needs the database, checks out a connection from
    # SQLAlchemy's pool. pool_size is the number of persistent connections kept
    # idle and ready; max_overflow allows temporary extra connections under load.
    #
    # So the max concurrent DB connections per replica = pool_size + max_overflow.
    # This effectively limits how many concurrent database-bound requests a single
    # replica can serve - additional requests wait for a connection to be returned.
    #
    # Pool sizing: must accommodate concurrent bulk requests.
    # PgBouncer allows e.g. 50 server connections (default_pool_size=50),
    # so app pool_size + max_overflow should stay well below that limit
    # to leave headroom for other clients (psql, migrations, monitoring).
    #
    # With a given maxReplicas deployed, each replica pool_size + max_overflow must
    # satisfy: maxReplicas x (pool_size + max_overflow) <= PgBouncer budget.
    # Example: 2 replicas x (10 + 15) = 50 max app connections.
    #
    # Note: there is also the pgBouncer max_client_conn (e.g. 1000), which limits the #clients
    # accepted by PgBouncer. This is typically not a bottleneck, because max_client_conn
    # only caps how many client connections PgBouncer accepts, not how many reach PostgreSQL.
    # With session pooling, default_pool_size remains the binding server-side constraint.
    APP_POOL_SIZE: int = Field(
        default=20, description="SQLAlchemy connection pool size"
    )
    APP_POOL_MAX_OVERFLOW: int = Field(
        default=30, description="SQLAlchemy max overflow connections"
    )


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Global settings instance
settings = get_settings()
