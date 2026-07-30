"""Translation-service providers and provider selection."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol

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
    """Translation service backed by a Microsoft Foundry deployment."""

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
        if not self._config.ai_foundry.api_key:
            raise TranslationServiceProviderError("Azure AI Foundry API key is not configured")

        try:
            from openai import OpenAI

            client = OpenAI(
                base_url=self._config.ai_foundry.endpoint,
                api_key=self._config.ai_foundry.api_key,
            )
            chapter_text = "\n\n".join(chapter_content)
            response: Any = client.responses.create(
                model=model,
                instructions=f"""
                You are a novel translator and editor. You're translating to {language}.
                Here are the global instructions for this translation:
                ---
                {instruction}
                ---
                Return formatting:
                ```
                <title>translated_title</title>
                <content>translated_content</content>
                ```
                """,
                input=f"""
                <title>{chapter_title}</title>
                <content>{chapter_text}</content>
                """,
            )
            output = getattr(response, "output_text", None)
            if not isinstance(output, str) or not output.strip():
                raise TranslationServiceProviderError("AI Foundry returned an empty translation")
            return parse_translation_output(output, fallback_title=chapter_title)
        except TranslationServiceProviderError:
            raise
        except Exception as exc:
            raise TranslationServiceProviderError("Azure AI Foundry translation failed") from exc


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


def parse_translation_output(output: str, *, fallback_title: str) -> TranslationPreview:
    """Parse the provider's ``Title``/``Content`` response into API fields."""

    normalized = output.strip()
    normalized = _strip_code_fence(normalized)
    xml_content_match = _xml_content_marker.search(normalized)
    if xml_content_match is not None:
        xml_title_match = _xml_title_marker.search(normalized)
        title = (
            xml_title_match.group(1).strip()
            if xml_title_match is not None
            else fallback_title
        )
        content_text = xml_content_match.group(1).strip()
    else:
        content_match = _content_marker.search(normalized)
        if content_match is None:
            title = fallback_title
            content_text = normalized
        else:
            header = normalized[: content_match.start()].strip()
            title_match = _title_marker.search(header)
            title = title_match.group(1).strip() if title_match else fallback_title
            content_text = normalized[content_match.end() :].strip()

    content_text = _strip_code_fence(content_text).strip()
    content = [
        paragraph.strip()
        for paragraph in _paragraph_splitter.split(content_text)
        if paragraph.strip()
    ]
    if not title or not content:
        raise TranslationServiceProviderError("AI Foundry returned an invalid translation")
    return TranslationPreview(title=title, content=content)


def _strip_code_fence(value: str) -> str:
    return _code_fence.sub("", value).strip()


_title_marker = re.compile(r"^\s*Title\s*:\s*(.+?)\s*$", re.MULTILINE | re.IGNORECASE)
_content_marker = re.compile(r"^\s*Content\s*:\s*\n?", re.MULTILINE | re.IGNORECASE)
_xml_title_marker = re.compile(r"<title>\s*(.*?)\s*</title>", re.DOTALL | re.IGNORECASE)
_xml_content_marker = re.compile(r"<content>\s*(.*?)\s*</content>", re.DOTALL | re.IGNORECASE)
_paragraph_splitter = re.compile(r"\r?\n\s*\r?\n")
_code_fence = re.compile(r"^```(?:text|markdown)?\s*|\s*```$", re.IGNORECASE)
