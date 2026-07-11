"""Application startup orchestration and infrastructure checks."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from typing import Any, cast

from fastapi import FastAPI

from app.core.config import Settings
from app.core.logging import get_logger
from app.providers.cache_provider import CacheProvider, RepositoryCacheProvider
from app.repositories.novel_repository import NovelRepository
from app.repositories.user_repository import UserRepository
from app.services.crawler_service import FlareSolverrClientLike
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
    provided_user_repository: UserRepository | None,
    provided_novel_repository: NovelRepository | None,
    provided_cache_provider: CacheProvider | None = None,
    provided_flaresolverr_client: FlareSolverrClientLike | None = None,
) -> Callable[[FastAPI], Any]:
    """Create the FastAPI lifespan function for startup orchestration."""

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        validate_external_connections(settings)
        user_repository = provided_user_repository or _build_default_user_repository(settings)
        novel_repository = provided_novel_repository or _build_default_novel_repository(settings)
        cache_provider = provided_cache_provider or _build_default_cache_provider(settings)
        flaresolverr_client = provided_flaresolverr_client or _build_default_flaresolverr_client(
            settings
        )
        app.state.user_repository = user_repository
        app.state.novel_repository = novel_repository
        app.state.cache_provider = cache_provider
        app.state.flaresolverr_client = flaresolverr_client
        seed_admin_user(settings, user_repository)
        yield

    return lifespan


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
            "Unable to connect to Cosmos DB using AZ_COSMOSDB_CONNECTION_STRING."
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
            "Unable to connect to Blob Storage using AZ_STORAGE_BLOB_CONNECTION_STRING."
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
            "Unable to connect to Queue Storage using AZ_STORAGE_QUEUE_CONNECTION_STRING."
        ) from exc


def _build_default_user_repository(settings: Settings) -> UserRepository:
    from app.repositories.cosmosdb.cosmos_user_repository import build_cosmos_user_repository

    return build_cosmos_user_repository(settings)


def _build_default_novel_repository(settings: Settings) -> NovelRepository:
    from app.repositories.cosmosdb.cosmos_novel_repository import build_cosmos_novel_repository

    return build_cosmos_novel_repository(settings)


def _build_default_cache_provider(settings: Settings) -> CacheProvider:
    from app.repositories.cosmosdb.cosmos_cache_repository import build_cosmos_cache_repository

    return RepositoryCacheProvider(
        repository=build_cosmos_cache_repository(settings),
        ttl_seconds=settings.crawler_cache_ttl_seconds,
    )


def _build_default_flaresolverr_client(settings: Settings) -> FlareSolverrClientLike:
    from shared.flaresolverr_http_client import FlareSolverrHttpClient

    return cast(
        FlareSolverrClientLike,
        FlareSolverrHttpClient(base_url=settings.flaresolverr_base_url),
    )


def _should_verify_connection(settings: Settings) -> bool:
    return settings.environment.lower() != "localhost"


def _storage_api_version(settings: Settings) -> str | None:
    if settings.environment.lower() == "localhost":
        return "2024-11-04"
    return None
