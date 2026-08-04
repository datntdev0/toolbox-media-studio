"""Audio workspace queue handler tests."""

from copy import deepcopy
from datetime import UTC, datetime
from hashlib import sha256
from logging import getLogger

import pytest

from app.core.events.message_handler import QueueMessage
from app.core.realtime import RealtimeHub
from app.domain.novels import Novel, NovelChapter
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
from app.providers.speech_service_provider import SpeechSynthesisArtifact
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
    def __init__(self, *, should_fail: bool = False) -> None:
        self.calls: list[tuple[list[str], str]] = []
        self._should_fail = should_fail

    def synthesize(self, sentences: list[str], voice: str) -> SpeechSynthesisArtifact:
        self.calls.append((sentences, voice))
        if self._should_fail:
            raise RuntimeError("mock TTS failure")
        return SpeechSynthesisArtifact(
            audio_data=f"audio:{voice}:{'|'.join(sentences)}".encode(),
            subtitle_data=b"1\n00:00:00,000 --> 00:00:01,000\nFirst sentence\n",
        )
class FakeAudioBlobProvider:
    def __init__(self) -> None:
        self.audio_calls: list[tuple[str, str, bytes]] = []
        self.subtitle_calls: list[tuple[str, str, bytes]] = []
        self.cleanup_calls: list[tuple[str, str]] = []
        self.fail_subtitle = False

    def upload_task_audio(
        self,
        workspace_id: str,
        task_id: str,
        content: bytes,
    ) -> str:
        self.audio_calls.append((workspace_id, task_id, content))
        return f"https://storage.test/{workspace_id}/{task_id}/audio.wav"

    def upload_task_subtitle(
        self,
        workspace_id: str,
        task_id: str,
        content: bytes,
    ) -> str:
        self.subtitle_calls.append((workspace_id, task_id, content))
        if self.fail_subtitle:
            raise RuntimeError("mock subtitle upload failure")
        return f"https://storage.test/{workspace_id}/{task_id}/captions.srt"

    def delete_legacy_task_audio(self, workspace_id: str, task_id: str) -> None:
        self.cleanup_calls.append((workspace_id, task_id))


def test_handler_synthesizes_and_persists_chapter_artifacts_atomically() -> None:
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
    assert [snapshot.content_key for snapshot in results.snapshots] == [expected]
    result = results.get(queued.workspace.id, "chapter-1")
    assert result is not None
    assert result.content_key == expected
    assert result.schema_version == 2
    assert result.audio_url == "https://storage.test/workspace-1/chapter-1/audio.wav"
    assert result.subtitle_url == "https://storage.test/workspace-1/chapter-1/captions.srt"
    assert speech.calls == [(["First sentence", "Second sentence"], "voice-1")]
    assert len(blobs.audio_calls) == 1
    assert len(blobs.subtitle_calls) == 1
    assert blobs.cleanup_calls == [("workspace-1", "chapter-1")]
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
    assert len(speech.calls) == 1
    assert len(blobs.audio_calls) == 1
    assert len(results.snapshots) == 1


def test_handler_does_not_persist_partial_result_and_marks_failure() -> None:
    workspaces, results, languages, queued = _queued_workspace()
    speech = FakeSpeechProvider()
    blobs = FakeAudioBlobProvider()
    blobs.fail_subtitle = True

    handler = WorkspaceTaskHandler(
        getLogger("test.workspace"),
        workspaces,
        results,
        languages,
        speech,
        blobs,
        RealtimeHub(),
    )
    with pytest.raises(RuntimeError, match="mock subtitle upload failure"):
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

    assert results.get(queued.workspace.id, "chapter-1") is None
    assert len(blobs.audio_calls) == 1
    assert len(blobs.subtitle_calls) == 1
    assert blobs.cleanup_calls == []
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
