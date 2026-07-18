"""User-management endpoint tests."""

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


def test_seeded_admin_can_be_read_from_me(client: TestClient) -> None:
    token = _login(client)

    response = client.get("/auth/me", headers=_auth_headers(token))

    assert response.status_code == 200
    body = response.json()
    assert body["email"] == TEST_ADMIN_EMAIL
    assert body["status"] == "active"
    assert body["displayName"] == "Admin"


def test_admin_can_create_list_update_and_delete_user(client: TestClient) -> None:
    token = _login(client)
    headers = _auth_headers(token)

    created = client.post(
        "/api/users",
        headers=headers,
        json={
            "email": "member@example.com",
            "password": "member-password",
            "displayName": "Member User",
            "role": "member",
        },
    )
    assert created.status_code == 201
    created_body = created.json()
    user_id = created_body["id"]
    etag = created_body["etag"]
    assert created_body["email"] == "member@example.com"

    listed = client.get("/api/users", headers=headers)
    assert listed.status_code == 200
    list_body = listed.json()
    assert len(list_body["items"]) == 2

    fetched = client.get(f"/api/users/{user_id}", headers=headers)
    assert fetched.status_code == 200
    assert fetched.json()["displayName"] == "Member User"

    updated = client.patch(
        f"/api/users/{user_id}",
        headers=headers,
        json={"displayName": "Updated Member", "status": "inactive", "etag": etag},
    )
    assert updated.status_code == 200
    updated_body = updated.json()
    assert updated_body["displayName"] == "Updated Member"
    assert updated_body["status"] == "inactive"

    deleted = client.delete(
        f"/api/users/{user_id}",
        headers=headers,
    )
    assert deleted.status_code == 204

    missing = client.get(f"/api/users/{user_id}", headers=headers)
    assert missing.status_code == 404


def test_duplicate_email_returns_409(client: TestClient) -> None:
    token = _login(client)

    response = client.post(
        "/api/users",
        headers=_auth_headers(token),
        json={"email": TEST_ADMIN_EMAIL, "password": "whatever"},
    )

    assert response.status_code == 409


def test_non_admin_cannot_access_user_management(client: TestClient) -> None:
    admin_token = _login(client)
    admin_headers = _auth_headers(admin_token)
    created = client.post(
        "/api/users",
        headers=admin_headers,
        json={
            "email": "member@example.com",
            "password": "member-password",
            "displayName": "Member User",
        },
    )
    assert created.status_code == 201

    member_token = _login(client, email="member@example.com", password="member-password")
    response = client.get("/api/users", headers=_auth_headers(member_token))

    assert response.status_code == 403


def test_inactive_user_cannot_log_in(client: TestClient) -> None:
    token = _login(client)
    headers = _auth_headers(token)
    created = client.post(
        "/api/users",
        headers=headers,
        json={
            "email": "inactive@example.com",
            "password": "inactive-password",
            "status": "inactive",
        },
    )
    assert created.status_code == 201

    response = client.post(
        "/auth/login",
        json={"email": "inactive@example.com", "password": "inactive-password"},
    )

    assert response.status_code == 401
