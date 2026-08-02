"""Novel-management endpoint tests."""

import json
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

from fastapi.testclient import TestClient

from app.domain.novels import NovelChapter
from app.repositories.novel_chapter_repository import InMemoryNovelChapterRepository
from tests.conftest import TEST_ADMIN_EMAIL, TEST_ADMIN_PASSWORD


def _login(
    client: TestClient,
    email: str = TEST_ADMIN_EMAIL,
    password: str = TEST_ADMIN_PASSWORD,
) -> str:
    response = client.post("/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return response.json()["access_token"]


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_user_can_create_list_update_and_delete_own_novel(client: TestClient) -> None:
    token = _login(client)
    headers = _auth_headers(token)

    created = client.post(
        "/api/novels",
        headers=headers,
        json={
            "title": "The First Novel",
            "description": "A test novel",
            "language": "en",
            "author": "Author One",
            "tags": ["fantasy", "test"],
            "notes": "Personal note",
        },
    )
    assert created.status_code == 201
    created_body = created.json()
    novel_id = created_body["id"]
    etag = created_body["etag"]
    assert created_body["title"] == "The First Novel"

    listed = client.get("/api/novels", headers=headers)
    assert listed.status_code == 200
    list_body = listed.json()
    assert len(list_body["items"]) == 1
    assert list_body["items"][0]["id"] == novel_id

    fetched = client.get(f"/api/novels/{novel_id}", headers=headers)
    assert fetched.status_code == 200
    assert fetched.json()["author"] == "Author One"

    updated = client.put(
        f"/api/novels/{novel_id}",
        headers=headers,
        json={"title": "Updated Title", "etag": etag},
    )
    assert updated.status_code == 200
    updated_body = updated.json()
    assert updated_body["title"] == "Updated Title"

    cleared = client.put(
        f"/api/novels/{novel_id}",
        headers=headers,
        json={
            "description": None,
            "language": None,
            "coverImageUrl": None,
            "etag": updated_body["etag"],
        },
    )
    assert cleared.status_code == 200
    assert cleared.json()["description"] is None
    assert cleared.json()["coverImageUrl"] is None
    assert cleared.json()["language"] is None

    deleted = client.delete(
        f"/api/novels/{novel_id}",
        headers=headers,
    )
    assert deleted.status_code == 204

    missing = client.get(f"/api/novels/{novel_id}", headers=headers)
    assert missing.status_code == 404


def test_user_can_only_see_their_own_novels(client: TestClient) -> None:
    admin_token = _login(client)
    admin_headers = _auth_headers(admin_token)

    created_user = client.post(
        "/api/users",
        headers=admin_headers,
        json={
            "email": "member@example.com",
            "password": "member-password",
            "displayName": "Member User",
        },
    )
    assert created_user.status_code == 201

    created_novel = client.post(
        "/api/novels",
        headers=admin_headers,
        json={"title": "Admin Novel"},
    )
    assert created_novel.status_code == 201
    novel_id = created_novel.json()["id"]

    member_token = _login(client, email="member@example.com", password="member-password")
    member_headers = _auth_headers(member_token)

    member_list = client.get("/api/novels", headers=member_headers)
    assert member_list.status_code == 200
    assert member_list.json()["items"] == []

    member_get = client.get(f"/api/novels/{novel_id}", headers=member_headers)
    assert member_get.status_code == 404


def test_novel_cover_image_url_is_accepted(client: TestClient) -> None:
    token = _login(client)
    headers = _auth_headers(token)

    created = client.post(
        "/api/novels",
        headers=headers,
        json={"title": "Cover URL", "coverImageUrl": "https://images.test/cover.jpg"},
    )
    assert created.status_code == 201
    assert created.json()["coverImageUrl"] == "https://images.test/cover.jpg"


def test_novel_cover_upload_updates_cover_url(client: TestClient) -> None:
    token = _login(client)
    headers = _auth_headers(token)
    created = client.post("/api/novels", headers=headers, json={"title": "Uploaded Cover"})
    assert created.status_code == 201

    uploaded = client.put(
        f"/api/novels/{created.json()['id']}/cover",
        headers=headers,
        files={"coverImage": ("cover.jpg", b"\xff\xd8\xffcover", "image/jpeg")},
    )

    assert uploaded.status_code == 200
    assert uploaded.json()["coverImageUrl"].endswith("/cover.jpg")


def test_novel_cover_upload_rejects_invalid_content(client: TestClient) -> None:
    token = _login(client)
    headers = _auth_headers(token)
    created = client.post("/api/novels", headers=headers, json={"title": "Invalid Cover"})
    assert created.status_code == 201

    uploaded = client.put(
        f"/api/novels/{created.json()['id']}/cover",
        headers=headers,
        files={"coverImage": ("cover.jpg", b"not a JPEG", "image/jpeg")},
    )

    assert uploaded.status_code == 422
    assert uploaded.json()["message"] == "Cover image content is invalid"
    assert isinstance(uploaded.json()["traceStack"], list)


def test_novel_update_with_stale_etag_returns_412(client: TestClient) -> None:
    token = _login(client)
    headers = _auth_headers(token)

    created = client.post("/api/novels", headers=headers, json={"title": "Concurrency Test"})
    assert created.status_code == 201
    body = created.json()
    novel_id = body["id"]
    etag = body["etag"]

    first_update = client.put(
        f"/api/novels/{novel_id}",
        headers=headers,
        json={"notes": "updated once", "etag": etag},
    )
    assert first_update.status_code == 200

    stale_update = client.put(
        f"/api/novels/{novel_id}",
        headers=headers,
        json={"notes": "updated twice", "etag": etag},
    )
    assert stale_update.status_code == 412


def test_novel_update_rejects_explicit_null_required_fields(client: TestClient) -> None:
    token = _login(client)
    headers = _auth_headers(token)

    created = client.post("/api/novels", headers=headers, json={"title": "Required fields"})
    assert created.status_code == 201
    novel_id = created.json()["id"]

    response = client.put(
        f"/api/novels/{novel_id}",
        headers=headers,
        json={"title": ""},
    )
    assert response.status_code == 422


def test_owner_can_export_novel_as_zip_with_metadata_and_ordered_chapters(
    client: TestClient,
    novel_chapter_repository: InMemoryNovelChapterRepository,
) -> None:
    token = _login(client)
    headers = _auth_headers(token)
    created = client.post(
        "/api/novels",
        headers=headers,
        json={
            "title": "Export/Novel",
            "description": "For offline reading",
            "coverImageUrl": "https://images.test/cover.jpg",
            "language": "en",
            "author": "Export Author",
            "tags": ["fantasy"],
            "notes": "Archive this",
        },
    )
    assert created.status_code == 201
    novel = created.json()
    now = datetime.now(UTC)
    novel_chapter_repository.save(
        _chapter(
            novel_id=novel["id"],
            id="chapter-b",
            title="Duplicate: Title",
            manifest_index=1,
            content=["Stale content must not be exported"],
            content_available=False,
            now=now,
        )
    )
    novel_chapter_repository.save(
        _chapter(
            novel_id=novel["id"],
            id="chapter-a",
            title="Duplicate/ Title",
            manifest_index=0,
            content=["First paragraph", "Second paragraph"],
            content_available=True,
            now=now,
        )
    )

    exported = client.get(f"/api/novels/{novel['id']}/export", headers=headers)

    assert exported.status_code == 200
    assert exported.headers["content-type"] == "application/zip"
    assert exported.headers["content-disposition"] == (
        'attachment; filename="Export_Novel.zip"; '
        "filename*=UTF-8''Export_Novel.zip"
    )
    with ZipFile(BytesIO(exported.content)) as archive:
        assert archive.namelist() == [
            "novel.json",
            "001 - Duplicate_ Title.txt",
            "002 - Duplicate_ Title_2.txt",
            "glossary-vi.template.md",
            "SKILL-vi.md",
        ]
        metadata = json.loads(archive.read("novel.json"))
        assert metadata == {
            "id": novel["id"],
            "title": "Export/Novel",
            "description": "For offline reading",
            "coverImageUrl": "https://images.test/cover.jpg",
            "language": "en",
            "author": "Export Author",
            "tags": ["fantasy"],
            "notes": "Archive this",
            "chapterCount": 0,
            "binding": None,
            "createdAt": novel["createdAt"],
            "updatedAt": novel["updatedAt"],
            "etag": novel["etag"],
        }
        assert archive.read("001 - Duplicate_ Title.txt") == b"First paragraph\n\nSecond paragraph"
        assert archive.read("002 - Duplicate_ Title_2.txt") == b""
        context_directory = Path(__file__).parents[2] / "app" / "skills" / "novel-context"
        assert archive.read("glossary-vi.template.md") == (
            context_directory / "glossary-vi.template.md"
        ).read_bytes()
        assert archive.read("SKILL-vi.md") == (context_directory / "SKILL-vi.md").read_bytes()


def test_novel_export_requires_authentication_and_ownership(client: TestClient) -> None:
    admin_token = _login(client)
    admin_headers = _auth_headers(admin_token)
    created = client.post("/api/novels", headers=admin_headers, json={"title": "Owner Novel"})
    assert created.status_code == 201

    unauthenticated = client.get(f"/api/novels/{created.json()['id']}/export")
    assert unauthenticated.status_code == 401

    user = client.post(
        "/api/users",
        headers=admin_headers,
        json={
            "email": "export-member@example.com",
            "password": "member-password",
            "displayName": "Export Member",
        },
    )
    assert user.status_code == 201
    member_headers = _auth_headers(
        _login(client, email="export-member@example.com", password="member-password")
    )

    non_owner = client.get(f"/api/novels/{created.json()['id']}/export", headers=member_headers)
    assert non_owner.status_code == 404


def test_novel_export_openapi_declares_binary_zip_response(client: TestClient) -> None:
    export_operation = client.get("/openapi.json").json()["paths"]["/api/novels/{id}/export"]["get"]

    assert export_operation["operationId"] == "export_novel"
    assert export_operation["responses"]["200"]["content"] == {
        "application/zip": {"schema": {"type": "string", "format": "binary"}}
    }


def _chapter(
    *,
    novel_id: str,
    id: str,
    title: str,
    manifest_index: int,
    content: list[str],
    content_available: bool,
    now: datetime,
) -> NovelChapter:
    return NovelChapter(
        id=id,
        novel_id=novel_id,
        scraping_task_id=id,
        title=title,
        chapter_number=manifest_index + 1,
        manifest_index=manifest_index,
        source_url=f"https://example.test/{id}",
        content=content,
        content_available=content_available,
        manually_edited=False,
        source_updated=False,
        source_removed=False,
        source_result_updated_at=None,
        created_at=now,
        updated_at=now,
    )
