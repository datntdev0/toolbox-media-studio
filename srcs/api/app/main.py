"""FastAPI application factory."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.exception_handlers import register_exception_handlers
from app.core.logging import configure_logging
from app.core.runtime import ApplicationOverrides, RuntimeConsumer
from app.core.startup import build_lifespan
from app.providers.cache_provider import CacheProvider
from app.providers.queue_provider import QueueProviderFactory
from app.repositories.job_repository import JobRepository
from app.repositories.novel_repository import NovelRepository
from app.repositories.user_repository import UserRepository
from app.routers import auth, crawlers, health, novels, users
from app.services.crawler_service import FlareSolverrClientLike


def create_app(
    user_repository: UserRepository | None = None,
    novel_repository: NovelRepository | None = None,
    job_repository: JobRepository | None = None,
    cache_provider: CacheProvider | None = None,
    flaresolverr_client: FlareSolverrClientLike | None = None,
    queue_provider_factory: QueueProviderFactory | None = None,
    crawler_consumer: RuntimeConsumer | None = None,
    start_consumers: bool = True,
) -> FastAPI:
    """Build and configure the FastAPI application."""

    settings = get_settings()
    configure_logging(settings)

    app = FastAPI(
        title="Novel Media Studio API",
        version="0.1.0",
        summary="Domain API - authentication, user-management, and novel-management slices",
        lifespan=build_lifespan(
            settings,
            ApplicationOverrides(
                user_repository=user_repository,
                novel_repository=novel_repository,
                job_repository=job_repository,
                cache_provider=cache_provider,
                flaresolverr_client=flaresolverr_client,
                queue_provider_factory=queue_provider_factory,
                crawler_consumer=crawler_consumer,
                start_consumers=start_consumers,
            ),
        ),
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.cors_allowed_origin],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(app)

    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(users.router)
    app.include_router(novels.router)
    app.include_router(crawlers.router)

    return app


app = create_app()
