"""Crawler provider and source URL validation."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from re import Pattern
from typing import Any
from urllib.parse import urlsplit

from app.domain.crawlers import (
    CrawlerChapterResponse,
    CrawlerMetadataResponse,
    CrawlerSource,
    CrawlerSummaryResponse,
)
from app.providers.cache_provider import CacheProvider
from app.providers.crawler_parser_novel543 import (
    Novel543ParseError,
    ParsedNovelMetadata,
    parse_novel543_metadata,
)
from app.providers.proxy_service_provider import ProxyProvider


class UnknownCrawlerError(ValueError):
    """Raised when a crawler id is not registered."""


class InvalidCrawlerUrlError(ValueError):
    """Raised when a source URL does not match the crawler allowlist."""


class CrawlerFetchTimeoutError(Exception):
    """Raised when an upstream crawler fetch times out."""


class CrawlerFetchError(Exception):
    """Raised when an upstream crawler fetch or parse fails."""


@dataclass(frozen=True, slots=True)
class CrawlerDefinition:
    """Static crawler provider entry."""

    id: str
    name: str
    hosts: tuple[str, ...]
    metadata_supported: bool
    scheme: str
    path_pattern: Pattern[str]


NOVEL543_CRAWLER = CrawlerDefinition(
    id="novel543",
    name="Novel543",
    hosts=("www.novel543.com",),
    metadata_supported=True,
    scheme="https",
    path_pattern=re.compile(r"^/(?P<source_novel_id>[0-9]+)/dir$"),
)

_CACHE_KIND_HTML = "html"
_CACHE_KIND_METADATA = "metadata"
_CRAWLERS = {NOVEL543_CRAWLER.id: NOVEL543_CRAWLER}


def get_crawler(crawler_id: str) -> CrawlerDefinition:
    """Return a crawler definition or raise when it is unknown."""

    crawler = _CRAWLERS.get(crawler_id)
    if crawler is None:
        raise UnknownCrawlerError(f"Unknown crawler: {crawler_id}")
    return crawler


def list_crawlers() -> list[CrawlerSummaryResponse]:
    return [
        CrawlerSummaryResponse(
            id=crawler.id,
            name=crawler.name,
            hosts=crawler.hosts,
            metadata_supported=crawler.metadata_supported,
        )
        for crawler in list(_CRAWLERS.values())
    ]


def validate_source(crawler_id: str, source_url: str) -> CrawlerSource:
    """Validate and canonicalize a source URL for the requested crawler."""

    crawler = get_crawler(crawler_id)
    try:
        parsed = urlsplit(source_url)
        port = parsed.port
    except ValueError as exc:
        raise InvalidCrawlerUrlError("Source URL is malformed") from exc

    host = parsed.hostname.lower() if parsed.hostname else None
    if parsed.scheme.lower() != crawler.scheme:
        raise InvalidCrawlerUrlError(f"{crawler.name} URLs must use {crawler.scheme}")
    if host not in crawler.hosts or port is not None:
        raise InvalidCrawlerUrlError(f"{crawler.name} URLs must use an allowed host")
    if parsed.query or parsed.fragment:
        raise InvalidCrawlerUrlError(f"{crawler.name} URLs cannot include query or fragment parts")

    match = crawler.path_pattern.fullmatch(parsed.path)
    if match is None:
        raise InvalidCrawlerUrlError(
            f"{crawler.name} URLs must point to a numeric novel directory path ending in /dir"
        )

    source_novel_id = match.group("source_novel_id")
    canonical_url = f"{crawler.scheme}://{host}/{source_novel_id}/dir"
    return CrawlerSource(
        crawler_id=crawler.id,
        source_url=canonical_url,
        canonical_url=canonical_url,
        source_novel_id=source_novel_id,
    )


validate_crawler_source = validate_source


def get_cached_metadata(
    cache_provider: CacheProvider,
    crawler_source: CrawlerSource,
) -> CrawlerMetadataResponse | None:
    """Return cached metadata if available, otherwise None."""

    metadata_cache_type = _cache_type(crawler_source.crawler_id, _CACHE_KIND_METADATA)
    cache_key = crawler_source.canonical_url

    cached_metadata = cache_provider.get(metadata_cache_type, cache_key)

    if cached_metadata is not None:
        if not isinstance(cached_metadata, dict):
            raise CrawlerFetchError("Cached crawler metadata has an invalid shape")
        return CrawlerMetadataResponse.model_validate(cached_metadata).model_copy(
            update={"cached": True}
        )

    return None


def get_cached_html(cache_provider: CacheProvider, crawler_source: CrawlerSource) -> str | None:
    """Return cached source HTML if available, otherwise None."""

    html_cache_type = _cache_type(crawler_source.crawler_id, _CACHE_KIND_HTML)
    cached_html = cache_provider.get(html_cache_type, crawler_source.canonical_url)

    if cached_html is not None and not isinstance(cached_html, str):
        raise CrawlerFetchError("Cached crawler HTML has an invalid shape")

    return cached_html


def fetch_metadata(
    crawler_id: str,
    source_url: str,
    cache_provider: CacheProvider,
    proxy_provider: ProxyProvider,
    config: Any,
) -> CrawlerMetadataResponse:
    """Fetch, parse, cache, and return crawler metadata."""

    source = validate_source(crawler_id, source_url)
    cached_metadata = get_cached_metadata(cache_provider, source)
    if cached_metadata is not None:
        return cached_metadata

    html_cache_type = _cache_type(source.crawler_id, _CACHE_KIND_HTML)
    metadata_cache_type = _cache_type(source.crawler_id, _CACHE_KIND_METADATA)
    cache_key = source.canonical_url

    html = get_cached_html(cache_provider, source)
    html_from_cache = html is not None
    if html is None:
        html = _fetch_html(source.canonical_url, config, proxy_provider)
        cache_provider.set(html_cache_type, cache_key, html)

    parsed = _parse_metadata(source, html)
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


def _fetch_html(
    canonical_url: str,
    config: Any,
    proxy_provider: ProxyProvider,
) -> str:
    try:
        result = proxy_provider.get(canonical_url)
    except TimeoutError as exc:
        raise CrawlerFetchTimeoutError("Proxy request timed out") from exc
    except Exception as exc:
        if type(exc).__name__ == "FlareSolverrTimeoutError":
            raise CrawlerFetchTimeoutError("Proxy request timed out") from exc
        raise CrawlerFetchError("Proxy request failed") from exc

    if not result.html:
        raise CrawlerFetchError("Proxy returned an empty HTML response")
    return result.html


def _parse_metadata(source: CrawlerSource, html: str) -> ParsedNovelMetadata:
    match source.crawler_id:
        case NOVEL543_CRAWLER.id:
            try:
                return parse_novel543_metadata(
                    html=html,
                    canonical_url=source.canonical_url,
                    source_novel_id=source.source_novel_id,
                )
            except Novel543ParseError as exc:
                raise CrawlerFetchError("Crawler HTML could not be parsed") from exc
        case _:
            raise UnknownCrawlerError(f"Unknown crawler: {source.crawler_id}")


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


def _cache_type(crawler_id: str, kind: str) -> str:
    return f"crawler:{crawler_id}:{kind}"
