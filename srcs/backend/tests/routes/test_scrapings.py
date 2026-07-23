"""Scraping route tests."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi.testclient import TestClient

from app.domain.scraping_results import ScrapingResult
from app.domain.scrapings import ScrapingTaskStatus
from app.repositories.scraping_repository import InMemoryScrapingRepository
from app.repositories.scraping_result_repository import InMemoryScrapingResultRepository
from tests.conftest import TEST_ADMIN_EMAIL, TEST_ADMIN_PASSWORD

METADATA_HTML = """
<html>
  <body>
    <img src="/cover.jpg" alt="Test Novel">
    <h1>Test Novel</h1>
    <div>作者： Test Author 分類：Fantasy 更新： 2026-07-23</div>
    <p>Test description</p>
    <h3>Test Novel 全部章节</h3>
    <ul>
      <li><a href="/0603625457/1.html">Chapter 1</a></li>
      <li><a href="/0603625457/2.html">Chapter 2</a></li>
    </ul>
  </body>
</html>
"""


def test_create_requires_auth_and_exact_request_fields(client: TestClient) -> None:
    unauthorized = client.post(
        "/api/scrapings",
        json={
            "crawlerId": "novel543",
            "sourceUrl": "https://www.novel543.com/0603625457/dir",
        },
    )
    token = _login(client)
    invalid = client.post(
        "/api/scrapings",
        headers=_headers(token),
        json={
            "crawlerId": "novel543",
            "sourceUrl": "https://www.novel543.com/0603625457/dir",
            "title": "Untrusted",
        },
    )

    assert unauthorized.status_code == 401
    assert invalid.status_code == 422


def test_create_persists_embedded_tasks_and_publishes_once(
    client: TestClient,
    flaresolverr_client: Any,
    scraping_repository: InMemoryScrapingRepository,
    queue_publisher: Any,
) -> None:
    flaresolverr_client.html = METADATA_HTML
    token = _login(client)
    payload = {
        "crawlerId": "novel543",
        "sourceUrl": "https://www.novel543.com/0603625457/dir",
    }

    first = client.post("/api/scrapings", headers=_headers(token), json=payload)
    second = client.post("/api/scrapings", headers=_headers(token), json=payload)

    assert first.status_code == 202
    assert first.headers["location"] == f"/api/scrapings/{first.json()['id']}"
    assert first.json()["reused"] is False
    assert first.json()["progress"] == {"total": 2, "completed": 0, "failed": 0}
    assert second.status_code == 202
    assert second.json()["id"] == first.json()["id"]
    assert second.json()["reused"] is True
    assert len(queue_publisher.messages) == 1
    assert queue_publisher.messages[0][0] == "scrapings"

    stored = scraping_repository.get(first.json()["id"], _admin_id(client, token))
    assert stored is not None
    assert [task.title for task in stored.tasks] == ["Chapter 1", "Chapter 2"]
    assert [task.manifest_index for task in stored.tasks] == [0, 1]


def test_list_and_detail_return_summaries_and_embedded_tasks(
    client: TestClient,
    flaresolverr_client: Any,
) -> None:
    flaresolverr_client.html = METADATA_HTML
    token = _login(client)
    created = _create(client, token)

    listed = client.get("/api/scrapings", headers=_headers(token))
    detail = client.get(
        f"/api/scrapings/{created['id']}",
        headers=_headers(token),
    )

    assert listed.status_code == 200
    assert len(listed.json()["items"]) == 1
    assert "tasks" not in listed.json()["items"][0]
    assert detail.status_code == 200
    assert detail.json()["metadata"]["title"] == "Test Novel"
    assert [task["title"] for task in detail.json()["tasks"]] == [
        "Chapter 1",
        "Chapter 2",
    ]
    assert all(task["resultAvailable"] is False for task in detail.json()["tasks"])


def test_result_endpoint_reads_one_completed_task_result(
    client: TestClient,
    flaresolverr_client: Any,
    scraping_repository: InMemoryScrapingRepository,
    scraping_result_repository: InMemoryScrapingResultRepository,
) -> None:
    flaresolverr_client.html = METADATA_HTML
    token = _login(client)
    created = _create(client, token)
    owner_id = _admin_id(client, token)
    scraping = scraping_repository.get(created["id"], owner_id)
    assert scraping is not None
    task = scraping.tasks[0]

    unavailable = client.get(
        f"/api/scrapings/{scraping.id}/results/{task.id}",
        headers=_headers(token),
    )
    assert unavailable.status_code == 409

    now = datetime.now(UTC)
    scraping_result_repository.upsert(
        ScrapingResult(
            id=task.id,
            scraping_id=scraping.id,
            task_id=task.id,
            title=task.title,
            chapter_number=task.chapter_number,
            content=["First", "Second"],
            created_at=now,
            updated_at=now,
        )
    )
    scraping_repository.update_task(
        scraping.id,
        owner_id,
        task.id,
        ScrapingTaskStatus.COMPLETED,
        attempts=1,
        error=None,
        result_available=True,
        completed_at=now,
        etag=scraping.etag,
    )

    response = client.get(
        f"/api/scrapings/{scraping.id}/results/{task.id}",
        headers=_headers(token),
    )

    assert response.status_code == 200
    assert response.json()["scrapingId"] == scraping.id
    assert response.json()["taskId"] == task.id
    assert response.json()["content"] == ["First", "Second"]


def test_openapi_uses_scraping_result_task_id_path_parameter(client: TestClient) -> None:
    operation = client.get("/openapi.json").json()["paths"][
        "/api/scrapings/{id}/results/{taskId}"
    ]["get"]

    assert {
        (parameter["name"], parameter["in"])
        for parameter in operation["parameters"]
    } >= {("id", "path"), ("taskId", "path")}


def _create(client: TestClient, token: str) -> dict[str, Any]:
    response = client.post(
        "/api/scrapings",
        headers=_headers(token),
        json={
            "crawlerId": "novel543",
            "sourceUrl": "https://www.novel543.com/0603625457/dir",
        },
    )
    assert response.status_code == 202
    return response.json()


def _login(client: TestClient) -> str:
    response = client.post(
        "/auth/login",
        json={"email": TEST_ADMIN_EMAIL, "password": TEST_ADMIN_PASSWORD},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def _admin_id(client: TestClient, token: str) -> str:
    response = client.get("/auth/me", headers=_headers(token))
    assert response.status_code == 200
    return response.json()["id"]


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}
