"""Translation repository tests."""

from datetime import UTC, datetime
from typing import Any

import pytest

from app.domain.translations import (
    Translation,
    TranslationConfiguration,
    TranslationStatus,
)
from app.repositories.cosmosdb.cosmos_translation_repository import (
    TRANSLATIONS_CONTAINER_NAME,
    CosmosTranslationRepository,
)
from app.repositories.translation_repository import (
    InMemoryTranslationRepository,
    TranslationConflictError,
    TranslationContinuationTokenError,
)


def _translation(id: str) -> Translation:
    now = datetime.now(UTC)
    return Translation(
        id=id,
        name=id,
        novel_id="novel-1",
        target_language="vi",
        configuration=TranslationConfiguration("openai", "gpt-5-mini", "Translate."),
        status=TranslationStatus.READY,
        created_by="user-1",
        created_at=now,
        updated_by="user-1",
        updated_at=now,
    )


def test_in_memory_repository_paginates_and_enforces_etags() -> None:
    repository = InMemoryTranslationRepository()
    first = repository.create(_translation("translation-1"))
    repository.create(_translation("translation-2"))

    page = repository.list(1, None)
    assert len(page.items) == 1
    assert page.continuation_token == "1"
    assert len(repository.list(1, page.continuation_token).items) == 1

    with pytest.raises(TranslationContinuationTokenError):
        repository.list(1, "-1")

    first.name = "Changed"
    with pytest.raises(TranslationConflictError):
        repository.update(first, "stale")


class _FakeContainer:
    def __init__(self) -> None:
        self.read_partition_key: str | None = None

    def read_item(self, *, item: str, partition_key: str) -> dict[str, Any]:
        self.read_partition_key = partition_key
        return {
            **CosmosTranslationRepository._serialize(_translation(item)),
            "_etag": "etag-1",
        }


class _FakeDatabase:
    def __init__(self, container: _FakeContainer) -> None:
        self.container = container
        self.container_id: str | None = None
        self.partition_key: Any = None

    def create_container_if_not_exists(
        self,
        *,
        id: str,
        partition_key: Any,
    ) -> _FakeContainer:
        self.container_id = id
        self.partition_key = partition_key
        return self.container


class _FakeCosmosClient:
    def __init__(self, database: _FakeDatabase) -> None:
        self.database = database

    def create_database_if_not_exists(self, *, id: str) -> _FakeDatabase:
        assert id == "mediastudio"
        return self.database


def test_cosmos_repository_uses_translation_container_and_id_partition() -> None:
    container = _FakeContainer()
    database = _FakeDatabase(container)
    repository = CosmosTranslationRepository(  # type: ignore[arg-type]
        _FakeCosmosClient(database),
        "mediastudio",
    )

    loaded = repository.get_by_id("translation-1")
    assert loaded is not None
    assert loaded.configuration == TranslationConfiguration(
        "openai",
        "gpt-5-mini",
        "Translate.",
    )
    assert database.container_id == TRANSLATIONS_CONTAINER_NAME
    assert repr(database.partition_key) == "<PartitionKey [/id]>"
    assert container.read_partition_key == "translation-1"
