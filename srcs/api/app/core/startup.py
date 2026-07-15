"""Application startup orchestration and infrastructure checks."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from typing import Any

from fastapi import FastAPI

from app.core.azure import should_verify_connection, storage_api_version
from app.core.logger import Logger
from app.core.logging import get_logger
from app.core.runtime import ApplicationOverrides, ApplicationRuntime

try:
    from azure.cosmos import CosmosClient
    from azure.storage.blob import BlobServiceClient
    from azure.storage.queue import QueueServiceClient
except ImportError as exc:  # pragma: no cover - exercised when deps are missing
    raise RuntimeError(
        "Azure SDK dependencies are missing. Install the api package dependencies first."
    ) from exc




# def build_lifespan(settings: Settings, overrides: ApplicationOverrides) -> Callable[[FastAPI], Any]:
#     """Create the FastAPI lifespan function for startup orchestration."""

#     @asynccontextmanager
#     async def lifespan(app: FastAPI) -> AsyncIterator[None]:
#         validate_external_connections(settings)
#         runtime = ApplicationRuntime(settings, overrides)
#         runtime.ensure_queues()
#         runtime.attach(app)

#         from app.services.user_service import seed_admin_user

#         seed_admin_user(settings, runtime.user_repository)
#         runtime.start()
#         try:
#             yield
#         finally:
#             runtime.stop()

#     return lifespan


def validate_external_connections(settings: Settings) -> None:
    """Fail fast if the configured Azure endpoints cannot be reached."""

    _check_cosmos(settings)
    _check_blob_storage(settings)
    _check_queue_storage(settings)


def _check_cosmos(settings: Settings) -> None:
    logger.info("Checking connectivity to Cosmos DB...")
    try:
        client = CosmosClient.from_connection_string(
            settings.az_cosmosdb_connection_string,
            connection_verify=_should_verify_connection(settings),
        )
        client.get_database_account()
    except Exception as exc:  # pragma: no cover - runtime integration path
        logger.exception("Cosmos DB connectivity check failed")
        raise RuntimeError(
            "Unable to connect to Cosmos DB using FAST_AZ_CONNECTION_STRING_COSMOSDB."
        ) from exc


def _check_blob_storage(settings: Settings) -> None:
    logger.info("Checking connectivity to Blob Storage...")
    try:
        client = BlobServiceClient.from_connection_string(
            settings.az_storage_blob_connection_string,
            api_version=_storage_api_version(settings),
        )
        client.get_service_properties()
    except Exception as exc:  # pragma: no cover - runtime integration path
        logger.exception("Blob Storage connectivity check failed")
        raise RuntimeError(
            "Unable to connect to Blob Storage using FAST_AZ_CONNECTION_STRING_STORAGE_BLOB."
        ) from exc


def _check_queue_storage(settings: Settings) -> None:
    logger.info("Checking connectivity to Queue Storage...")
    try:
        client = QueueServiceClient.from_connection_string(
            settings.az_storage_queue_connection_string,
            api_version=_storage_api_version(settings),
        )
        client.get_service_properties()
    except Exception as exc:  # pragma: no cover - runtime integration path
        logger.exception("Queue Storage connectivity check failed")
        raise RuntimeError(
            "Unable to connect to Queue Storage using FAST_AZ_CONNECTION_STRING_STORAGE_QUEUE."
        ) from exc


def _should_verify_connection(settings: Settings) -> bool:
    return should_verify_connection(settings)


def _storage_api_version(settings: Settings) -> str | None:
    return storage_api_version(settings)
