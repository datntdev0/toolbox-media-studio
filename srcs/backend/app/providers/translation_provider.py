"""AI providers used by synchronous translation previews."""

import re
from dataclasses import dataclass
from typing import Any

from app.core.config.app_config import AppConfig


class TranslationProviderError(Exception):
    """Raised when an AI translation provider cannot produce a result."""


class UnsupportedTranslationProviderError(TranslationProviderError):
    """Raised when the requested provider is not configured."""


@dataclass(frozen=True, slots=True)
class TranslationPreview:
    """Normalized translated chapter returned by an AI provider."""

    title: str
    content: list[str]


def translate_preview(
    *,
    provider: str,
    model: str,
    language: str,
    instruction: str,
    chapter_title: str,
    chapter_content: list[str],
    config: AppConfig,
) -> TranslationPreview:
    """Translate a chapter using the configured Azure AI Foundry deployment."""

    if provider.strip().lower() not in {
        "openai",
        "foundry",
        "azure-ai-foundry",
        "azure_ai_foundry",
    }:
        raise UnsupportedTranslationProviderError(f"Unsupported translation provider: {provider}")
    if not config.ai_foundry.api_key:
        raise TranslationProviderError("Azure AI Foundry API key is not configured")

    try:
        from openai import OpenAI

        client = OpenAI(base_url=config.ai_foundry.endpoint, api_key=config.ai_foundry.api_key)
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
            raise TranslationProviderError("AI Foundry returned an empty translation")
        return parse_translation_output(output, fallback_title=chapter_title)
    except TranslationProviderError:
        raise
    except Exception as exc:
        raise TranslationProviderError("Azure AI Foundry translation failed") from exc


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
        raise TranslationProviderError("AI Foundry returned an invalid translation")
    return TranslationPreview(title=title, content=content)


def _strip_code_fence(value: str) -> str:
    return _code_fence.sub("", value).strip()


_title_marker = re.compile(r"^\s*Title\s*:\s*(.+?)\s*$", re.MULTILINE | re.IGNORECASE)
_content_marker = re.compile(r"^\s*Content\s*:\s*\n?", re.MULTILINE | re.IGNORECASE)
_xml_title_marker = re.compile(r"<title>\s*(.*?)\s*</title>", re.DOTALL | re.IGNORECASE)
_xml_content_marker = re.compile(r"<content>\s*(.*?)\s*</content>", re.DOTALL | re.IGNORECASE)
_paragraph_splitter = re.compile(r"\r?\n\s*\r?\n")
_code_fence = re.compile(r"^```(?:text|markdown)?\s*|\s*```$", re.IGNORECASE)
