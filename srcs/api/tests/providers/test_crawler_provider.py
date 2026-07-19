"""Crawler registry tests."""

from dataclasses import dataclass
from datetime import UTC, datetime

import pytest

from app.domain.crawlers import CrawlerChapterResponse, CrawlerMetadataResponse
from app.providers.cache_provider import InMemoryCacheProvider
from app.providers.crawler_provider import (
    InvalidCrawlerUrlError,
    UnknownCrawlerError,
    fetch_chapter_content,
    get_crawler,
    list_crawlers,
    validate_chapter_url,
    validate_crawler_source,
)


@dataclass(slots=True)
class _ProxyResult:
    html: str


class _FakeProxyProvider:
    def __init__(self, responses: dict[str, str]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, int | None]] = []

    def get(self, url: str, max_timeout_ms: int | None = None) -> _ProxyResult:
        self.calls.append((url, max_timeout_ms))
        return _ProxyResult(self.responses[url])


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


def test_validate_novel543_chapter_url() -> None:
    source = validate_chapter_url("novel543", "https://WWW.NOVEL543.COM/0603625457/8096_1.html")

    assert source.crawler_id == "novel543"
    assert source.source_novel_id == "0603625457"
    assert source.source_url == "https://www.novel543.com/0603625457/8096_1.html"
    assert source.canonical_url == "https://www.novel543.com/0603625457/8096_1.html"


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


@pytest.mark.parametrize(
    "chapter_url",
    [
        "http://www.novel543.com/0603625457/8096_1.html",
        "https://example.com/0603625457/8096_1.html",
        "https://www.novel543.com/books/0603625457/8096_1.html",
        "https://www.novel543.com/abc/8096_1.html",
        "https://www.novel543.com/0603625457/dir",
        "https://www.novel543.com/0603625457/8096_1.html?utm_source=test",
        "https://www.novel543.com/0603625457/8096_1.html#content",
    ],
)
def test_validate_rejects_invalid_novel543_chapter_urls(chapter_url: str) -> None:
    with pytest.raises(InvalidCrawlerUrlError):
        validate_chapter_url("novel543", chapter_url)


def test_fetch_chapter_content_fetches_remaining_novel543_parts() -> None:
    first_url = "https://www.novel543.com/0603625457/8096_1.html"
    second_url = "https://www.novel543.com/0603625457/8096_1_2.html"
    cache_provider = InMemoryCacheProvider()
    proxy_provider = _FakeProxyProvider(
        {
            first_url: """
            <html><body>
              <h1>第1章 林神醫 (1/2)</h1>
              <div id="chaptercontent">
                大虞王朝，燕山城。<br>
                暴雪初降，城中百姓多受風寒。<br>
                溫馨提示: 請記得加入書架哦
              </div>
            </body></html>
            """,
            second_url: """
            <html><body>
              <h1>第1章 林神醫 (2/2)</h1>
              <div id="chaptercontent">
                只剩下他微弱綿長的呼吸聲。<br>
                “其實當個瞎子，倒也不錯！”<br>
                溫馨提示: 切勿掃碼和發送簡訊!
              </div>
            </body></html>
            """,
        }
    )

    response = fetch_chapter_content(
        crawler_id="novel543",
        chapter_url="https://WWW.NOVEL543.COM/0603625457/8096_1.html",
        cache_provider=cache_provider,
        proxy_provider=proxy_provider,
    )

    assert response.crawler_id == "novel543"
    assert response.novel_url == "https://www.novel543.com/0603625457/dir"
    assert response.chapter_url == first_url
    assert response.chapter_title == "第1章 林神醫"
    assert response.chapter_number == 1
    assert response.content == [
        "大虞王朝，燕山城。",
        "暴雪初降，城中百姓多受風寒。",
        "只剩下他微弱綿長的呼吸聲。",
        "“其實當個瞎子，倒也不錯！”",
    ]
    assert response.cached is False
    assert proxy_provider.calls == [(first_url, None), (second_url, None)]
    cached = cache_provider.get("crawler:novel543:content", first_url)
    assert isinstance(cached, dict)
    assert cached["content"] == response.content


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
