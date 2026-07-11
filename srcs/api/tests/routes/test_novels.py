"""Novel-management endpoint tests."""

from fastapi.testclient import TestClient

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
            "coverImageUrl": "https://example.com/cover.jpg",
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
    assert created_body["status"] == "draft"

    listed = client.get("/api/novels", headers=headers)
    assert listed.status_code == 200
    list_body = listed.json()
    assert len(list_body["items"]) == 1
    assert list_body["items"][0]["id"] == novel_id

    fetched = client.get(f"/api/novels/{novel_id}", headers=headers)
    assert fetched.status_code == 200
    assert fetched.json()["author"] == "Author One"

    updated = client.patch(
        f"/api/novels/{novel_id}",
        headers={**headers, "If-Match": etag},
        json={"title": "Updated Title", "status": "active"},
    )
    assert updated.status_code == 200
    updated_body = updated.json()
    assert updated_body["title"] == "Updated Title"
    assert updated_body["status"] == "active"

    deleted = client.delete(
        f"/api/novels/{novel_id}",
        headers={**headers, "If-Match": updated_body["etag"]},
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


def test_novel_update_with_stale_etag_returns_412(client: TestClient) -> None:
    token = _login(client)
    headers = _auth_headers(token)

    created = client.post("/api/novels", headers=headers, json={"title": "Concurrency Test"})
    assert created.status_code == 201
    body = created.json()
    novel_id = body["id"]
    etag = body["etag"]

    first_update = client.patch(
        f"/api/novels/{novel_id}",
        headers={**headers, "If-Match": etag},
        json={"notes": "updated once"},
    )
    assert first_update.status_code == 200

    stale_update = client.patch(
        f"/api/novels/{novel_id}",
        headers={**headers, "If-Match": etag},
        json={"notes": "updated twice"},
    )
    assert stale_update.status_code == 412
