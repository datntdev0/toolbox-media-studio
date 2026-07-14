"""Application runtime dependency composition."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, cast

from fastapi import FastAPI

from app.core.config import Settings
from app.providers.cache_provider import CacheProvider, RepositoryCacheProvider
from app.providers.queue_provider import QueueProviderFactory, build_azure_queue_provider_factory
from app.repositories.job_repository import JobRepository
from app.repositories.novel_repository import NovelRepository
from app.repositories.user_repository import UserRepository
from app.services.crawler_service import FlareSolverrClientLike


class RuntimeConsumer(Protocol):
    """Minimal lifecycle contract for runtime consumers."""

    def start(self) -> None: ...

    def stop(self) -> None: ...


@dataclass(slots=True)
class ApplicationOverrides:
    """Optional dependencies supplied by tests and app factory callers."""

    user_repository: UserRepository | None = None
    novel_repository: NovelRepository | None = None
    job_repository: JobRepository | None = None
    cache_provider: CacheProvider | None = None
    flaresolverr_client: FlareSolverrClientLike | None = None
    queue_provider_factory: QueueProviderFactory | None = None
    crawler_consumer: RuntimeConsumer | None = None
    start_consumers: bool = True


class ApplicationRuntime:
    """Own application dependencies and background consumers."""

    def __init__(self, settings: Settings, overrides: ApplicationOverrides) -> None:
        self._settings = settings
        self._overrides = overrides
        self.user_repository = overrides.user_repository or _build_default_user_repository(settings)
        self.novel_repository = (
            overrides.novel_repository or _build_default_novel_repository(settings)
        )
        self.job_repository = overrides.job_repository or _build_default_job_repository(settings)
        self.cache_provider = overrides.cache_provider or _build_default_cache_provider(settings)
        self.flaresolverr_client = (
            overrides.flaresolverr_client or _build_default_flaresolverr_client(settings)
        )
        self.queue_provider_factory = (
            overrides.queue_provider_factory or build_azure_queue_provider_factory(settings)
        )
        self.crawler_consumer: RuntimeConsumer | None = overrides.crawler_consumer

    def ensure_queues(self) -> None:
        from app.consumers.crawler_queue_consumer import CrawlerQueueConsumer

        CrawlerQueueConsumer.ensure_queues(self.queue_provider_factory)

    def attach(self, app: FastAPI) -> None:
        from app.consumers.crawler_queue_consumer import CrawlerQueueConsumer

        app.state.user_repository = self.user_repository
        app.state.novel_repository = self.novel_repository
        app.state.job_repository = self.job_repository
        app.state.cache_provider = self.cache_provider
        app.state.flaresolverr_client = self.flaresolverr_client
        app.state.queue_provider_factory = self.queue_provider_factory
        app.state.crawler_queue_provider = CrawlerQueueConsumer.source_queue_provider(
            self.queue_provider_factory
        )

    def start(self) -> None:
        if not self._overrides.start_consumers:
            return
        if self.crawler_consumer is None:
            from app.consumers.crawler_queue_consumer import CrawlerQueueConsumer

            self.crawler_consumer = CrawlerQueueConsumer(
                job_repository=self.job_repository,
                queue_provider_factory=self.queue_provider_factory,
            )
        self.crawler_consumer.start()

    def stop(self) -> None:
        if self.crawler_consumer is not None:
            self.crawler_consumer.stop()


def _build_default_user_repository(settings: Settings) -> UserRepository:
    from app.repositories.cosmosdb.cosmos_user_repository import build_cosmos_user_repository

    return build_cosmos_user_repository(settings)


def _build_default_novel_repository(settings: Settings) -> NovelRepository:
    from app.repositories.cosmosdb.cosmos_novel_repository import build_cosmos_novel_repository

    return build_cosmos_novel_repository(settings)


def _build_default_job_repository(settings: Settings) -> JobRepository:
    from app.repositories.cosmosdb.cosmos_job_repository import build_cosmos_job_repository

    return build_cosmos_job_repository(settings)


def _build_default_cache_provider(settings: Settings) -> CacheProvider:
    from app.repositories.cosmosdb.cosmos_cache_repository import build_cosmos_cache_repository

    return RepositoryCacheProvider(
        repository=build_cosmos_cache_repository(settings),
        ttl_seconds=settings.crawler_cache_ttl_seconds,
    )


def _build_default_flaresolverr_client(settings: Settings) -> FlareSolverrClientLike:
    from app.providers.flaresolverr_provider import FlareSolverrHttpClient

    return cast(
        FlareSolverrClientLike,
        FlareSolverrHttpClient(base_url=settings.flaresolverr_base_url),
    )
