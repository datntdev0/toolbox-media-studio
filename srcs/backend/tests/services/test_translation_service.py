"""Translation service tests."""

from datetime import UTC, datetime

import pytest

from app.domain.novels import Novel, NovelStatus
from app.domain.translations import (
    Translation,
    TranslationConfiguration,
    TranslationStatus,
)
from app.repositories.novel_repository import InMemoryNovelRepository
from app.repositories.translation_repository import InMemoryTranslationRepository
from app.services.translation_service import (
    TranslationNovelNotFoundError,
    TranslationService,
)


def _novel(id: str = "novel-1") -> Novel:
    now = datetime.now(UTC)
    return Novel(
        id=id,
        title="Novel",
        description=None,
        cover_image_url=None,
        language="zh",
        author=None,
        tags=[],
        notes=None,
        status=NovelStatus.DRAFT,
        created_by="user-1",
        created_at=now,
        updated_by="user-1",
        updated_at=now,
    )


def _translation(
    *,
    status: TranslationStatus = TranslationStatus.NEEDS_SETUP,
) -> Translation:
    now = datetime.now(UTC)
    return Translation(
        id="translation-1",
        name="Vietnamese",
        novel_id="novel-1",
        target_language="vi",
        configuration=None,
        status=status,
        created_by="user-1",
        created_at=now,
        updated_by="user-1",
        updated_at=now,
    )


def _service() -> tuple[
    TranslationService,
    InMemoryTranslationRepository,
    InMemoryNovelRepository,
]:
    translations = InMemoryTranslationRepository()
    novels = InMemoryNovelRepository()
    novels.create(_novel())
    return TranslationService(translations, novels), translations, novels


def test_configuration_moves_setup_translation_to_ready_and_can_be_cleared() -> None:
    service, translations, _ = _service()
    created = service.create(_translation()).translation
    configuration = TranslationConfiguration(
        provider_id="openai",
        model_id="gpt-5-mini",
        global_prompt="Translate faithfully.",
    )

    ready = service.update(
        created.id,
        name=created.name,
        novel_id=created.novel_id,
        target_language=created.target_language,
        configuration=configuration,
        etag=created.etag,
        updated_by="user-2",
    ).translation
    assert ready.status == TranslationStatus.READY
    assert ready.configuration == configuration

    cleared = service.update(
        ready.id,
        name=ready.name,
        novel_id=ready.novel_id,
        target_language=ready.target_language,
        configuration=None,
        etag=ready.etag,
        updated_by="user-2",
    ).translation
    assert cleared.status == TranslationStatus.NEEDS_SETUP
    assert translations.get_by_id(cleared.id) == cleared


@pytest.mark.parametrize(
    "status",
    [
        TranslationStatus.RUNNING,
        TranslationStatus.COMPLETED,
        TranslationStatus.STOPPED,
        TranslationStatus.FAILED,
    ],
)
def test_configuration_preserves_active_and_terminal_status(
    status: TranslationStatus,
) -> None:
    service, translations, _ = _service()
    created = translations.create(_translation(status=status))

    updated = service.update(
        created.id,
        name=created.name,
        novel_id=created.novel_id,
        target_language=created.target_language,
        configuration=TranslationConfiguration("openai", "gpt-5", "Translate."),
        etag=created.etag,
        updated_by="user-2",
    ).translation
    assert updated.status == status


def test_create_and_update_require_a_live_novel() -> None:
    service, translations, _ = _service()
    missing = _translation()
    missing.novel_id = "missing"
    with pytest.raises(TranslationNovelNotFoundError):
        service.create(missing)

    created = translations.create(_translation())
    with pytest.raises(TranslationNovelNotFoundError):
        service.update(
            created.id,
            name=created.name,
            novel_id="missing",
            target_language=created.target_language,
            configuration=None,
            etag=created.etag,
            updated_by="user-2",
        )
