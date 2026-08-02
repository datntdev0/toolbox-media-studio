"""Azure OpenAI translation provider tests."""

from __future__ import annotations

import sys
from types import SimpleNamespace
from typing import Any, cast

import pytest

from app.core.config.app_config import AppConfig
from app.providers.translation_service_provider import (
    MicrosoftFoundryServiceProvider,
    TranslationPreview,
    TranslationServiceProviderError,
    TranslationServiceProviderFactory,
    UnsupportedTranslationServiceProviderError,
    build_translation_service_provider_factory,
)


def _config(
    *,
    endpoint: str = "https://example.openai.azure.com/openai/v1/",
    api_key: str = "test-key",
) -> AppConfig:
    return cast(
        AppConfig,
        SimpleNamespace(azure_openai=SimpleNamespace(endpoint=endpoint, api_key=api_key)),
    )


def _install_fake_openai(
    monkeypatch: pytest.MonkeyPatch,
    *,
    parsed_fields: tuple[str, str] | None = (" Translated title ", "First.\n\nSecond."),
    refusal: str | None = None,
    choices: bool = True,
    parsed_value: object | None = None,
    exception: Exception | None = None,
) -> dict[str, Any]:
    calls: dict[str, Any] = {}

    class FakeCompletions:
        def parse(self, **kwargs: Any) -> Any:
            calls["parse"] = kwargs
            if exception is not None:
                raise exception
            if not choices:
                return SimpleNamespace(choices=[])
            if parsed_value is not None:
                parsed = parsed_value
            elif parsed_fields is None:
                parsed = None
            else:
                response_format = kwargs["response_format"]
                parsed = response_format(title=parsed_fields[0], content=parsed_fields[1])
            message = SimpleNamespace(parsed=parsed, refusal=refusal)
            return SimpleNamespace(choices=[SimpleNamespace(message=message)])

    class FakeOpenAI:
        def __init__(self, **kwargs: Any) -> None:
            calls["client"] = kwargs
            self.beta = SimpleNamespace(
                chat=SimpleNamespace(completions=FakeCompletions()),
            )

    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=FakeOpenAI))
    return calls


def _translate(provider: MicrosoftFoundryServiceProvider) -> TranslationPreview:
    return provider.translate(
        model="gpt-5-mini",
        language="Vietnamese",
        instruction="Keep character names unchanged.",
        chapter_title="Original title",
        chapter_content=["Source first.", "Source second."],
    )


def test_translate_uses_structured_output_and_normalizes_paragraphs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _install_fake_openai(
        monkeypatch,
        parsed_fields=(
            " Translated title ",
            " First line.\ncontinued. \n\n  Second paragraph.  \r\n\r\n",
        ),
    )

    result = _translate(MicrosoftFoundryServiceProvider(_config()))

    assert result == TranslationPreview(
        title="Translated title",
        content=["First line.\ncontinued.", "Second paragraph."],
    )
    assert calls["client"] == {
        "base_url": "https://example.openai.azure.com/openai/v1/",
        "api_key": "test-key",
    }
    request = calls["parse"]
    assert request["model"] == "gpt-5-mini"
    assert request["messages"][0]["role"] == "system"
    assert "Vietnamese" in request["messages"][0]["content"]
    assert "Keep character names unchanged." in request["messages"][0]["content"]
    assert request["messages"][1] == {
        "role": "user",
        "content": (
            "Title:\nOriginal title\n\nContent:\nSource first.\n\nSource second."
        ),
    }
    response_schema = request["response_format"].model_json_schema()
    assert response_schema["required"] == ["title", "content"]
    assert response_schema["additionalProperties"] is False


@pytest.mark.parametrize(
    ("endpoint", "api_key", "message"),
    [
        ("", "test-key", "Azure OpenAI endpoint is not configured"),
        (
            "https://example.openai.azure.com/openai/v1/",
            "",
            "Azure OpenAI API key is not configured",
        ),
    ],
)
def test_translate_rejects_missing_configuration(
    endpoint: str,
    api_key: str,
    message: str,
) -> None:
    provider = MicrosoftFoundryServiceProvider(_config(endpoint=endpoint, api_key=api_key))

    with pytest.raises(TranslationServiceProviderError, match=message):
        _translate(provider)


def test_translate_rejects_a_refusal(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_openai(monkeypatch, refusal="I cannot translate this request.")

    with pytest.raises(TranslationServiceProviderError, match="refused the translation"):
        _translate(MicrosoftFoundryServiceProvider(_config()))


def test_translate_rejects_missing_structured_output(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_openai(monkeypatch, parsed_fields=None)

    with pytest.raises(TranslationServiceProviderError, match="no structured translation"):
        _translate(MicrosoftFoundryServiceProvider(_config()))


@pytest.mark.parametrize(
    "parsed_fields",
    [("", "Translated content."), ("Translated title", "  \n\n ")],
)
def test_translate_rejects_empty_structured_fields(
    monkeypatch: pytest.MonkeyPatch,
    parsed_fields: tuple[str, str],
) -> None:
    _install_fake_openai(monkeypatch, parsed_fields=parsed_fields)

    with pytest.raises(TranslationServiceProviderError, match="invalid structured translation"):
        _translate(MicrosoftFoundryServiceProvider(_config()))


def test_translate_rejects_an_invalid_parsed_type(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_openai(monkeypatch, parsed_value={"title": "Title", "content": "Content"})

    with pytest.raises(TranslationServiceProviderError, match="invalid structured translation"):
        _translate(MicrosoftFoundryServiceProvider(_config()))


def test_translate_wraps_sdk_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_openai(monkeypatch, exception=RuntimeError("request failed"))

    with pytest.raises(TranslationServiceProviderError, match="translation failed") as error:
        _translate(MicrosoftFoundryServiceProvider(_config()))

    assert isinstance(error.value.__cause__, RuntimeError)


def test_factory_normalizes_and_selects_a_provider() -> None:
    class FakeTranslationServiceProvider:
        def translate(
            self,
            *,
            model: str,
            language: str,
            instruction: str,
            chapter_title: str,
            chapter_content: list[str],
        ) -> TranslationPreview:
            raise NotImplementedError

    provider = FakeTranslationServiceProvider()
    factory = TranslationServiceProviderFactory({"foundry": provider})

    assert factory.get(" FOUNDRY ") is provider


def test_default_factory_preserves_provider_aliases() -> None:
    factory = build_translation_service_provider_factory(_config())
    provider = factory.get("openai")

    assert factory.get("foundry") is provider
    assert factory.get("azure-ai-foundry") is provider
    assert factory.get("azure_ai_foundry") is provider


def test_factory_rejects_an_unknown_provider() -> None:
    factory = TranslationServiceProviderFactory({})

    with pytest.raises(UnsupportedTranslationServiceProviderError):
        factory.get("unknown")
