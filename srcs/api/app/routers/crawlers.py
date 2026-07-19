from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from app.core.injection import ProviderCacheDep, ProviderProxyDep
from app.core.security.authorization import SessionUser
from app.domain.crawlers import (
    CrawlerChapterContentResponse,
    CrawlerListResponse,
    CrawlerMetadataResponse,
)
from app.providers.crawler_provider import (
    CrawlerFetchError,
    CrawlerFetchTimeoutError,
    InvalidCrawlerUrlError,
    UnknownCrawlerError,
    fetch_chapter_content,
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

@router.get("/{id}/chapter", response_model=CrawlerChapterContentResponse)
def get_crawler_chapter_route(
    session_user: SessionUser,
    provider_cache: ProviderCacheDep,
    provider_proxy: ProviderProxyDep,
    id: str,
    source_url: Annotated[str, Query(alias="url")],
) -> CrawlerChapterContentResponse:
    """Fetch chapter content from a supported crawler source."""

    del session_user
    try:
        return fetch_chapter_content(
            crawler_id=id,
            chapter_url=source_url,
            cache_provider=provider_cache,
            proxy_provider=provider_proxy,
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
