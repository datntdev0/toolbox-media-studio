"""Cache providers."""

from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from typing import Any, Protocol, cast

from azure.cosmos import CosmosClient, PartitionKey, exceptions

CacheValue = str | dict[str, Any]
CacheClock = Callable[[], datetime]
CACHE_CONTAINER_NAME = "sys.caches"


@dataclass(frozen=True, slots=True)
class CacheRecord:
    """Persisted cache record."""

    cache_type: str
    cache_key: str
    value: CacheValue
    created_at: datetime
    expired_at: datetime


class CacheProvider(Protocol):
    """Generic cache contract."""

    def get(self, cache_type: str, cache_key: str) -> CacheValue | None: ...

    def set(
        self,
        cache_type: str,
        cache_key: str,
        value: CacheValue,
        ttl: int | None = None,
    ) -> None: ...

    def delete(self, cache_type: str, cache_key: str) -> None: ...


class _RecordCacheProvider:
    """Cache provider behavior backed by concrete record storage."""

    def __init__(
        self,
        ttl_seconds: int,
        clock: CacheClock | None = None,
    ) -> None:
        self._ttl = timedelta(seconds=ttl_seconds)
        self._clock = clock or _utc_now

    def get(self, cache_type: str, cache_key: str) -> CacheValue | None:
        record = self._get_record(cache_type, cache_key)
        if record is None:
            return None
        if _is_expired(record.expired_at, self._clock()):
            self._delete_record(cache_type, cache_key)
            return None
        return record.value

    def set(
        self,
        cache_type: str,
        cache_key: str,
        value: CacheValue,
        ttl: int | None = None,
    ) -> None:
        ttl_seconds = int(self._ttl.total_seconds()) if ttl is None else ttl
        now = self._clock()
        self._upsert_record(
            CacheRecord(
                cache_type=cache_type,
                cache_key=cache_key,
                value=value,
                created_at=now,
                expired_at=now + timedelta(seconds=ttl_seconds),
            )
        )

    def delete(self, cache_type: str, cache_key: str) -> None:
        self._delete_record(cache_type, cache_key)

    def _get_record(self, cache_type: str, cache_key: str) -> CacheRecord | None:
        raise NotImplementedError

    def _upsert_record(self, record: CacheRecord) -> None:
        raise NotImplementedError

    def _delete_record(self, cache_type: str, cache_key: str) -> None:
        raise NotImplementedError


class InMemoryCacheProvider(_RecordCacheProvider):
    """In-memory cache provider for tests."""

    def __init__(
        self,
        ttl_seconds: int = 3600,
        clock: CacheClock | None = None,
    ) -> None:
        super().__init__(ttl_seconds=ttl_seconds, clock=clock)
        self._records: dict[tuple[str, str], CacheRecord] = {}

    def _get_record(self, cache_type: str, cache_key: str) -> CacheRecord | None:
        record = self._records.get((cache_type, cache_record_id(cache_type, cache_key)))
        return deepcopy(record) if record is not None else None

    def _upsert_record(self, record: CacheRecord) -> None:
        self._records[(record.cache_type, cache_record_id(record.cache_type, record.cache_key))] = (
            deepcopy(record)
        )

    def _delete_record(self, cache_type: str, cache_key: str) -> None:
        self._records.pop((cache_type, cache_record_id(cache_type, cache_key)), None)


class CosmosCacheProvider(_RecordCacheProvider):
    """Cache provider backed by Azure Cosmos DB."""

    def __init__(
        self,
        client: CosmosClient,
        database_name: str,
        ttl_seconds: int,
        clock: CacheClock | None = None,
    ) -> None:
        super().__init__(ttl_seconds=ttl_seconds, clock=clock)
        self._database = client.create_database_if_not_exists(id=database_name)
        self._container = self._database.create_container_if_not_exists(
            id=CACHE_CONTAINER_NAME,
            partition_key=PartitionKey(path="/cacheType"),
        )

    def _get_record(self, cache_type: str, cache_key: str) -> CacheRecord | None:
        item_id = cache_record_id(cache_type, cache_key)
        try:
            item = cast(
                dict[str, Any],
                self._container.read_item(item=item_id, partition_key=cache_type),
            )
        except exceptions.CosmosResourceNotFoundError:
            return None
        return self._deserialize(item)

    def _upsert_record(self, record: CacheRecord) -> None:
        self._container.upsert_item(self._serialize(record))

    def _delete_record(self, cache_type: str, cache_key: str) -> None:
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
            "expiredAt": record.expired_at.isoformat(),
        }

    def _deserialize(self, item: dict[str, Any]) -> CacheRecord:
        created_at = datetime.fromisoformat(cast(str, item["createdAt"]))
        expired_at_value = item.get("expiredAt")
        expired_at = (
            datetime.fromisoformat(cast(str, expired_at_value))
            if isinstance(expired_at_value, str)
            else created_at + self._ttl
        )
        return CacheRecord(
            cache_type=cast(str, item["cacheType"]),
            cache_key=cast(str, item["cacheKey"]),
            value=cast(CacheValue, item["value"]),
            created_at=created_at,
            expired_at=expired_at,
        )


def build_cosmos_cache_provider(config: Any) -> CacheProvider:
    """Construct the default Cosmos-backed cache provider."""

    client = CosmosClient.from_connection_string(
        _cosmos_connection_string(config),
        connection_verify=_should_verify_connection(config),
    )
    return CosmosCacheProvider(
        client=client,
        database_name=_cosmos_database_name(config),
        ttl_seconds=_cache_ttl_seconds(config),
    )


def cache_record_id(cache_type: str, cache_key: str) -> str:
    """Build the deterministic cache record id."""

    digest = sha256(f"{cache_type}:{cache_key}".encode()).hexdigest()
    return f"sha256:{digest}"


def _is_expired(expired_at: datetime, now: datetime) -> bool:
    if expired_at.tzinfo is None:
        expired_at = expired_at.replace(tzinfo=UTC)
    return now >= expired_at


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _cache_ttl_seconds(config: Any) -> int:
    cache_settings = getattr(config, "cache", None)
    ttl = getattr(cache_settings, "ttl_default", None)
    if ttl is None:
        ttl = getattr(config, "crawler_cache_ttl_seconds", None)
    return int(ttl if ttl is not None else 3600)


def _cosmos_connection_string(config: Any) -> str:
    connection_strings = getattr(config, "connectionStrings", None)
    connection_string = getattr(connection_strings, "azCosmosDb", None)
    if connection_string is None:
        connection_string = getattr(config, "az_cosmosdb_connection_string", "")
    return str(connection_string)


def _cosmos_database_name(config: Any) -> str:
    database_name = getattr(config, "azCosmosDbDatabaseName", None)
    if database_name is None:
        database_name = getattr(config, "az_cosmosdb_database_name", "mediastudio")
    return str(database_name)


def _should_verify_connection(config: Any) -> bool:
    return str(getattr(config, "environment", "production")).lower() != "localhost"
