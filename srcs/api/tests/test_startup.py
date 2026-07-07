"""Startup behavior tests."""

from __future__ import annotations

import pytest

from app.core.config import Settings


def test_cosmos_connection_verification_is_disabled_for_localhost(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Local development should bypass Cosmos TLS verification only for localhost."""

    calls: list[dict[str, object]] = []

    class _FakeCosmosClient:
        @staticmethod
        def from_connection_string(conn_str: str, **kwargs: object) -> object:
            calls.append({"conn_str": conn_str, **kwargs})

            class _Client:
                @staticmethod
                def get_database_account() -> None:
                    return None

            return _Client()

    monkeypatch.setattr("app.core.startup_checks.CosmosClient", _FakeCosmosClient)

    from app.core.startup_checks import _check_cosmos

    _check_cosmos(
        Settings(
            admin_email="admin@example.com",
            admin_password="change-me",
            jwt_signing_key="test-signing-key",
            az_cosmosdb_connection_string="AccountEndpoint=https://localhost:8081/;AccountKey=test;",
            az_storage_blob_connection_string="UseDevelopmentStorage=true",
            az_storage_queue_connection_string="UseDevelopmentStorage=true",
            environment="localhost",
        )
    )

    assert calls[0]["connection_verify"] is False
