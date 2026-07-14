"""Crawler metadata use-cases."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Protocol

from app.core.config import Settings
from app.domain.crawlers import (
    CrawlerChapterResponse,
    CrawlerMetadataResponse,
)
from app.parsers.novel543_parser import ParsedNovelMetadata, parse_novel543_metadata
from app.providers.cache_provider import CacheProvider
from app.providers.crawler_provider import validate_source


class CrawlerFetchTimeoutError(Exception):
    """Raised when an upstream crawler fetch times out."""


class CrawlerFetchError(Exception):
    """Raised when an upstream crawler fetch fails."""


class FlareSolverrResultLike(Protocol):
    """Result shape needed from the FlareSolverr client."""

    html: str


class FlareSolverrClientLike(Protocol):
    """FlareSolverr client shape needed by crawler metadata."""

    def get(self, url: str, max_timeout_ms: int | None = None) -> FlareSolverrResultLike: ...


_HTML_CACHE_KIND = "html"
_METADATA_CACHE_KIND = "metadata"


def fetch_crawler_metadata(
    crawler_id: str,
    source_url: str,
    settings: Settings,
    cache_provider: CacheProvider,
    flaresolverr_client: FlareSolverrClientLike,
) -> CrawlerMetadataResponse:
    """Fetch, parse, cache, and return crawler metadata."""

    source = validate_source(crawler_id, source_url)

    metadata_cache_type = _cache_type(source.crawler_id, _METADATA_CACHE_KIND)
    html_cache_type = _cache_type(source.crawler_id, _HTML_CACHE_KIND)
    cache_key = source.canonical_url

    cached_metadata = cache_provider.get(metadata_cache_type, cache_key)
    if cached_metadata is not None:
        if not isinstance(cached_metadata, dict):
            raise CrawlerFetchError("Cached crawler metadata has an invalid shape")
        return CrawlerMetadataResponse.model_validate(cached_metadata).model_copy(
            update={"cached": True}
        )

    html = cache_provider.get(html_cache_type, cache_key)
    if html is not None and not isinstance(html, str):
        raise CrawlerFetchError("Cached crawler HTML has an invalid shape")
    html_from_cache = html is not None
    if html is None:
        html = _fetch_html(source.canonical_url, settings, flaresolverr_client)
        cache_provider.set(html_cache_type, cache_key, html)

    parsed = parse_novel543_metadata(
        html=html,
        canonical_url=source.canonical_url,
        source_novel_id=source.source_novel_id,
    )
    response = _to_response(
        crawler_id=source.crawler_id,
        source_url=source.canonical_url,
        parsed=parsed,
        cached=html_from_cache,
        fetched_at=datetime.now(UTC),
    )
    cache_provider.set(
        metadata_cache_type,
        cache_key,
        response.model_dump(mode="json"),
    )
    return response


def _cache_type(crawler_id: str, kind: str) -> str:
    return f"crawler:{crawler_id}:{kind}"


def _fetch_html(
    canonical_url: str,
    settings: Settings,
    flaresolverr_client: FlareSolverrClientLike,
) -> str:
    try:
        result = flaresolverr_client.get(
            canonical_url,
            max_timeout_ms=settings.flaresolverr_max_timeout_ms,
        )
    except TimeoutError as exc:
        raise CrawlerFetchTimeoutError("FlareSolverr request timed out") from exc
    except Exception as exc:
        if type(exc).__name__ == "FlareSolverrTimeoutError":
            raise CrawlerFetchTimeoutError("FlareSolverr request timed out") from exc
        raise CrawlerFetchError("FlareSolverr request failed") from exc

    if not result.html:
        raise CrawlerFetchError("FlareSolverr returned an empty HTML response")
    return result.html


def _to_response(
    crawler_id: str,
    source_url: str,
    parsed: ParsedNovelMetadata,
    cached: bool,
    fetched_at: datetime,
) -> CrawlerMetadataResponse:
    return CrawlerMetadataResponse(
        crawler_id=crawler_id,
        source_url=source_url,
        source_novel_id=parsed.source_novel_id,
        title=parsed.title,
        author=parsed.author,
        category=parsed.category,
        updated_date=parsed.updated_date,
        protagonists=parsed.protagonists,
        description=parsed.description,
        cover_image_url=parsed.cover_image_url,
        chapters=[
            CrawlerChapterResponse(
                title=chapter.title,
                url=chapter.url,
                chapter_number=chapter.chapter_number,
            )
            for chapter in parsed.chapters
        ],
        cached=cached,
        fetched_at=fetched_at,
    )
