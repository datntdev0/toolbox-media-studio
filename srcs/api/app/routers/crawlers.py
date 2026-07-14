"""Crawler integration routes."""

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from app.core.dependencies import (
    CacheProviderDep,
    CrawlerQueueProviderDep,
    CurrentUser,
    FlareSolverrClientDep,
    JobRepositoryDep,
    SettingsDep,
)
from app.domain.crawlers import CrawlerListResponse, CrawlerMetadataResponse
from app.domain.requests import CrawlerJobCreateRequest
from app.domain.responses import CrawlerJobResponse
from app.providers.crawler_provider import (
    InvalidCrawlerUrlError,
    UnknownCrawlerError,
    list_crawler_summaries,
)
from app.services.crawler_job_service import CrawlerJobPublishError, create_crawler_job
from app.services.crawler_service import (
    CrawlerFetchError,
    CrawlerFetchTimeoutError,
    fetch_crawler_metadata,
)

router = APIRouter(prefix="/api/crawlers", tags=["crawlers"])


@router.get("", response_model=CrawlerListResponse)
def list_crawlers() -> CrawlerListResponse:
    """List supported crawlers."""

    return CrawlerListResponse(items=list_crawler_summaries())


@router.get("/{id}/metadata", response_model=CrawlerMetadataResponse)
def get_crawler_metadata(
    id: str,
    source_url: Annotated[str, Query(alias="url")],
    current_user: CurrentUser,
    settings: SettingsDep,
    cache_provider: CacheProviderDep,
    flaresolverr_client: FlareSolverrClientDep,
) -> CrawlerMetadataResponse:
    """Fetch novel metadata from a supported crawler source."""

    del current_user
    try:
        return fetch_crawler_metadata(
            crawler_id=id,
            source_url=source_url,
            settings=settings,
            cache_provider=cache_provider,
            flaresolverr_client=flaresolverr_client,
        )
    except UnknownCrawlerError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Crawler not found",
        ) from exc
    except InvalidCrawlerUrlError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except CrawlerFetchTimeoutError as exc:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Crawler upstream timed out",
        ) from exc
    except CrawlerFetchError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Crawler upstream failed",
        ) from exc


@router.post("/{id}/jobs", response_model=CrawlerJobResponse, status_code=status.HTTP_202_ACCEPTED)
def create_job(
    id: str,
    request: CrawlerJobCreateRequest,
    current_user: CurrentUser,
    job_repository: JobRepositoryDep,
    crawler_queue_provider: CrawlerQueueProviderDep,
) -> CrawlerJobResponse:
    """Create or reuse an asynchronous crawler job."""

    try:
        return create_crawler_job(
            crawler_id=id,
            request=request,
            created_by=current_user.id,
            repository=job_repository,
            queue_provider=crawler_queue_provider,
        )
    except UnknownCrawlerError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Crawler not found",
        ) from exc
    except InvalidCrawlerUrlError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except CrawlerJobPublishError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Crawler job could not be queued",
        ) from exc
