"""Shared Azure runtime helpers."""

from app.core.config import Settings


def should_verify_connection(settings: Settings) -> bool:
    """Return whether Azure SDK clients should verify TLS connections."""

    return settings.environment.lower() != "localhost"


def storage_api_version(settings: Settings) -> str | None:
    """Return the Storage API version needed by the local Azurite emulator."""

    if settings.environment.lower() == "localhost":
        return "2024-11-04"
    return None
