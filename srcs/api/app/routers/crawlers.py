from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from app.core.injection import (
    PollingQueuePublisherDep,
    ProviderCacheDep,
    ProviderProxyDep,
    config,
)
from app.core.security.authorization import SessionUser
from app.domain.crawlers import CrawlerListResponse, CrawlerMetadataResponse
from app.domain.requests import CrawlerJobCreateRequest
from app.providers.crawler_provider import (
    CrawlerFetchError,
    CrawlerFetchTimeoutError,
    InvalidCrawlerUrlError,
    UnknownCrawlerError,
    fetch_metadata,
    list_crawlers,
)

router = APIRouter(prefix="/api/crawlers", tags=["crawlers"])


@router.get("", response_model=CrawlerListResponse)
def list_crawlers_route() -> CrawlerListResponse:
    """List supported crawlers."""

    return CrawlerListResponse(items=list_crawlers())


@router.get("/{id}/metadata", response_model=CrawlerMetadataResponse)
def get_crawler_metadata_route(
    session_user: SessionUser,
    provider_cache: ProviderCacheDep,
    provider_proxy: ProviderProxyDep,
    id: str,
    source_url: Annotated[str, Query(alias="url")],
) -> CrawlerMetadataResponse:
    """Fetch novel metadata from a supported crawler source."""

    del session_user
    try:
        return fetch_metadata(
            crawler_id=id,
            source_url=source_url,
            cache_provider=provider_cache,
            proxy_provider=provider_proxy,
            config=config,
        )
    except UnknownCrawlerError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Crawler not found",
        ) from exc
    except InvalidCrawlerUrlError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
    except CrawlerFetchTimeoutError as exc:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Crawler source timed out",
        ) from exc
    except CrawlerFetchError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Crawler source could not be fetched",
        ) from exc

@router.post("/{id}/jobs", status_code=status.HTTP_201_CREATED)
def create_crawler_job_route(
    session_user: SessionUser,
    queue_publisher: PollingQueuePublisherDep,
    id: str,
    body: CrawlerJobCreateRequest,
):
    """Create a crawler job to fetch novel data from a supported crawler source."""

    message = queue_publisher.publish(
        "sample",
        {
            "schemaVersion": 1,
            "kind": "sample",
            "crawlerId": id,
            "url": body.url,
            "chapters": body.chapters or [],
            "createdBy": session_user.id,
        },
    )

    return message
