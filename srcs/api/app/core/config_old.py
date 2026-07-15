"""Application settings, loaded from environment variables (12-factor)."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-driven configuration.

    In Azure these resolve from Key Vault via Managed Identity; locally they come
    from a `.env` file (see `.env.example`).
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="FAST_",
        extra="ignore",
    )

    # Auth.
    admin_email: str = Field(validation_alias="FAST_SECURITY_DEFAULT_ADMIN_EMAIL")
    admin_password: str = Field(validation_alias="FAST_SECURITY_DEFAULT_ADMIN_PASSWORD")

    # JWT
    jwt_signing_key: str = Field(validation_alias="FAST_SECURITY_JWT_SIGNING_KEY")
    jwt_expire_minutes: int = Field(default=60, validation_alias="FAST_SECURITY_JWT_EXPIRE_MINUTES")
    jwt_algorithm: str = "HS256"

    # CORS — the Nuxt web app origin (only origin allowed).
    cors_allowed_origin: str = Field(
        default="http://localhost:3000",
        validation_alias="FAST_SECURITY_CORS_ALLOWED_ORIGIN",
    )

    # Runtime environment name. Use "localhost" to relax emulator TLS checks.
    environment: str = "production"

    # Logging
    log_level: str = "INFO"
    log_file_path: str = "logs/api.log"

    # Azure connection strings.
    az_cosmosdb_connection_string: str = Field(
        validation_alias="FAST_AZ_CONNECTION_STRING_COSMOSDB"
    )
    az_storage_blob_connection_string: str = Field(
        validation_alias="FAST_AZ_CONNECTION_STRING_STORAGE_BLOB"
    )
    az_storage_queue_connection_string: str = Field(
        validation_alias="FAST_AZ_CONNECTION_STRING_STORAGE_QUEUE"
    )

    # Azure configuration
    az_cosmosdb_database_name: str = "mediastudio"
    az_storage_queue_api_version: str | None = "2024-11-04"

    # Crawler infrastructure.
    flaresolverr_base_url: str = "http://localhost:8191/v1"
    flaresolverr_max_timeout_ms: int = 60000
    crawler_cache_ttl_seconds: int = Field(
        default=2_592_000,
        validation_alias="FAST_CACHE_TTL_SECONDS_CRAWLER",
    )

@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()
