"""Translation queue handler tests."""

from datetime import UTC, datetime
from logging import getLogger
from typing import Any

from app.core.events.message_handler import QueueMessage
from app.core.realtime import RealtimeHub
from app.domain.novels import NovelChapter
from app.domain.translation_results import TranslationResult
from app.domain.translations import (
    Translation,
    TranslationConfiguration,
    TranslationProgress,
    TranslationStatus,
    TranslationTask,
    TranslationTaskStatus,
)
from app.events.translation_handler import (
    TranslationHandler,
    build_translation_event,
)
from app.providers.translation_service_provider import TranslationPreview
from app.repositories.novel_chapter_repository import InMemoryNovelChapterRepository
from app.repositories.translation_repository import InMemoryTranslationRepository
from app.repositories.translation_result_repository import (
    InMemoryTranslationResultRepository,
)


def test_handler_translates_source_content() -> None:
    now = datetime.now(UTC)
    translations = InMemoryTranslationRepository()
    results = InMemoryTranslationResultRepository()
    chapters = InMemoryNovelChapterRepository()
    chapters.save(
        NovelChapter(
            id="chapter-1",
            novel_id="novel-1",
            scraping_task_id="chapter-1",
            title="Chapter 1",
            chapter_number=1,
            manifest_index=0,
            source_url="https://example.test/chapter-1",
            content=["First paragraph", "Second paragraph"],
            content_available=True,
            manually_edited=False,
            source_updated=False,
            source_removed=False,
            source_result_updated_at=now,
            created_at=now,
            updated_at=now,
        )
    )
    task = TranslationTask(
        id="chapter-1",
        title="Chapter 1",
        chapter_number=1,
        manifest_index=0,
        source_chapter_updated_at=now,
    )
    created = translations.create(
        Translation(
            id="translation-1",
            name="Vietnamese",
            novel_id="novel-1",
            target_language="vi",
            configuration=TranslationConfiguration("openai", "gpt-5", "Translate faithfully."),
            status=TranslationStatus.READY,
            created_by="user-1",
            created_at=now,
            updated_by="user-1",
            updated_at=now,
            tasks=[task],
            progress=TranslationProgress.from_tasks([task]),
        )
    )
    queued = translations.queue_tasks(
        created.id,
        chapter_index_from=1,
        chapter_index_to=1,
        force=False,
        etag=created.etag,
    )
    calls: list[dict[str, Any]] = []

    class FakeTranslationServiceProvider:
        def translate(self, **kwargs: Any) -> TranslationPreview:
            calls.append(kwargs)
            return TranslationPreview("Translated chapter", ["Translated paragraph"])

    class FakeTranslationServiceProviderFactory:
        def get(self, provider_id: str) -> FakeTranslationServiceProvider:
            assert provider_id == "openai"
            return FakeTranslationServiceProvider()

    handler = TranslationHandler(
        getLogger("test.translation"),
        translations,
        results,
        chapters,
        RealtimeHub(),
        FakeTranslationServiceProviderFactory(),
    )

    handler.handle(
        QueueMessage(
            id="message-1",
            content=build_translation_event(
                queued.translation,
                queued.tasks[0],
                refetch=False,
            ),
        )
    )

    assert len(calls) == 1
    call = calls[0]
    assert call == {
        "model": "gpt-5",
        "language": "vi",
        "instruction": "Translate faithfully.",
        "chapter_title": "Chapter 1",
        "chapter_content": ["First paragraph", "Second paragraph"],
    }
    result = results.get(created.id, task.id)
    assert result is not None
    assert result.title == "Translated chapter"
    assert result.content == ["Translated paragraph"]
    completed = translations.get_by_id(created.id)
    assert completed is not None
    assert completed.tasks[0].status == TranslationTaskStatus.COMPLETED
    assert completed.tasks[0].result_available is True


def test_handler_reuses_existing_result_without_sleeping() -> None:
    now = datetime.now(UTC)
    translations = InMemoryTranslationRepository()
    results = InMemoryTranslationResultRepository()
    chapters = InMemoryNovelChapterRepository()
    task = TranslationTask(
        id="chapter-1",
        title="Chapter 1",
        chapter_number=1,
        manifest_index=0,
        source_chapter_updated_at=now,
        status=TranslationTaskStatus.COMPLETED,
        result_available=True,
        source_updated=True,
    )
    created = translations.create(
        Translation(
            id="translation-1",
            name="Vietnamese",
            novel_id="novel-1",
            target_language="vi",
            configuration=TranslationConfiguration("mock", "copy", "Copy."),
            status=TranslationStatus.COMPLETED,
            created_by="user-1",
            created_at=now,
            updated_by="user-1",
            updated_at=now,
            tasks=[task],
            progress=TranslationProgress.from_tasks([task]),
        )
    )
    results.upsert(
        TranslationResult(
            id=task.id,
            translation_id=created.id,
            task_id=task.id,
            title=task.title,
            chapter_number=task.chapter_number,
            content=["Existing"],
            created_at=now,
            updated_at=now,
        )
    )
    queued = translations.queue_tasks(
        created.id,
        chapter_index_from=1,
        chapter_index_to=1,
        force=False,
        etag=created.etag,
    )

    class UnexpectedTranslationServiceProvider:
        def translate(self, **_: Any) -> TranslationPreview:
            raise AssertionError("unexpected translation")

    class UnexpectedTranslationServiceProviderFactory:
        def get(self, _: str) -> UnexpectedTranslationServiceProvider:
            return UnexpectedTranslationServiceProvider()

    handler = TranslationHandler(
        getLogger("test.translation"),
        translations,
        results,
        chapters,
        RealtimeHub(),
        UnexpectedTranslationServiceProviderFactory(),
    )

    handler.handle(
        QueueMessage(
            id="message-1",
            content=build_translation_event(
                queued.translation,
                queued.tasks[0],
                refetch=False,
            ),
        )
    )

    completed = translations.get_by_id(created.id)
    assert completed is not None
    assert completed.tasks[0].status == TranslationTaskStatus.COMPLETED
    assert completed.tasks[0].source_updated is True
