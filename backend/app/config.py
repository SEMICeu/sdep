"""Configuration settings"""

from functools import lru_cache
from typing import Self

from pydantic import Field, model_validator
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
        env_ignore_empty=True,
        extra="ignore",
    )

    # Application settings
    APP_NAME: str = Field(
        default="Single Digital Entry Point",
        description="Application name",
    )

    # OS settings
    DTAP: str = Field(
        default="DEV",
        description="DTAP environment (DEV/TST/ACC/PRE/PRD)",
    )
    # Semantic version of this release (the pipeline sets the image tag). Served as
    # OpenAPI `info.version` and the `API-Version` response header, see docs/API_TECH.md
    # "NLgov REST API Design Rules". The local default is valid semver too.
    IMAGE_TAG: str = Field(
        default="0.0.0-dev",
        description="Image tag from container build (semantic version)",
    )
    # OpenAPI `info.contact`, published in every version's document: a functional
    # mailbox of the deployment's API owner, so each Member State names its own team.
    API_CONTACT_NAME: str = Field(
        default="Nationaal Coordinator SDEP",
        description="API owner shown as OpenAPI info.contact.name",
    )
    API_CONTACT_URL: str = Field(
        default="https://minvro.nl/",
        description="API owner website shown as OpenAPI info.contact.url",
    )
    API_CONTACT_EMAIL: str = Field(
        default="nationaalcoordinatorsdep@minbzk.nl",
        description="API owner mailbox shown as OpenAPI info.contact.email",
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
    # Client-secret authentication (a static shared secret) is considered less secure
    # than client-signed JWT. Both use the same Client Credentials flow; this flag
    # gates the authentication method, not the flow. Note that client-signed JWT
    # (private_key_jwt) always stays available, even when this flag is false.
    # Default enabled is false, recommended to enable (true) in local- and test environments only.
    CLIENT_SECRET_AUTH_ENABLED: bool = Field(
        default=False,
        description=(
            "Allow client-secret authentication (client_secret_post / client_secret_basic) "
            "on the token endpoint. Disabled by default; only allow in local- and test "
            "environments. Client-signed JWT (private_key_jwt) always stays available, "
            "even when this flag is false."
        ),
    )

    # Alpha API versions are served up to PRE only, never in PRD, so data written through
    # a contract that may still change stays out of the production database. Off by
    # default; see docs/API_TECH.md "Design".
    API_ALPHA_ENABLED: bool = Field(
        default=False,
        description=(
            "Serve the alpha API versions. Disabled by default; only allow up to PRE. "
            "Refused when DTAP is PRD."
        ),
    )

    # Malware scan settings
    MALWARE_SCAN_ENABLED: bool = Field(
        default=True,
        description="Enable upload malware scanning with ClamAV",
    )
    MALWARE_SCAN_CLAMAV_HOST: str = Field(
        default="",
        description="ClamAV daemon host",
    )
    MALWARE_SCAN_CLAMAV_PORT: int = Field(
        default=3310,
        description="ClamAV daemon port",
    )
    MALWARE_SCAN_CLAMAV_TIMEOUT: int = Field(
        default=10,
        description="ClamAV scan timeout in seconds",
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
    POSTGRES_PORT: int = Field(
        default=5432,
        description="Database port",
    )
    POSTGRES_DB_NAME: str = Field(
        default="sdep",
        description="Database name",
    )

    # Database credentials
    POSTGRES_DB_USER: str = Field(
        default="undefined",
        description="Database application user",
    )
    POSTGRES_DB_PASSWORD: str = Field(
        default="undefined",
        description="Database application password",
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
        default=20,
        description="SQLAlchemy connection pool size",
    )
    APP_POOL_MAX_OVERFLOW: int = Field(
        default=30,
        description="SQLAlchemy max overflow connections",
    )

    @model_validator(mode="after")
    def _no_alpha_in_production(self) -> Self:
        """Refuse to start PRD with alpha versions enabled (see API_ALPHA_ENABLED)."""
        if self.API_ALPHA_ENABLED and self.DTAP.upper() == "PRD":
            raise ValueError("API_ALPHA_ENABLED must not be true when DTAP is PRD")

        return self

    @property
    def api_version(self) -> str:
        """Semantic version served as OpenAPI `info.version` and `API-Version` header."""
        return self.IMAGE_TAG

    @property
    def api_contact(self) -> dict[str, str]:
        """OpenAPI `info.contact` (name, url and email are all required by the design rules)."""
        return {
            "name": self.API_CONTACT_NAME,
            "url": self.API_CONTACT_URL,
            "email": self.API_CONTACT_EMAIL,
        }


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Global settings instance
settings = get_settings()
