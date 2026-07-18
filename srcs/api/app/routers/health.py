import logging

from azure.cosmos import CosmosClient
from azure.storage.blob import BlobServiceClient
from azure.storage.queue import QueueServiceClient
from fastapi import APIRouter

from app.core.config.app_config import AppConfig
from app.core.logging import LogManager

router = APIRouter(tags=["health"])

@router.get("/health")
def health() -> dict[str, str]:
    logger = LogManager().getLogger("router.health")
    settings = AppConfig()

    cosmos_ok = _check_cosmos(logger, settings)
    blob_ok = _check_blob_storage(logger, settings)
    queue_ok = _check_queue_storage(logger, settings)

    return {
        "azCosmosDb": "ok" if cosmos_ok else "error",
        "azStorageBlob": "ok" if blob_ok else "error",
        "azStorageQueue": "ok" if queue_ok else "error",
    }


def _check_cosmos(logger: logging.Logger, settings: AppConfig) -> bool:
    logger.info("Checking connectivity to Cosmos DB...")
    try:
        client = CosmosClient.from_connection_string(
            settings.connectionStrings.azCosmosDb,
            connection_verify=True
        )
        client.get_database_account()
        return True
    except Exception as exc:  # pragma: no cover - runtime integration path
        logger.exception("Cosmos DB connectivity check failed", exc_info=exc)
        return False
    
def _check_blob_storage(logger: logging.Logger, settings: AppConfig) -> bool:
    logger.info("Checking connectivity to Blob Storage...")
    try:
        client = BlobServiceClient.from_connection_string(
            settings.connectionStrings.azStorageBlob,
            api_version=_storage_api_version(settings),
        )
        client.get_service_properties()
        return True
    except Exception as exc:  # pragma: no cover - runtime integration path
        logger.exception("Blob Storage connectivity check failed", exc_info=exc)
        return False


def _check_queue_storage(logger: logging.Logger, settings: AppConfig) -> bool:
    logger.info("Checking connectivity to Queue Storage...")
    try:
        client = QueueServiceClient.from_connection_string(
            settings.connectionStrings.azStorageQueue,
            api_version=_storage_api_version(settings),
        )
        client.get_service_properties()
        return True
    except Exception as exc:  # pragma: no cover - runtime integration path
        logger.exception("Queue Storage connectivity check failed", exc_info=exc)
        return False

def _storage_api_version(settings: AppConfig) -> str | None:
    return "2024-11-04" if settings.environment.lower() == "localhost" else None