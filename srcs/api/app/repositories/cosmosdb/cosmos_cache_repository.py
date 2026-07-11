"""Azure Cosmos DB implementation of the cache repository."""

from __future__ import annotations

from datetime import datetime
from typing import Any, cast

from azure.cosmos import CosmosClient, PartitionKey, exceptions

from app.core.config import Settings
from app.repositories.cache_repository import (
    CacheRecord,
    CacheRepository,
    cache_record_id,
)

CACHE_CONTAINER_NAME = "cache"


class CosmosCacheRepository:
    """Cache repository backed by Cosmos DB."""

    def __init__(self, client: CosmosClient, settings: Settings) -> None:
        self._database = client.create_database_if_not_exists(id=settings.az_cosmosdb_database_name)
        self._container = self._database.create_container_if_not_exists(
            id=CACHE_CONTAINER_NAME,
            partition_key=PartitionKey(path="/cacheType"),
        )

    def get(self, cache_type: str, cache_key: str) -> CacheRecord | None:
        item_id = cache_record_id(cache_type, cache_key)
        try:
            item = cast(
                dict[str, Any],
                self._container.read_item(item=item_id, partition_key=cache_type),
            )
        except exceptions.CosmosResourceNotFoundError:
            return None
        return self._deserialize(item)

    def upsert(self, record: CacheRecord) -> None:
        self._container.upsert_item(self._serialize(record))

    def delete(self, cache_type: str, cache_key: str) -> None:
        item_id = cache_record_id(cache_type, cache_key)
        try:
            self._container.delete_item(item=item_id, partition_key=cache_type)
        except exceptions.CosmosResourceNotFoundError:
            return

    @staticmethod
    def _serialize(record: CacheRecord) -> dict[str, Any]:
        return {
            "id": cache_record_id(record.cache_type, record.cache_key),
            "cacheType": record.cache_type,
            "cacheKey": record.cache_key,
            "value": record.value,
            "createdAt": record.created_at.isoformat(),
        }

    @staticmethod
    def _deserialize(item: dict[str, Any]) -> CacheRecord:
        return CacheRecord(
            cache_type=cast(str, item["cacheType"]),
            cache_key=cast(str, item["cacheKey"]),
            value=cast(str | dict[str, Any], item["value"]),
            created_at=datetime.fromisoformat(cast(str, item["createdAt"])),
        )


def build_cosmos_cache_repository(settings: Settings) -> CacheRepository:
    """Construct the default Cosmos-backed cache repository."""

    client = CosmosClient.from_connection_string(
        settings.az_cosmosdb_connection_string,
        connection_verify=settings.environment.lower() != "localhost",
    )
    return CosmosCacheRepository(client=client, settings=settings)
