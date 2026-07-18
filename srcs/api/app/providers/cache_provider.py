"""Cache provider."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Protocol

from app.core.config.app_config import AppConfig
from app.repositories.cache_repository import CacheRecord, CacheRepository, CacheValue

CacheClock = Callable[[], datetime]


class CacheProvider(Protocol):
    """Generic cache contract."""

    def get(self, cache_type: str, cache_key: str) -> CacheValue | None: ...

    def set(self, cache_type: str, cache_key: str, value: CacheValue) -> None: ...

    def delete(self, cache_type: str, cache_key: str) -> None: ...


class RepositoryCacheProvider:
    """Cache provider backed by a cache repository."""

    def __init__(self, config: AppConfig, repository: CacheRepository) -> None:
        self._repository = repository
        self._ttl = timedelta(seconds=config.cache.ttl_default)
        self._clock = _utc_now

    def get(self, cache_type: str, cache_key: str) -> CacheValue | None:
        record = self._repository.get(cache_type, cache_key)
        if record is None:
            return None
        if _is_expired(record.created_at, self._ttl, self._clock()):
            self._repository.delete(cache_type, cache_key)
            return None
        return record.value

    def set(self, cache_type: str, cache_key: str, value: CacheValue, ttl: int = None) -> None:
        if ttl is None: ttl = int(self._ttl.total_seconds())
        self._repository.upsert(
            CacheRecord(
                cache_type=cache_type,
                cache_key=cache_key,
                value=value,
                created_at=self._clock(),
                expired_at=self._clock() + timedelta(seconds=ttl)
            )
        )

    def delete(self, cache_type: str, cache_key: str) -> None:
        self._repository.delete(cache_type, cache_key)


def _is_expired(created_at: datetime, ttl: timedelta, now: datetime) -> bool:
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=UTC)
    return now >= created_at + ttl


def _utc_now() -> datetime:
    return datetime.now(UTC)
