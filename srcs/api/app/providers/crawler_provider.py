"""Crawler provider and source URL validation."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from re import Pattern
from urllib.parse import urlsplit, urlunsplit

from app.domain.crawlers import (
    CrawlerChapterContentResponse,
    CrawlerChapterResponse,
    CrawlerMetadataResponse,
    CrawlerSource,
    CrawlerSummaryResponse,
)
from app.providers.cache_provider import CACHE_TYPE_PREFIX_CRAWLER, CacheProvider
from app.providers.crawler_parser_novel543 import (
    Novel543ParseError,
    ParsedChapterContent,
    ParsedNovelMetadata,
    _is_chapter_url,
    parse_novel543_chapter,
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
_CACHE_KIND_CONTENT = "content"
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


def validate_novel_url(crawler_id: str, source_url: str) -> CrawlerSource:
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


validate_crawler_source = validate_novel_url


def validate_chapter_url(crawler_id: str, chapter_url: str) -> CrawlerSource:
    """Validate and canonicalize a chapter URL for the requested crawler."""

    crawler = get_crawler(crawler_id)
    try:
        parsed = urlsplit(chapter_url)
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

    match = re.fullmatch(r"/(?P<source_novel_id>[0-9]+)/(?P<chapter_slug>[^/]+\.html)", parsed.path)
    if match is None:
        raise InvalidCrawlerUrlError(
            f"{crawler.name} chapter URLs must point to a numeric novel chapter HTML path"
        )

    source_novel_id = match.group("source_novel_id")
    canonical_url = f"{crawler.scheme}://{host}{parsed.path}"
    novel_url = _novel_url(crawler, host, source_novel_id)
    if not _is_chapter_url(canonical_url, novel_url, source_novel_id):
        raise InvalidCrawlerUrlError(
            f"{crawler.name} chapter URLs must point to a numeric novel chapter HTML path"
        )

    return CrawlerSource(
        crawler_id=crawler.id,
        source_url=canonical_url,
        canonical_url=canonical_url,
        source_novel_id=source_novel_id,
    )


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


def get_cached_chapter_content(
    cache_provider: CacheProvider,
    crawler_source: CrawlerSource,
) -> CrawlerChapterContentResponse | None:
    """Return cached chapter content if available, otherwise None."""

    content_cache_type = _cache_type(crawler_source.crawler_id, _CACHE_KIND_CONTENT)
    cache_key = crawler_source.canonical_url

    cached_content = cache_provider.get(content_cache_type, cache_key)

    if cached_content is not None:
        if not isinstance(cached_content, dict):
            raise CrawlerFetchError("Cached crawler chapter content has an invalid shape")
        return CrawlerChapterContentResponse.model_validate(cached_content).model_copy(
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
    use_cache: bool = True,
) -> CrawlerMetadataResponse:
    """Fetch, parse, cache, and return crawler metadata."""

    source = validate_novel_url(crawler_id, source_url)
    if use_cache:
        cached_metadata = get_cached_metadata(cache_provider, source)
        if cached_metadata is not None:
            return cached_metadata

    html_cache_type = _cache_type(source.crawler_id, _CACHE_KIND_HTML)
    metadata_cache_type = _cache_type(source.crawler_id, _CACHE_KIND_METADATA)
    cache_key = source.canonical_url

    html = get_cached_html(cache_provider, source) if use_cache else None
    html_from_cache = html is not None
    if html is None:
        html = _fetch_html(source.canonical_url, proxy_provider)
        cache_provider.set(html_cache_type, cache_key, html)

    parsed = _parse_metadata(source, html)
    response = _to_metadata_response(
        crawler_id=source.crawler_id,
        source_url=source.canonical_url,
        parsed=parsed,
        cached=html_from_cache,
        fetched_at=datetime.now(UTC),
    )
    cache_provider.set(metadata_cache_type, cache_key, response.model_dump(mode="json"))
    return response


def fetch_chapter_content(
    crawler_id: str,
    chapter_url: str,
    cache_provider: CacheProvider,
    proxy_provider: ProxyProvider,
    use_cache: bool = True,
) -> CrawlerChapterContentResponse:
    """Fetch, parse, cache, and return crawler chapter content."""

    source = validate_chapter_url(crawler_id, chapter_url)
    if use_cache:
        cached_content = get_cached_chapter_content(cache_provider, source)
        if cached_content is not None:
            return cached_content

    html_cache_type = _cache_type(source.crawler_id, _CACHE_KIND_HTML)
    content_cache_type = _cache_type(source.crawler_id, _CACHE_KIND_CONTENT)
    cache_key = source.canonical_url

    html = get_cached_html(cache_provider, source) if use_cache else None
    html_from_cache = html is not None
    if html is None:
        html = _fetch_html(source.canonical_url, proxy_provider)
        cache_provider.set(html_cache_type, cache_key, html)

    parsed = _parse_chapter_content(source, html)
    content = list(parsed.content)
    for part_url in _remaining_chapter_part_urls(source, parsed):
        part_source = validate_chapter_url(source.crawler_id, part_url)
        part_html = get_cached_html(cache_provider, part_source) if use_cache else None
        if part_html is None:
            part_html = _fetch_html(part_source.canonical_url, proxy_provider)
            cache_provider.set(html_cache_type, part_source.canonical_url, part_html)
        part = _parse_chapter_content(part_source, part_html)
        content.extend(part.content)

    parsed = ParsedChapterContent(
        source_novel_id=parsed.source_novel_id,
        url=parsed.url,
        title=parsed.title,
        chapter_number=parsed.chapter_number,
        content=content,
        part_number=parsed.part_number,
        part_count=parsed.part_count,
    )

    response = _to_chapter_content_response(
        crawler_id=source.crawler_id,
        chapter_url=source.canonical_url,
        parsed=parsed,
        cached=html_from_cache,
        fetched_at=datetime.now(UTC),
    )
    cache_provider.set(content_cache_type, cache_key, response.model_dump(mode="json"))
    return response


def _fetch_html(canonical_url: str, proxy_provider: ProxyProvider) -> str:
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


def _parse_chapter_content(source: CrawlerSource, html: str) -> ParsedChapterContent:
    match source.crawler_id:
        case NOVEL543_CRAWLER.id:
            try:
                return parse_novel543_chapter(
                    html=html,
                    canonical_url=source.canonical_url,
                    source_novel_id=source.source_novel_id,
                )
            except Novel543ParseError as exc:
                raise CrawlerFetchError("Crawler HTML could not be parsed") from exc
        case _:
            raise UnknownCrawlerError(f"Unknown crawler: {source.crawler_id}")


def _to_metadata_response(
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


def _to_chapter_content_response(
    crawler_id: str,
    chapter_url: str,
    parsed: ParsedChapterContent,
    cached: bool,
    fetched_at: datetime,
) -> CrawlerChapterContentResponse:
    return CrawlerChapterContentResponse(
        crawler_id=crawler_id,
        novel_url=_novel_url_from_source(crawler_id, chapter_url, parsed.source_novel_id),
        chapter_url=chapter_url,
        chapter_title=parsed.title,
        chapter_number=parsed.chapter_number,
        content=parsed.content,
        cached=cached,
        fetched_at=fetched_at,
    )


def _remaining_chapter_part_urls(
    source: CrawlerSource,
    parsed: ParsedChapterContent,
) -> list[str]:
    if parsed.part_number is None or parsed.part_count is None:
        return []
    if parsed.part_number >= parsed.part_count:
        return []
    return [
        _chapter_part_url(source.canonical_url, source_part=parsed.part_number, target_part=part)
        for part in range(parsed.part_number + 1, parsed.part_count + 1)
    ]


def _chapter_part_url(chapter_url: str, *, source_part: int, target_part: int) -> str:
    parsed = urlsplit(chapter_url)
    path_without_extension = parsed.path.removesuffix(".html")
    source_suffix = f"_{source_part}"
    if source_part > 1 and path_without_extension.endswith(source_suffix):
        path_without_extension = path_without_extension[: -len(source_suffix)]
    next_path = f"{path_without_extension}_{target_part}.html"
    return urlunsplit((parsed.scheme, parsed.netloc, next_path, "", ""))


def _novel_url_from_source(crawler_id: str, chapter_url: str, source_novel_id: str) -> str:
    crawler = get_crawler(crawler_id)
    parsed = urlsplit(chapter_url)
    host = parsed.hostname.lower() if parsed.hostname else crawler.hosts[0]
    return _novel_url(crawler, host, source_novel_id)


def _novel_url(crawler: CrawlerDefinition, host: str, source_novel_id: str) -> str:
    return f"{crawler.scheme}://{host}/{source_novel_id}/dir"


def _cache_type(crawler_id: str, kind: str) -> str:
    return f"{CACHE_TYPE_PREFIX_CRAWLER}:{crawler_id}:{kind}"
