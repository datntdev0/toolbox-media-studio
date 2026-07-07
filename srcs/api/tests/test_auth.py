"""Auth endpoint tests."""

from fastapi.testclient import TestClient

from tests.conftest import ADMIN_EMAIL, ADMIN_PASSWORD


def test_health(client: TestClient) -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_login_success_returns_token(client: TestClient) -> None:
    resp = client.post("/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert resp.status_code == 200
    body = resp.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]


def test_openapi_uses_http_bearer_security_scheme(client: TestClient) -> None:
    resp = client.get("/openapi.json")

    assert resp.status_code == 200
    schema = resp.json()
    assert schema["components"]["securitySchemes"]["HTTPBearer"]["type"] == "http"
    assert schema["components"]["securitySchemes"]["HTTPBearer"]["scheme"] == "bearer"


def test_login_wrong_password_is_401(client: TestClient) -> None:
    resp = client.post("/auth/login", json={"email": ADMIN_EMAIL, "password": "nope"})
    assert resp.status_code == 401


def test_login_unknown_email_is_401(client: TestClient) -> None:
    resp = client.post(
        "/auth/login", json={"email": "someone@else.com", "password": ADMIN_PASSWORD}
    )
    assert resp.status_code == 401


def test_me_with_valid_token(client: TestClient) -> None:
    login = client.post("/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    token = login.json()["access_token"]

    resp = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"]
    assert body["email"] == ADMIN_EMAIL
    assert body["role"] == "admin"
    assert body["status"] == "active"


def test_me_without_token_is_401(client: TestClient) -> None:
    resp = client.get("/auth/me")
    assert resp.status_code == 401


def test_me_with_bad_token_is_401(client: TestClient) -> None:
    resp = client.get("/auth/me", headers={"Authorization": "Bearer not-a-jwt"})
    assert resp.status_code == 401
