"""Scraping metadata preview route tests."""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from tests.conftest import TEST_ADMIN_EMAIL, TEST_ADMIN_PASSWORD


METADATA_HTML = """
<html><body>
  <img src="/cover.jpg" alt="Test Novel">
  <h1>Test Novel</h1>
  <div>作者： Test Author 分類：Fantasy 更新： 2026-07-23</div>
  <p>Test description</p>
  <h3>Test Novel 全部章节</h3>
  <ul><li><a href="/0603625457/1.html">Chapter 1</a></li></ul>
</body></html>
"""


def test_preview_returns_metadata_under_scrapings_route(
    client: TestClient,
    flaresolverr_client: Any,
) -> None:
    flaresolverr_client.html = METADATA_HTML
    token = _login(client)

    response = client.get(
        "/api/scrapings/preview",
        headers={"Authorization": f"Bearer {token}"},
        params={
            "crawlerId": "novel543",
            "sourceUrl": "https://www.novel543.com/0603625457/dir",
        },
    )

    assert response.status_code == 200
    assert response.json()["crawlerId"] == "novel543"
    assert response.json()["title"] == "Test Novel"


def test_preview_rejects_unknown_crawler(client: TestClient) -> None:
    token = _login(client)

    response = client.get(
        "/api/scrapings/preview",
        headers={"Authorization": f"Bearer {token}"},
        params={
            "crawlerId": "unknown",
            "sourceUrl": "https://www.novel543.com/0603625457/dir",
        },
    )

    assert response.status_code == 404


def _login(client: TestClient) -> str:
    response = client.post(
        "/auth/login",
        json={"email": TEST_ADMIN_EMAIL, "password": TEST_ADMIN_PASSWORD},
    )
    assert response.status_code == 200
    return response.json()["access_token"]
