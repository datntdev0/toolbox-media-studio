"""Application settings, loaded from environment variables (12-factor)."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-driven configuration.

    In Azure these resolve from Key Vault via Managed Identity; locally they come
    from a `.env` file (see `.env.example`).
    """

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Auth — this iteration validates login against these values (no database yet).
    admin_email: str
    admin_password: str

    # JWT
    jwt_signing_key: str
    jwt_expire_minutes: int = 60
    jwt_algorithm: str = "HS256"

    # CORS — the Nuxt web app origin (only origin allowed).
    cors_allowed_origin: str = "http://localhost:3000"


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()
