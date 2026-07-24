"""Cosmos ScrapingResult repository tests."""

from __future__ import annotations

from typing import Any

from app.repositories.cosmosdb.cosmos_scraping_result_repository import (
    CosmosScrapingResultRepository,
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


def test_delete_by_scraping_queries_and_deletes_partition_items() -> None:
    container = FakeContainer()
    repository = CosmosScrapingResultRepository.__new__(
        CosmosScrapingResultRepository
    )
    repository._container = container  # type: ignore[assignment]

    repository.delete_by_scraping("scraping-1")

    assert container.query is not None
    assert container.query["partition_key"] == "scraping-1"
    assert container.query["parameters"] == [
        {"name": "@scraping_id", "value": "scraping-1"}
    ]
    assert container.deleted == [
        ("task-1", "scraping-1"),
        ("task-2", "scraping-1"),
    ]
