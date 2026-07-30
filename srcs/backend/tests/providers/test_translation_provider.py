"""Translation provider parsing tests."""

import pytest

from app.providers.translation_service_provider import (
    TranslationPreview,
    TranslationServiceProviderError,
    TranslationServiceProviderFactory,
    UnsupportedTranslationServiceProviderError,
    parse_translation_output,
)


def test_parse_translation_output_extracts_title_and_paragraphs() -> None:
    result = parse_translation_output(
        """```text
Title: The translated chapter
Content:
First paragraph.

Second paragraph.
```""",
        fallback_title="Original title",
    )

    assert result.title == "The translated chapter"
    assert result.content == ["First paragraph.", "Second paragraph."]


def test_parse_translation_output_extracts_xml_title_and_content() -> None:
    result = parse_translation_output(
        """<title>Translated title</title>
<content>First paragraph.

Second paragraph.</content>""",
        fallback_title="Original title",
    )

    assert result.title == "Translated title"
    assert result.content == ["First paragraph.", "Second paragraph."]


def test_parse_translation_output_uses_fallback_title_without_header() -> None:
    result = parse_translation_output(
        "Translated paragraph.",
        fallback_title="Original title",
    )

    assert result.title == "Original title"
    assert result.content == ["Translated paragraph."]


def test_parse_translation_output_rejects_empty_content() -> None:
    with pytest.raises(TranslationServiceProviderError):
        parse_translation_output("Title: Missing content\nContent:\n", fallback_title="Original")


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


def test_factory_rejects_an_unknown_provider() -> None:
    factory = TranslationServiceProviderFactory({})

    with pytest.raises(UnsupportedTranslationServiceProviderError):
        factory.get("unknown")
