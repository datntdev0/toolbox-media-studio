"""Audio workspace queue handler tests."""

from copy import deepcopy
from datetime import UTC, datetime
from hashlib import sha256
from logging import getLogger

import pytest

from app.core.events.message_handler import QueueMessage
from app.core.realtime import RealtimeHub
from app.domain.novels import Novel, NovelChapter, NovelStatus
from app.domain.workspace_results import WorkspaceResult
from app.domain.workspaces import (
    Workspace,
    WorkspaceProgress,
    WorkspaceQueueResult,
    WorkspaceTask,
    WorkspaceTaskStatus,
    WorkspaceType,
)
from app.events.workspace_handler import WorkspaceTaskHandler, build_workspace_task_event
from app.repositories.novel_chapter_repository import InMemoryNovelChapterRepository
from app.repositories.novel_repository import InMemoryNovelRepository
from app.repositories.translation_repository import InMemoryTranslationRepository
from app.repositories.translation_result_repository import InMemoryTranslationResultRepository
from app.repositories.workspace_repository import InMemoryWorkspaceRepository
from app.repositories.workspace_result_repository import InMemoryWorkspaceResultRepository
from app.services.novel_language_service import NovelLanguageService


class RecordingWorkspaceResultRepository(InMemoryWorkspaceResultRepository):
    def __init__(self) -> None:
        super().__init__()
        self.snapshots: list[WorkspaceResult] = []

    def upsert(self, result: WorkspaceResult) -> WorkspaceResult:
        saved = super().upsert(result)
        self.snapshots.append(deepcopy(saved))
        return saved


def test_handler_hashes_and_persists_each_sentence() -> None:
    workspaces, results, languages, queued = _queued_workspace()
    sleeps: list[float] = []
    handler = WorkspaceTaskHandler(
        getLogger("test.workspace"),
        workspaces,
        results,
        languages,
        RealtimeHub(),
        sleeper=sleeps.append,
    )

    handler.handle(
        QueueMessage(
            id="message-1",
            content=build_workspace_task_event(
                queued.workspace,
                queued.tasks[0],
                refetch=False,
            ),
        )
    )

    expected = [
        sha256(sentence.encode("utf-8")).hexdigest()
        for sentence in ["First sentence", "Second sentence"]
    ]
    assert sleeps == [5, 5]
    assert [snapshot.content_key for snapshot in results.snapshots] == [
        [],
        [expected[0]],
        expected,
    ]
    result = results.get(queued.workspace.id, "chapter-1")
    assert result is not None
    assert result.content_key == expected
    completed = workspaces.get_by_id(queued.workspace.id)
    assert completed is not None
    assert completed.tasks[0].status == WorkspaceTaskStatus.COMPLETED
    assert completed.tasks[0].result_available is True

    requeued = workspaces.queue_tasks(
        completed.id,
        chapter_index_from=1,
        chapter_index_to=1,
        provider="foundry",
        voice="voice-1",
        force=False,
        etag=completed.etag,
    )
    reuse_sleeps: list[float] = []
    reuse_handler = WorkspaceTaskHandler(
        getLogger("test.workspace.reuse"),
        workspaces,
        results,
        languages,
        RealtimeHub(),
        sleeper=reuse_sleeps.append,
    )
    reuse_handler.handle(
        QueueMessage(
            id="message-2",
            content=build_workspace_task_event(
                requeued.workspace,
                requeued.tasks[0],
                refetch=False,
            ),
        )
    )
    assert reuse_sleeps == []
    assert len(results.snapshots) == 3


def test_handler_keeps_partial_result_and_marks_failure() -> None:
    workspaces, results, languages, queued = _queued_workspace()
    calls = 0

    def fail_second(_: float) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("mock TTS failure")

    handler = WorkspaceTaskHandler(
        getLogger("test.workspace"),
        workspaces,
        results,
        languages,
        RealtimeHub(),
        sleeper=fail_second,
    )
    with pytest.raises(RuntimeError, match="mock TTS failure"):
        handler.handle(
            QueueMessage(
                id="message-1",
                content=build_workspace_task_event(
                    queued.workspace,
                    queued.tasks[0],
                    refetch=True,
                ),
            )
        )

    partial = results.get(queued.workspace.id, "chapter-1")
    assert partial is not None
    assert len(partial.content_key) == 1
    failed = workspaces.get_by_id(queued.workspace.id)
    assert failed is not None
    assert failed.tasks[0].status == WorkspaceTaskStatus.FAILED
    assert failed.tasks[0].result_available is False


def _queued_workspace() -> tuple[
    InMemoryWorkspaceRepository,
    RecordingWorkspaceResultRepository,
    NovelLanguageService,
    WorkspaceQueueResult,
]:
    now = datetime.now(UTC)
    novels = InMemoryNovelRepository()
    chapters = InMemoryNovelChapterRepository()
    novels.create(
        Novel(
            id="novel-1",
            title="Novel",
            description=None,
            cover_image_url=None,
            language="en",
            author=None,
            tags=[],
            notes=None,
            status=NovelStatus.DRAFT,
            created_by="user-1",
            created_at=now,
            updated_by="user-1",
            updated_at=now,
        )
    )
    chapters.save(
        NovelChapter(
            id="chapter-1",
            novel_id="novel-1",
            scraping_task_id="chapter-1",
            title="Chapter 1",
            chapter_number=1,
            manifest_index=0,
            source_url="https://example.test/chapter-1",
            content=["First sentence", "Second sentence"],
            content_available=True,
            manually_edited=False,
            source_updated=False,
            source_removed=False,
            source_result_updated_at=now,
            created_at=now,
            updated_at=now,
        )
    )
    languages = NovelLanguageService(
        novels,
        chapters,
        InMemoryTranslationRepository(),
        InMemoryTranslationResultRepository(),
    )
    task = WorkspaceTask("chapter-1", "Chapter 1", 1, 0, now)
    workspace = Workspace(
        id="workspace-1",
        title="Audio",
        type=WorkspaceType.AUDIO,
        novel_id="novel-1",
        language="en",
        created_by="user-1",
        created_at=now,
        updated_by="user-1",
        updated_at=now,
        tasks=[task],
        progress=WorkspaceProgress.from_tasks([task]),
    )
    workspaces = InMemoryWorkspaceRepository()
    created = workspaces.create(workspace)
    queued = workspaces.queue_tasks(
        created.id,
        chapter_index_from=1,
        chapter_index_to=1,
        provider="foundry",
        voice="voice-1",
        force=False,
        etag=created.etag,
    )
    return workspaces, RecordingWorkspaceResultRepository(), languages, queued
