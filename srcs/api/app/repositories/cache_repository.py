"""Cache repository contracts."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
from typing import Any, Protocol

CacheValue = str | dict[str, Any]


@dataclass(frozen=True, slots=True)
class CacheRecord:
    """Persisted cache record."""

    cache_type: str
    cache_key: str
    value: CacheValue
    created_at: datetime
    expired_at: datetime


class CacheRepository(Protocol):
    """Persistence contract for cache records."""

    def get(self, cache_type: str, cache_key: str) -> CacheRecord | None: ...

    def upsert(self, record: CacheRecord) -> None: ...

    def delete(self, cache_type: str, cache_key: str) -> None: ...


class InMemoryCacheRepository:
    """In-memory cache repository for tests."""

    def __init__(self) -> None:
        self._records: dict[tuple[str, str], CacheRecord] = {}

    def get(self, cache_type: str, cache_key: str) -> CacheRecord | None:
        record = self._records.get((cache_type, cache_record_id(cache_type, cache_key)))
        return deepcopy(record) if record is not None else None

    def upsert(self, record: CacheRecord) -> None:
        self._records[(record.cache_type, cache_record_id(record.cache_type, record.cache_key))] = (
            deepcopy(record)
        )

    def delete(self, cache_type: str, cache_key: str) -> None:
        self._records.pop((cache_type, cache_record_id(cache_type, cache_key)), None)


def cache_record_id(cache_type: str, cache_key: str) -> str:
    """Build the deterministic cache record id."""

    digest = sha256(f"{cache_type}:{cache_key}".encode()).hexdigest()
    return f"sha256:{digest}"
