"""Shared pytest fixtures."""

import pytest

ADMIN_EMAIL = "admin@example.com"
ADMIN_PASSWORD = "s3cret-pass"


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set required env vars before settings are constructed.

    Environment variables take priority over any local `.env` file in pydantic-settings,
    so these values are what the app sees during tests.
    """
    monkeypatch.setenv("ADMIN_EMAIL", ADMIN_EMAIL)
    monkeypatch.setenv("ADMIN_PASSWORD", ADMIN_PASSWORD)
    monkeypatch.setenv("JWT_SIGNING_KEY", "test-signing-key-please-ignore")
    monkeypatch.setenv("JWT_EXPIRE_MINUTES", "60")


@pytest.fixture
def client(_env: None):
    """A TestClient with a fresh app and cleared settings cache."""
    from fastapi.testclient import TestClient

    from app.core.config import get_settings
    from app.main import create_app

    get_settings.cache_clear()
    return TestClient(create_app())
