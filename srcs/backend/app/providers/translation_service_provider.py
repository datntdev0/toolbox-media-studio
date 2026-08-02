"""Translation-service providers and provider selection."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict

from app.core.config.app_config import AppConfig


class TranslationServiceProviderError(Exception):
    """Raised when a translation service cannot produce a result."""


class UnsupportedTranslationServiceProviderError(TranslationServiceProviderError):
    """Raised when the requested translation service is unavailable."""


@dataclass(frozen=True, slots=True)
class TranslationPreview:
    """Normalized translated chapter returned by a translation service."""

    title: str
    content: list[str]


class _StructuredTranslation(BaseModel):
    """Structured chapter payload required from Azure OpenAI."""
    title: str
    content: str


class TranslationServiceProvider(Protocol):
    """Contract implemented by a concrete translation service."""

    def translate(
        self,
        *,
        model: str,
        language: str,
        instruction: str,
        chapter_title: str,
        chapter_content: list[str],
    ) -> TranslationPreview: ...


class MicrosoftFoundryServiceProvider:
    """Translation service backed by an Azure OpenAI deployment."""

    def __init__(self, config: AppConfig) -> None:
        self._config = config

    def translate(
        self,
        *,
        model: str,
        language: str,
        instruction: str,
        chapter_title: str,
        chapter_content: list[str],
    ) -> TranslationPreview:
        if not self._config.azure_openai.endpoint:
            raise TranslationServiceProviderError("Azure OpenAI endpoint is not configured")
        if not self._config.azure_openai.api_key:
            raise TranslationServiceProviderError("Azure OpenAI API key is not configured")

        try:
            from openai import OpenAI

            client = OpenAI(
                base_url=self._config.azure_openai.endpoint,
                api_key=self._config.azure_openai.api_key,
            )
            chapter_text = "\n".join(chapter_content)
            completion: Any = client.chat.completions.parse(
                model=model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            f"You are a novel translator and editor translating into {language}. "
                            "Translate both the chapter title and content faithfully. Preserve "
                            "paragraph boundaries in the content by separating paragraphs with a "
                            f"blank line. Follow these global instructions:\n\n{instruction}"
                        ),
                    },
                    {
                        "role": "user",
                        "content": f"Title:\n{chapter_title}\n\nContent:\n{chapter_text}",
                    },
                ],
                response_format=_StructuredTranslation,
            )
            choices = getattr(completion, "choices", None)
            if not choices:
                raise TranslationServiceProviderError("Azure OpenAI returned no translation choice")

            message = getattr(choices[0], "message", None)
            if message is None:
                raise TranslationServiceProviderError(
                    "Azure OpenAI returned no translation message"
                )
            if getattr(message, "refusal", None):
                raise TranslationServiceProviderError("Azure OpenAI refused the translation")

            parsed = getattr(message, "parsed", None)
            if parsed is None:
                raise TranslationServiceProviderError(
                    "Azure OpenAI returned no structured translation"
                )
            if not isinstance(parsed, _StructuredTranslation):
                raise TranslationServiceProviderError(
                    "Azure OpenAI returned an invalid structured translation"
                )
            return _to_translation_preview(parsed)
        except TranslationServiceProviderError:
            raise
        except Exception as exc:
            raise TranslationServiceProviderError("Azure OpenAI translation failed") from exc


class TranslationServiceProviderFactory:
    """Select a translation service using the provider configured by a user."""

    def __init__(self, providers: Mapping[str, TranslationServiceProvider]) -> None:
        self._providers = {key.strip().lower(): value for key, value in providers.items()}

    def get(self, provider_id: str) -> TranslationServiceProvider:
        provider = self._providers.get(provider_id.strip().lower())
        if provider is None:
            raise UnsupportedTranslationServiceProviderError(
                f"Unsupported translation provider: {provider_id}"
            )
        return provider


def build_translation_service_provider_factory(
    config: AppConfig,
) -> TranslationServiceProviderFactory:
    """Construct the translation-service provider factory."""

    foundry = MicrosoftFoundryServiceProvider(config)
    return TranslationServiceProviderFactory(
        {
            "openai": foundry,
            "foundry": foundry,
            "azure-ai-foundry": foundry,
            "azure_ai_foundry": foundry,
        }
    )


def _to_translation_preview(parsed: _StructuredTranslation) -> TranslationPreview:
    title = parsed.title.strip()
    content = _split_paragraphs(parsed.content)
    if not title or not content:
        raise TranslationServiceProviderError(
            "Azure OpenAI returned an invalid structured translation"
        )
    return TranslationPreview(title=title, content=content)


def _split_paragraphs(content: str) -> list[str]:
    paragraphs: list[str] = []
    paragraph_lines: list[str] = []
    for line in content.splitlines():
        if line.strip():
            paragraph_lines.append(line.strip())
        elif paragraph_lines:
            paragraphs.append("\n".join(paragraph_lines))
            paragraph_lines = []
    if paragraph_lines:
        paragraphs.append("\n".join(paragraph_lines))
    return paragraphs
