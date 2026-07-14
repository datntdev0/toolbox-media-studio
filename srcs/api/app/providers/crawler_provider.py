"""Crawler provider and source URL validation."""

from __future__ import annotations

import re
from dataclasses import dataclass
from re import Pattern
from urllib.parse import urlsplit

from app.domain.crawlers import CrawlerSource, CrawlerSummaryResponse


class UnknownCrawlerError(ValueError):
    """Raised when a crawler id is not registered."""


class InvalidCrawlerUrlError(ValueError):
    """Raised when a source URL does not match the crawler allowlist."""


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

_CRAWLERS = {NOVEL543_CRAWLER.id: NOVEL543_CRAWLER}


def list_crawlers() -> list[CrawlerDefinition]:
    """Return registered crawler definitions."""

    return list(_CRAWLERS.values())


def list_crawler_summaries() -> list[CrawlerSummaryResponse]:
    """Return registered crawler definitions as API summary models."""

    return [
        CrawlerSummaryResponse(
            id=crawler.id,
            name=crawler.name,
            hosts=list(crawler.hosts),
            metadata_supported=crawler.metadata_supported,
        )
        for crawler in list_crawlers()
    ]


def get_crawler(crawler_id: str) -> CrawlerDefinition:
    """Return a crawler definition or raise when it is unknown."""

    crawler = _CRAWLERS.get(crawler_id)
    if crawler is None:
        raise UnknownCrawlerError(f"Unknown crawler: {crawler_id}")
    return crawler


def validate_crawler_source(crawler_id: str, source_url: str) -> CrawlerSource:
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


def validate_source(crawler_id: str, source_url: str) -> CrawlerSource:
    """Validate and canonicalize a source URL for the requested crawler."""

    return validate_crawler_source(crawler_id, source_url)
