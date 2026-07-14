"""Crawler endpoint and cache tests."""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from app.providers.cache_provider import RepositoryCacheProvider
from tests.conftest import TEST_ADMIN_EMAIL, TEST_ADMIN_PASSWORD, FakeFlareSolverrClient

SAMPLE_HTML = """
<html>
  <body>
    <img src="/cover.jpg" alt="瞎眼神醫，開局遇到聖女報恩">
    <h1>瞎眼神醫，開局遇到聖女報恩</h1>
    <div>作者： 十一條金魚 分類：奇幻 更新： 2025-07-31</div>
    <div>主角： 林牧,姬梧桐</div>
    <p>報恩，她是認真的！</p>
    <h3>瞎眼神醫，開局遇到聖女報恩...最新章節</h3>
    <ul>
      <li><a href="/0603625457/536.html">第536章 常回來看看（大結局）</a></li>
      <li><a href="/0603625457/535.html">第535章 心意</a></li>
    </ul>
    <h3>瞎眼神醫，開局遇到聖女報恩...全部章节</h3>
    <ul>
      <li><a href="/0603625457/1.html">第1章 故事開始</a></li>
      <li><a href="/0603625457/2.html">第2章 踏上旅程</a></li>
      <li><a href="/0603625457/535.html">第535章 心意</a></li>
      <li><a href="/0603625457/536.html">第536章 常回來看看（大結局）</a></li>
    </ul>
  </body>
</html>
"""


def _login(client: TestClient) -> str:
    response = client.post(
        "/auth/login",
        json={"email": TEST_ADMIN_EMAIL, "password": TEST_ADMIN_PASSWORD},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def _headers(client: TestClient) -> dict[str, str]:
    return {"Authorization": f"Bearer {_login(client)}"}


def _metadata_url(source_url: str = "https://www.novel543.com/0603625457/dir") -> str:
    return f"/api/crawlers/novel543/metadata?url={source_url}"


def test_list_crawlers_returns_novel543(client: TestClient) -> None:
    response = client.get("/api/crawlers")

    assert response.status_code == 200
    assert response.json() == {
        "items": [
            {
                "id": "novel543",
                "name": "Novel543",
                "hosts": ["www.novel543.com"],
                "metadataSupported": True,
            }
        ]
    }


def test_metadata_openapi_uses_id_path_parameter(client: TestClient) -> None:
    paths = client.get("/openapi.json").json()["paths"]
    operation = paths["/api/crawlers/{id}/metadata"]["get"]

    assert not any(path == "/api/crawlers/{crawler_id}/metadata" for path in paths)
    assert any(
        parameter["name"] == "id" and parameter["in"] == "path"
        for parameter in operation["parameters"]
    )


def test_metadata_requires_auth(client: TestClient) -> None:
    response = client.get(_metadata_url())

    assert response.status_code == 401


def test_metadata_rejects_unknown_crawler(client: TestClient) -> None:
    response = client.get(
        "/api/crawlers/unknown/metadata?url=https://www.novel543.com/0603625457/dir",
        headers=_headers(client),
    )

    assert response.status_code == 404


def test_metadata_rejects_invalid_novel543_urls(client: TestClient) -> None:
    headers = _headers(client)

    for source_url in [
        "http://www.novel543.com/0603625457/",
        "https://example.com/0603625457/",
        "https://www.novel543.com/books/0603625457/",
        "https://www.novel543.com/0603625457/",
    ]:
        response = client.get(_metadata_url(source_url), headers=headers)
        assert response.status_code == 422


def test_metadata_fetches_html_through_flaresolverr_on_cache_miss(
    client: TestClient,
    flaresolverr_client: FakeFlareSolverrClient,
) -> None:
    flaresolverr_client.html = SAMPLE_HTML

    response = client.get(_metadata_url(), headers=_headers(client))

    assert response.status_code == 200
    body = response.json()
    assert body["crawlerId"] == "novel543"
    assert body["sourceUrl"] == "https://www.novel543.com/0603625457/dir"
    assert body["sourceNovelId"] == "0603625457"
    assert body["title"] == "瞎眼神醫，開局遇到聖女報恩"
    assert body["author"] == "十一條金魚"
    assert body["category"] == "奇幻"
    assert body["updatedDate"] == "2025-07-31"
    assert body["protagonists"] == ["林牧", "姬梧桐"]
    assert body["description"] == "報恩，她是認真的！"
    assert body["coverImageUrl"] == "https://www.novel543.com/cover.jpg"
    assert [chapter["chapterNumber"] for chapter in body["chapters"]] == [1, 2, 535, 536]
    assert body["cached"] is False
    assert flaresolverr_client.calls == [("https://www.novel543.com/0603625457/dir", 60000)]


def test_metadata_uses_html_cache_without_fetching(
    client: TestClient,
    cache_provider: RepositoryCacheProvider,
    flaresolverr_client: FakeFlareSolverrClient,
) -> None:
    cache_provider.set(
        "crawler:novel543:html",
        "https://www.novel543.com/0603625457/dir",
        SAMPLE_HTML,
    )

    response = client.get(_metadata_url(), headers=_headers(client))

    assert response.status_code == 200
    assert response.json()["cached"] is True
    assert flaresolverr_client.calls == []


def test_metadata_uses_parsed_metadata_cache_without_fetching_or_reparsing(
    client: TestClient,
    cache_provider: RepositoryCacheProvider,
    flaresolverr_client: FakeFlareSolverrClient,
) -> None:
    cached: dict[str, Any] = {
        "crawler_id": "novel543",
        "source_url": "https://www.novel543.com/0603625457/dir",
        "source_novel_id": "0603625457",
        "title": "Cached Title",
        "author": None,
        "category": None,
        "updated_date": None,
        "protagonists": [],
        "description": None,
        "cover_image_url": None,
        "chapters": [],
        "cached": False,
        "fetched_at": "2026-07-11T00:00:00+00:00",
    }
    cache_provider.set(
        "crawler:novel543:metadata",
        "https://www.novel543.com/0603625457/dir",
        cached,
    )

    response = client.get(_metadata_url(), headers=_headers(client))

    assert response.status_code == 200
    assert response.json()["title"] == "Cached Title"
    assert response.json()["cached"] is True
    assert flaresolverr_client.calls == []


def test_metadata_maps_flaresolverr_timeout_to_504(
    client: TestClient,
    flaresolverr_client: FakeFlareSolverrClient,
) -> None:
    flaresolverr_client.exception = TimeoutError("slow")

    response = client.get(_metadata_url(), headers=_headers(client))

    assert response.status_code == 504


def test_metadata_maps_flaresolverr_bad_response_to_502(
    client: TestClient,
    flaresolverr_client: FakeFlareSolverrClient,
) -> None:
    flaresolverr_client.html = ""

    response = client.get(_metadata_url(), headers=_headers(client))

    assert response.status_code == 502
