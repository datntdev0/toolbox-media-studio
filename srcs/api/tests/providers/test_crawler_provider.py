"""Crawler registry tests."""

from datetime import UTC, datetime

import pytest

from app.domain.crawlers import CrawlerChapterResponse, CrawlerMetadataResponse
from app.providers.crawler_provider import (
    InvalidCrawlerUrlError,
    UnknownCrawlerError,
    get_crawler,
    list_crawlers,
    validate_crawler_source,
)


def test_list_crawlers_includes_novel543() -> None:
    crawlers = list_crawlers()

    assert [crawler.id for crawler in crawlers] == ["novel543"]
    assert crawlers[0].hosts == ("www.novel543.com",)
    assert crawlers[0].metadata_supported is True


def test_validate_novel543_directory_url() -> None:
    source = validate_crawler_source("novel543", "https://www.novel543.com/0603625457/dir")

    assert source.crawler_id == "novel543"
    assert source.source_novel_id == "0603625457"
    assert source.source_url == "https://www.novel543.com/0603625457/dir"
    assert source.canonical_url == "https://www.novel543.com/0603625457/dir"


def test_validate_rejects_unknown_crawler() -> None:
    with pytest.raises(UnknownCrawlerError):
        get_crawler("unknown")


@pytest.mark.parametrize(
    "source_url",
    [
        "http://www.novel543.com/0603625457/",
        "https://example.com/0603625457/",
        "https://www.novel543.com/books/0603625457/",
        "https://www.novel543.com/abc/",
        "https://www.novel543.com/0603625457/?utm_source=test",
        "https://www.novel543.com/0603625457/",
        "https://www.novel543.com/0603625457/dir/",
        "https://www.novel543.com/0603625457/dir?utm_source=test",
    ],
)
def test_validate_rejects_invalid_novel543_urls(source_url: str) -> None:
    with pytest.raises(InvalidCrawlerUrlError):
        validate_crawler_source("novel543", source_url)


def test_crawler_metadata_response_uses_camel_case_aliases() -> None:
    response = CrawlerMetadataResponse(
        crawler_id="novel543",
        source_url="https://www.novel543.com/0603625457/dir",
        source_novel_id="0603625457",
        title="瞎眼神醫，開局遇到聖女報恩",
        protagonists=["林牧", "姬梧桐"],
        chapters=[
            CrawlerChapterResponse(
                title="第536章 常回來看看（大結局）",
                url="https://www.novel543.com/0603625457/536.html",
                chapter_number=536,
            )
        ],
        cached=False,
        fetched_at=datetime(2026, 7, 11, tzinfo=UTC),
    )

    payload = response.model_dump(mode="json", by_alias=True)

    assert payload["crawlerId"] == "novel543"
    assert payload["sourceUrl"] == "https://www.novel543.com/0603625457/dir"
    assert payload["sourceNovelId"] == "0603625457"
    assert payload["chapters"][0]["chapterNumber"] == 536
    assert payload["fetchedAt"] == "2026-07-11T00:00:00Z"
