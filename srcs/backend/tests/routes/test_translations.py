"""Translation-management endpoint tests."""

from typing import Any

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


def _create_novel(client: TestClient, headers: dict[str, str], title: str) -> dict[str, Any]:
    response = client.post(
        "/api/novels",
        headers=headers,
        json={"title": title, "language": "zh"},
    )
    assert response.status_code == 201
    return response.json()


def _create_translation(
    client: TestClient,
    headers: dict[str, str],
    novel_id: str,
    *,
    name: str = "Vietnamese translation",
    target_language: str = "vi",
) -> dict[str, Any]:
    response = client.post(
        "/api/translations",
        headers=headers,
        json={
            "name": name,
            "novelId": novel_id,
            "targetLanguage": target_language,
        },
    )
    assert response.status_code == 201
    return response.json()


def test_translation_crud_persists_configuration_and_allows_duplicates(
    client: TestClient,
) -> None:
    headers = _headers(_login(client))
    first_novel = _create_novel(client, headers, "First Novel")
    second_novel = _create_novel(client, headers, "Second Novel")

    first = _create_translation(client, headers, first_novel["id"])
    duplicate = _create_translation(client, headers, first_novel["id"])
    assert first["id"] != duplicate["id"]
    assert first["novel"]["title"] == "First Novel"
    assert first["status"] == "needs_setup"
    assert first["configuration"] is None
    assert "kind" not in first

    updated = client.put(
        f"/api/translations/{first['id']}",
        headers=headers,
        json={
            "name": "English edition",
            "novelId": second_novel["id"],
            "targetLanguage": "en",
            "configuration": {
                "providerId": "openai",
                "modelId": "gpt-5-mini",
                "globalPrompt": "Translate this literary chapter faithfully.",
            },
            "etag": first["etag"],
        },
    )
    assert updated.status_code == 200
    updated_body = updated.json()
    assert updated_body["name"] == "English edition"
    assert updated_body["novelId"] == second_novel["id"]
    assert updated_body["targetLanguage"] == "en"
    assert updated_body["novel"]["title"] == "Second Novel"
    assert updated_body["status"] == "ready"
    assert updated_body["configuration"] == {
        "providerId": "openai",
        "modelId": "gpt-5-mini",
        "globalPrompt": "Translate this literary chapter faithfully.",
    }

    fetched = client.get(f"/api/translations/{first['id']}", headers=headers)
    assert fetched.status_code == 200
    assert fetched.json()["configuration"] == updated_body["configuration"]

    listed = client.get("/api/translations", headers=headers)
    assert listed.status_code == 200
    listed_item = next(item for item in listed.json()["items"] if item["id"] == first["id"])
    assert listed_item["configuration"] == updated_body["configuration"]

    assert client.delete(f"/api/translations/{first['id']}", headers=headers).status_code == 204
    assert (
        client.get(f"/api/translations/{first['id']}", headers=headers).status_code == 404
    )


def test_translation_operations_are_not_restricted_to_creator(client: TestClient) -> None:
    admin_headers = _headers(_login(client))
    novel = _create_novel(client, admin_headers, "Shared Novel")
    translation = _create_translation(
        client,
        admin_headers,
        novel["id"],
        name="Shared translation",
    )

    created_user = client.post(
        "/api/users",
        headers=admin_headers,
        json={
            "email": "translation-member@example.com",
            "password": "member-password",
            "displayName": "Translation Member",
        },
    )
    assert created_user.status_code == 201
    member_headers = _headers(
        _login(client, "translation-member@example.com", "member-password")
    )

    listed = client.get("/api/translations", headers=member_headers)
    assert listed.status_code == 200
    assert any(item["id"] == translation["id"] for item in listed.json()["items"])

    updated = client.put(
        f"/api/translations/{translation['id']}",
        headers=member_headers,
        json={
            "name": "Updated by member",
            "novelId": novel["id"],
            "targetLanguage": "ja",
            "configuration": None,
            "etag": translation["etag"],
        },
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "Updated by member"
    assert updated.json()["targetLanguage"] == "ja"
    assert (
        client.delete(
            f"/api/translations/{translation['id']}",
            headers=member_headers,
        ).status_code
        == 204
    )


def test_translation_returns_null_for_deleted_bound_novel(client: TestClient) -> None:
    headers = _headers(_login(client))
    novel = _create_novel(client, headers, "Temporary Novel")
    translation = _create_translation(client, headers, novel["id"])

    assert client.delete(f"/api/novels/{novel['id']}", headers=headers).status_code == 204
    response = client.get(f"/api/translations/{translation['id']}", headers=headers)
    assert response.status_code == 200
    assert response.json()["novel"] is None


def test_translation_update_with_stale_etag_returns_412(client: TestClient) -> None:
    headers = _headers(_login(client))
    novel = _create_novel(client, headers, "Concurrency Novel")
    translation = _create_translation(client, headers, novel["id"])
    payload = {
        "name": "Updated once",
        "novelId": novel["id"],
        "targetLanguage": "en",
        "configuration": None,
        "etag": translation["etag"],
    }
    assert client.put(
        f"/api/translations/{translation['id']}",
        headers=headers,
        json=payload,
    ).status_code == 200
    stale = client.put(
        f"/api/translations/{translation['id']}",
        headers=headers,
        json={**payload, "name": "Updated twice"},
    )
    assert stale.status_code == 412


def test_translation_validation_missing_novel_and_legacy_routes(client: TestClient) -> None:
    headers = _headers(_login(client))
    missing_novel = client.post(
        "/api/translations",
        headers=headers,
        json={
            "name": "Missing novel",
            "novelId": "missing",
            "targetLanguage": "vi",
        },
    )
    assert missing_novel.status_code == 404
    invalid_token = client.get(
        "/api/translations?continuationToken=invalid",
        headers=headers,
    )
    assert invalid_token.status_code == 422
    assert client.get("/api/translations?continuationToken=-1", headers=headers).status_code == 422
    assert client.get("/api/workspaces", headers=headers).status_code == 404
    legacy_body = client.post(
        "/api/translations",
        headers=headers,
        json={
            "name": "Legacy body",
            "kind": "translation",
            "novelId": "missing",
            "targetLanguage": "vi",
        },
    )
    assert legacy_body.status_code == 422

    openapi = client.get("/openapi.json").json()
    assert all("Workspace" not in schema for schema in openapi["components"]["schemas"])


def test_translation_configuration_rejects_blank_values(client: TestClient) -> None:
    headers = _headers(_login(client))
    novel = _create_novel(client, headers, "Validation Novel")
    translation = _create_translation(client, headers, novel["id"])

    response = client.put(
        f"/api/translations/{translation['id']}",
        headers=headers,
        json={
            "name": translation["name"],
            "novelId": novel["id"],
            "targetLanguage": translation["targetLanguage"],
            "configuration": {
                "providerId": " ",
                "modelId": "gpt-5-mini",
                "globalPrompt": "Translate.",
            },
            "etag": translation["etag"],
        },
    )
    assert response.status_code == 422
