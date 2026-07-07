"""Application startup orchestration and infrastructure checks."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI

from app.core.config import Settings
from app.core.logging import get_logger
from app.repositories.user_repository import UserRepository
from app.services.user_service import seed_admin_user

try:
    from azure.cosmos import CosmosClient
    from azure.storage.blob import BlobServiceClient
    from azure.storage.queue import QueueServiceClient
except ImportError as exc:  # pragma: no cover - exercised when deps are missing
    raise RuntimeError(
        "Azure SDK dependencies are missing. Install the api package dependencies first."
    ) from exc

logger = get_logger("startup")


def build_lifespan(
    settings: Settings,
    provided_repository: UserRepository | None,
) -> Callable[[FastAPI], Any]:
    """Create the FastAPI lifespan function for startup orchestration."""

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        logger.info("Application startup initiated")
        validate_external_connections(settings)
        logger.info("External infrastructure validation succeeded")
        repository = provided_repository or _build_default_user_repository(settings)
        app.state.user_repository = repository
        logger.info("User repository is ready")
        seed_admin_user(settings, repository)
        logger.info("Application startup completed")
        yield

    return lifespan


def validate_external_connections(settings: Settings) -> None:
    """Fail fast if the configured Azure endpoints cannot be reached."""

    logger.info("Validating external infrastructure connections")
    _check_cosmos(settings)
    _check_blob_storage(settings)
    _check_queue_storage(settings)
    logger.info("External infrastructure connections validated successfully")


def _check_cosmos(settings: Settings) -> None:
    logger.info("Checking Cosmos DB connectivity")
    try:
        client = CosmosClient.from_connection_string(
            settings.az_cosmosdb_connection_string,
            connection_verify=_should_verify_connection(settings),
        )
        client.get_database_account()
    except Exception as exc:  # pragma: no cover - runtime integration path
        logger.exception("Cosmos DB connectivity check failed")
        raise RuntimeError(
            "Unable to connect to Cosmos DB using AZ_COSMOSDB_CONNECTION_STRING."
        ) from exc
    logger.info("Cosmos DB connectivity check succeeded")


def _check_blob_storage(settings: Settings) -> None:
    logger.info("Checking Blob Storage connectivity")
    try:
        client = BlobServiceClient.from_connection_string(
            settings.az_storage_blob_connection_string,
            api_version=_storage_api_version(settings),
        )
        client.get_service_properties()
    except Exception as exc:  # pragma: no cover - runtime integration path
        logger.exception("Blob Storage connectivity check failed")
        raise RuntimeError(
            "Unable to connect to Blob Storage using AZ_STORAGE_BLOB_CONNECTION_STRING."
        ) from exc
    logger.info("Blob Storage connectivity check succeeded")


def _check_queue_storage(settings: Settings) -> None:
    logger.info("Checking Queue Storage connectivity")
    try:
        client = QueueServiceClient.from_connection_string(
            settings.az_storage_queue_connection_string,
            api_version=_storage_api_version(settings),
        )
        client.get_service_properties()
    except Exception as exc:  # pragma: no cover - runtime integration path
        logger.exception("Queue Storage connectivity check failed")
        raise RuntimeError(
            "Unable to connect to Queue Storage using AZ_STORAGE_QUEUE_CONNECTION_STRING."
        ) from exc
    logger.info("Queue Storage connectivity check succeeded")


def _build_default_user_repository(settings: Settings) -> UserRepository:
    from app.repositories.cosmosdb.cosmos_user_repository import build_cosmos_user_repository

    return build_cosmos_user_repository(settings)


def _should_verify_connection(settings: Settings) -> bool:
    return settings.environment.lower() != "localhost"


def _storage_api_version(settings: Settings) -> str | None:
    if settings.environment.lower() == "localhost":
        return "2024-11-04"
    return None
