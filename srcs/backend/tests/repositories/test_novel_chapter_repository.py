"""Novel chapter persistence contract tests."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.domain.novels import NovelBinding, NovelChapter
from app.repositories.cosmosdb.cosmos_novel_chapter_repository import (
    NOVEL_CHAPTERS_CONTAINER_NAME,
    CosmosNovelChapterRepository,
)
from app.repositories.cosmosdb.cosmos_novel_repository import CosmosNovelRepository


class FakeDatabase:
    def __init__(self) -> None:
        self.container_options: dict[str, Any] | None = None

    def create_container_if_not_exists(self, **kwargs: Any) -> object:
        self.container_options = kwargs
        return object()


class FakeCosmosClient:
    def __init__(self) -> None:
        self.database_name: str | None = None
        self.database = FakeDatabase()

    def create_database_if_not_exists(self, *, id: str) -> FakeDatabase:
        self.database_name = id
        return self.database


def test_cosmos_novel_chapter_container_name_and_partition_key_are_stable() -> None:
    client = FakeCosmosClient()

    CosmosNovelChapterRepository(client, "media-studio")  # type: ignore[arg-type]

    assert NOVEL_CHAPTERS_CONTAINER_NAME == "domain.novel_chapters"
    assert client.database_name == "media-studio"
    assert client.database.container_options is not None
    assert client.database.container_options["id"] == "domain.novel_chapters"
    assert repr(client.database.container_options["partition_key"]) == (
        "<PartitionKey [/novelId]>"
    )


def test_legacy_novel_document_defaults_to_unbound_with_no_chapters() -> None:
    now = datetime.now(UTC).isoformat()

    novel = CosmosNovelRepository._deserialize(
        {
            "id": "novel-1",
            "title": "Legacy novel",
            "description": None,
            "coverImageUrl": None,
            "language": None,
            "author": None,
            "tags": [],
            "notes": None,
            "status": "draft",
            "createdBy": "user-1",
            "createdAt": now,
            "updatedBy": "user-1",
            "updatedAt": now,
        }
    )

    assert novel.binding is None
    assert novel.chapter_count == 0


def test_novel_chapter_content_is_stored_in_the_cosmos_document() -> None:
    now = datetime.now(UTC)
    chapter = NovelChapter(
        id="chapter-1",
        novel_id="novel-1",
        scraping_task_id="task-1",
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

    document = CosmosNovelChapterRepository._serialize(chapter)
    restored = CosmosNovelChapterRepository._deserialize(document)

    assert document["content"] == ["First paragraph", "Second paragraph"]
    assert "contentBlobName" not in document
    assert restored.content == chapter.content


def test_novel_binding_persists_only_novel_specific_relationship_data() -> None:
    now = datetime.now(UTC)
    novel = CosmosNovelRepository._deserialize(
        {
            "id": "novel-1",
            "title": "Bound novel",
            "description": None,
            "coverImageUrl": None,
            "language": None,
            "author": None,
            "tags": [],
            "notes": None,
            "status": "draft",
            "binding": {
                "scrapingId": "scraping-1",
                "crawlerId": "legacy-crawler",
                "sourceUrl": "https://legacy.test",
                "title": "Legacy snapshot",
                "coverImageUrl": "https://legacy.test/cover.jpg",
                "sourceUpdatedAt": now.isoformat(),
                "boundAt": now.isoformat(),
                "lastSyncedAt": now.isoformat(),
                "progress": {"total": 10, "completed": 5},
            },
            "chapterCount": 0,
            "createdBy": "user-1",
            "createdAt": now.isoformat(),
            "updatedBy": "user-1",
            "updatedAt": now.isoformat(),
        }
    )

    assert novel.binding == NovelBinding(
        scraping_id="scraping-1",
        bound_at=now,
        last_synced_at=now,
    )
    assert set(CosmosNovelRepository._serialize(novel)["binding"]) == {
        "scrapingId",
        "boundAt",
        "lastSyncedAt",
    }
