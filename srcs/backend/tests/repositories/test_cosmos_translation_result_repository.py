"""Cosmos translation result repository tests."""

from typing import Any

from app.repositories.cosmosdb.cosmos_translation_result_repository import (
    CosmosTranslationResultRepository,
)


class FakeContainer:
    def __init__(self) -> None:
        self.query: dict[str, Any] | None = None
        self.deleted: list[tuple[str, str]] = []

    def query_items(self, **kwargs: Any) -> list[str]:
        self.query = kwargs
        return ["task-1", "task-2"]

    def delete_item(self, *, item: str, partition_key: str) -> None:
        self.deleted.append((item, partition_key))


def test_delete_by_translation_queries_and_deletes_partition_items() -> None:
    container = FakeContainer()
    repository = CosmosTranslationResultRepository.__new__(
        CosmosTranslationResultRepository
    )
    repository._container = container  # type: ignore[assignment]

    repository.delete_by_translation("translation-1")

    assert container.query is not None
    assert container.query["partition_key"] == "translation-1"
    assert container.query["parameters"] == [
        {"name": "@translation_id", "value": "translation-1"}
    ]
    assert container.deleted == [
        ("task-1", "translation-1"),
        ("task-2", "translation-1"),
    ]
