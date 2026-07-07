"""Startup behavior tests."""

from __future__ import annotations

import logging
from pathlib import Path

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

    monkeypatch.setattr("app.core.startup.CosmosClient", _FakeCosmosClient)

    from app.core.startup import _check_cosmos

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


def test_configure_logging_creates_file_handler(tmp_path: Path) -> None:
    """Logging should write to both console and file outputs."""

    from app.core.logging import LOGGER_NAME, configure_logging

    logger = logging.getLogger(LOGGER_NAME)
    logger.handlers.clear()
    if hasattr(logger, "_toolbox_configured"):
        delattr(logger, "_toolbox_configured")

    log_file = tmp_path / "api.log"
    configured_logger = configure_logging(
        Settings(
            admin_email="admin@example.com",
            admin_password="change-me",
            jwt_signing_key="test-signing-key",
            az_cosmosdb_connection_string="AccountEndpoint=https://localhost:8081/;AccountKey=test;",
            az_storage_blob_connection_string="UseDevelopmentStorage=true",
            az_storage_queue_connection_string="UseDevelopmentStorage=true",
            environment="localhost",
            log_file_path=str(log_file),
        )
    )

    configured_logger.info("test log line")

    assert log_file.exists()
    assert "test log line" in log_file.read_text(encoding="utf-8")
    assert len(configured_logger.handlers) == 2
