"""Shared FastAPI dependencies."""

from typing import Annotated, cast

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.logging import LogManager
from app.core.security import JWTError, decode_access_token
from app.domain.users import User, UserRole, UserStatus
from app.providers.cache_provider import CacheProvider
from app.providers.queue_provider import QueueProvider
from app.repositories.job_repository import JobRepository
from app.repositories.novel_repository import NovelRepository
from app.repositories.user_repository import UserRepository
from app.services.crawler_service import FlareSolverrClientLike


_bearer_scheme = HTTPBearer(auto_error=False)


def get_user_repository(request: Request) -> UserRepository:
    """Resolve the configured user repository from app state."""

    repository = getattr(request.app.state, "user_repository", None)
    if repository is None:
        raise RuntimeError("User repository is not configured")
    return cast(UserRepository, repository)


UserRepositoryDep = Annotated[UserRepository, Depends(get_user_repository)]


def get_novel_repository(request: Request) -> NovelRepository:
    """Resolve the configured novel repository from app state."""

    repository = getattr(request.app.state, "novel_repository", None)
    if repository is None:
        raise RuntimeError("Novel repository is not configured")
    return cast(NovelRepository, repository)


NovelRepositoryDep = Annotated[NovelRepository, Depends(get_novel_repository)]


def get_cache_provider(request: Request) -> CacheProvider:
    """Resolve the configured cache provider from app state."""

    cache_provider = getattr(request.app.state, "cache_provider", None)
    if cache_provider is None:
        raise RuntimeError("Cache provider is not configured")
    return cast(CacheProvider, cache_provider)


CacheProviderDep = Annotated[CacheProvider, Depends(get_cache_provider)]


def get_job_repository(request: Request) -> JobRepository:
    """Resolve the configured job repository from app state."""

    repository = getattr(request.app.state, "job_repository", None)
    if repository is None:
        raise RuntimeError("Job repository is not configured")
    return cast(JobRepository, repository)


JobRepositoryDep = Annotated[JobRepository, Depends(get_job_repository)]


def get_crawler_queue_provider(request: Request) -> QueueProvider:
    """Resolve the crawler-job queue provider from app state."""

    provider = getattr(request.app.state, "crawler_queue_provider", None)
    if provider is None:
        raise RuntimeError("Crawler queue provider is not configured")
    return cast(QueueProvider, provider)


CrawlerQueueProviderDep = Annotated[QueueProvider, Depends(get_crawler_queue_provider)]


def get_flaresolverr_client(request: Request) -> FlareSolverrClientLike:
    """Resolve the configured FlareSolverr client from app state."""

    client = getattr(request.app.state, "flaresolverr_client", None)
    if client is None:
        raise RuntimeError("FlareSolverr client is not configured")
    return cast(FlareSolverrClientLike, client)


FlareSolverrClientDep = Annotated[FlareSolverrClientLike, Depends(get_flaresolverr_client)]

