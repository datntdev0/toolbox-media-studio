"""Application configuration tests."""

from __future__ import annotations

import importlib

import pytest

import app.core.config.app_config as app_config_module


def test_app_config_reads_azure_openai_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "FAST_AZURE_OPENAI_ENDPOINT",
        "https://example.openai.azure.com/openai/v1/",
    )
    monkeypatch.setenv("FAST_AZURE_OPENAI_API_KEY", "new-key")

    config = importlib.reload(app_config_module).AppConfig()

    assert config.azure_openai.endpoint == "https://example.openai.azure.com/openai/v1/"
    assert config.azure_openai.api_key == "new-key"
    assert not hasattr(config, "ai_foundry")


def test_app_config_reads_gemini_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FAST_GEMINI_API_KEY", "gemini-key")

    config = importlib.reload(app_config_module).AppConfig()

    assert config.gemini.api_key == "gemini-key"
