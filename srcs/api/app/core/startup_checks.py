"""Startup checks for external infrastructure dependencies."""

from __future__ import annotations

from app.core.config import Settings

try:
    from azure.cosmos import CosmosClient
    from azure.storage.blob import BlobServiceClient
    from azure.storage.queue import QueueServiceClient
except ImportError as exc:  # pragma: no cover - exercised when deps are missing
    raise RuntimeError(
        "Azure SDK dependencies are missing. Install the api package dependencies first."
    ) from exc


def validate_external_connections(settings: Settings) -> None:
    """Fail fast if the configured Azure endpoints cannot be reached."""

    _check_cosmos(settings)
    _check_blob_storage(settings)
    _check_queue_storage(settings)


def _check_cosmos(settings: Settings) -> None:
    try:
        client = CosmosClient.from_connection_string(
            settings.az_cosmosdb_connection_string,
            connection_verify=_should_verify_connection(settings),
        )
        client.get_database_account()
    except Exception as exc:  # pragma: no cover - runtime integration path
        raise RuntimeError(
            "Unable to connect to Cosmos DB using AZ_COSMOSDB_CONNECTION_STRING."
        ) from exc


def _check_blob_storage(settings: Settings) -> None:
    try:
        client = BlobServiceClient.from_connection_string(
            settings.az_storage_blob_connection_string,
            api_version=_storage_api_version(settings),
        )
        client.get_service_properties()
    except Exception as exc:  # pragma: no cover - runtime integration path
        raise RuntimeError(
            "Unable to connect to Blob Storage using AZ_STORAGE_BLOB_CONNECTION_STRING."
        ) from exc


def _check_queue_storage(settings: Settings) -> None:
    try:
        client = QueueServiceClient.from_connection_string(
            settings.az_storage_queue_connection_string,
            api_version=_storage_api_version(settings),
        )
        client.get_service_properties()
    except Exception as exc:  # pragma: no cover - runtime integration path
        raise RuntimeError(
            "Unable to connect to Queue Storage using AZ_STORAGE_QUEUE_CONNECTION_STRING."
        ) from exc


def _should_verify_connection(settings: Settings) -> bool:
    return settings.environment.lower() != "localhost"


def _storage_api_version(settings: Settings) -> str | None:
    if settings.environment.lower() == "localhost":
        return "2024-11-04"
    return None
