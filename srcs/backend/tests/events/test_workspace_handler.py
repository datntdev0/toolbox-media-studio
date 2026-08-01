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
from app.events.workspace_handler import (
    MICROSOFT_FOUNDRY_SPEECH_PROVIDER,
    WorkspaceTaskHandler,
    build_workspace_task_event,
)
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


class FakeSpeechProvider:
    def __init__(self, fail_at: int | None = None) -> None:
        self.calls: list[tuple[str, str]] = []
        self._fail_at = fail_at

    def synthesize(self, text: str, voice: str) -> bytes:
        call_index = len(self.calls)
        self.calls.append((text, voice))
        if call_index == self._fail_at:
            raise RuntimeError("mock TTS failure")
        return f"audio:{voice}:{text}".encode()


class FakeAudioBlobProvider:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, int, bytes]] = []

    def upload_audio(
        self,
        workspace_id: str,
        task_id: str,
        index: int,
        content: bytes,
    ) -> str:
        self.calls.append((workspace_id, task_id, index, content))
        return f"https://storage.test/{workspace_id}/{task_id}/{index}.wav"


def test_handler_hashes_and_persists_each_sentence() -> None:
    workspaces, results, languages, queued = _queued_workspace()
    speech = FakeSpeechProvider()
    blobs = FakeAudioBlobProvider()
    handler = WorkspaceTaskHandler(
        getLogger("test.workspace"),
        workspaces,
        results,
        languages,
        speech,
        blobs,
        RealtimeHub(),
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
    assert [snapshot.content_key for snapshot in results.snapshots] == [
        [],
        [expected[0]],
        expected,
    ]
    result = results.get(queued.workspace.id, "chapter-1")
    assert result is not None
    assert result.content_key == expected
    assert result.audio_urls == [
        "https://storage.test/workspace-1/chapter-1/0.wav",
        "https://storage.test/workspace-1/chapter-1/1.wav",
    ]
    completed = workspaces.get_by_id(queued.workspace.id)
    assert completed is not None
    assert completed.tasks[0].status == WorkspaceTaskStatus.COMPLETED
    assert completed.tasks[0].result_available is True

    requeued = workspaces.queue_tasks(
        completed.id,
        chapter_index_from=1,
        chapter_index_to=1,
        provider=MICROSOFT_FOUNDRY_SPEECH_PROVIDER,
        voice="voice-1",
        force=False,
        etag=completed.etag,
    )
    reuse_handler = WorkspaceTaskHandler(
        getLogger("test.workspace.reuse"),
        workspaces,
        results,
        languages,
        speech,
        blobs,
        RealtimeHub(),
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
    assert len(speech.calls) == 2
    assert len(blobs.calls) == 2
    assert len(results.snapshots) == 3


def test_handler_keeps_partial_result_and_marks_failure() -> None:
    workspaces, results, languages, queued = _queued_workspace()
    speech = FakeSpeechProvider(fail_at=1)

    handler = WorkspaceTaskHandler(
        getLogger("test.workspace"),
        workspaces,
        results,
        languages,
        speech,
        FakeAudioBlobProvider(),
        RealtimeHub(),
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
        provider=MICROSOFT_FOUNDRY_SPEECH_PROVIDER,
        voice="voice-1",
        force=False,
        etag=created.etag,
    )
    return workspaces, RecordingWorkspaceResultRepository(), languages, queued
