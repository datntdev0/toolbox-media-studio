"""Workspace-management endpoint tests."""

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


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _create_novel(client: TestClient, headers: dict[str, str], title: str) -> dict[str, object]:
    response = client.post(
        "/api/novels",
        headers=headers,
        json={"title": title, "language": "zh"},
    )
    assert response.status_code == 201
    return response.json()


def test_workspace_crud_allows_duplicates_and_live_novel_resolution(
    client: TestClient,
) -> None:
    token = _login(client)
    headers = _headers(token)
    first_novel = _create_novel(client, headers, "First Novel")
    second_novel = _create_novel(client, headers, "Second Novel")
    request = {
        "name": "Vietnamese translation",
        "kind": "translation",
        "novelId": first_novel["id"],
        "targetLanguage": "vi",
    }

    first = client.post("/api/workspaces", headers=headers, json=request)
    duplicate = client.post("/api/workspaces", headers=headers, json=request)
    assert first.status_code == 201
    assert duplicate.status_code == 201
    assert first.json()["id"] != duplicate.json()["id"]
    workspace = first.json()
    assert workspace["novel"]["title"] == "First Novel"
    assert workspace["status"] == "needs_setup"

    listed = client.get("/api/workspaces?kind=translation", headers=headers)
    assert listed.status_code == 200
    assert {item["id"] for item in listed.json()["items"]} == {
        first.json()["id"],
        duplicate.json()["id"],
    }

    updated_novel = client.put(
        f"/api/novels/{first_novel['id']}",
        headers=headers,
        json={"title": "Renamed First Novel", "etag": first_novel["etag"]},
    )
    assert updated_novel.status_code == 200
    fetched = client.get(f"/api/workspaces/{workspace['id']}", headers=headers)
    assert fetched.status_code == 200
    assert fetched.json()["novel"]["title"] == "Renamed First Novel"

    updated = client.put(
        f"/api/workspaces/{workspace['id']}",
        headers=headers,
        json={
            "name": "English edition",
            "novelId": second_novel["id"],
            "targetLanguage": "en",
            "etag": workspace["etag"],
        },
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "English edition"
    assert updated.json()["novelId"] == second_novel["id"]
    assert updated.json()["targetLanguage"] == "en"
    assert updated.json()["novel"]["title"] == "Second Novel"

    deleted = client.delete(f"/api/workspaces/{workspace['id']}", headers=headers)
    assert deleted.status_code == 204
    assert client.get(f"/api/workspaces/{workspace['id']}", headers=headers).status_code == 404


def test_workspace_operations_are_not_restricted_to_creator(client: TestClient) -> None:
    admin_token = _login(client)
    admin_headers = _headers(admin_token)
    novel = _create_novel(client, admin_headers, "Shared Novel")
    workspace = client.post(
        "/api/workspaces",
        headers=admin_headers,
        json={
            "name": "Shared workspace",
            "kind": "translation",
            "novelId": novel["id"],
            "targetLanguage": "vi",
        },
    ).json()

    created_user = client.post(
        "/api/users",
        headers=admin_headers,
        json={
            "email": "workspace-member@example.com",
            "password": "member-password",
            "displayName": "Workspace Member",
        },
    )
    assert created_user.status_code == 201
    member_headers = _headers(
        _login(client, "workspace-member@example.com", "member-password")
    )

    listed = client.get("/api/workspaces", headers=member_headers)
    assert listed.status_code == 200
    assert any(item["id"] == workspace["id"] for item in listed.json()["items"])
    assert client.get(
        f"/api/workspaces/{workspace['id']}",
        headers=member_headers,
    ).status_code == 200

    updated = client.put(
        f"/api/workspaces/{workspace['id']}",
        headers=member_headers,
        json={
            "name": "Updated by member",
            "novelId": novel["id"],
            "targetLanguage": "ja",
            "etag": workspace["etag"],
        },
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "Updated by member"
    assert updated.json()["targetLanguage"] == "ja"

    deleted = client.delete(
        f"/api/workspaces/{workspace['id']}",
        headers=member_headers,
    )
    assert deleted.status_code == 204


def test_workspace_returns_null_for_deleted_bound_novel(client: TestClient) -> None:
    token = _login(client)
    headers = _headers(token)
    novel = _create_novel(client, headers, "Temporary Novel")
    workspace = client.post(
        "/api/workspaces",
        headers=headers,
        json={
            "name": "Orphanable workspace",
            "kind": "translation",
            "novelId": novel["id"],
            "targetLanguage": "fr",
        },
    ).json()

    assert client.delete(f"/api/novels/{novel['id']}", headers=headers).status_code == 204
    response = client.get(f"/api/workspaces/{workspace['id']}", headers=headers)
    assert response.status_code == 200
    assert response.json()["novel"] is None


def test_workspace_update_with_stale_etag_returns_412(client: TestClient) -> None:
    token = _login(client)
    headers = _headers(token)
    novel = _create_novel(client, headers, "Concurrency Novel")
    workspace = client.post(
        "/api/workspaces",
        headers=headers,
        json={
            "name": "Concurrency workspace",
            "kind": "translation",
            "novelId": novel["id"],
            "targetLanguage": "vi",
        },
    ).json()
    payload = {
        "name": "Updated once",
        "novelId": novel["id"],
        "targetLanguage": "en",
        "etag": workspace["etag"],
    }
    assert client.put(
        f"/api/workspaces/{workspace['id']}",
        headers=headers,
        json=payload,
    ).status_code == 200
    stale = client.put(
        f"/api/workspaces/{workspace['id']}",
        headers=headers,
        json={**payload, "name": "Updated twice"},
    )
    assert stale.status_code == 412
