"""Queue handler and listener for audio workspace chapter tasks."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from logging import Logger
from time import sleep
from typing import Any

from app.core.events.message_handler import MessageHandler, QueueMessage
from app.core.events.polling_queue_subscriber import PollingQueueSubscriber
from app.core.realtime import RealtimeHub
from app.domain.workspace_results import WorkspaceResult
from app.domain.workspaces import Workspace, WorkspaceTask, WorkspaceTaskStatus
from app.repositories.workspace_repository import (
    WorkspaceConflictError,
    WorkspaceNotFoundError,
    WorkspaceRepository,
)
from app.repositories.workspace_result_repository import WorkspaceResultRepository
from app.services.novel_language_service import NovelLanguageService

WORKSPACE_TASK_QUEUE_NAME = "workspaces-tasks"
WORKSPACE_TASK_EVENT_TYPE = "workspace.task.requested"
WORKSPACE_TASK_EVENT_SCHEMA_VERSION = 1


@dataclass(frozen=True, slots=True)
class WorkspaceTaskEvent:
    """Validated task-scoped workspace queue event."""

    workspace_id: str
    created_by: str
    task_id: str
    provider: str
    voice: str
    refetch: bool
    enqueued_at: str

    @classmethod
    def from_mapping(cls, content: Mapping[str, Any]) -> WorkspaceTaskEvent:
        if content.get("schemaVersion") != WORKSPACE_TASK_EVENT_SCHEMA_VERSION:
            raise ValueError("Unsupported workspace task event schema")
        if content.get("type") != WORKSPACE_TASK_EVENT_TYPE:
            raise ValueError("Unsupported workspace task event type")
        refetch = content.get("refetch", False)
        if not isinstance(refetch, bool):
            raise ValueError("Invalid workspace task event refetch flag")
        return cls(
            workspace_id=_required_string(content, "workspaceId"),
            created_by=_required_string(content, "createdBy"),
            task_id=_required_string(content, "taskId"),
            provider=_required_string(content, "provider"),
            voice=_required_string(content, "voice"),
            refetch=refetch,
            enqueued_at=_required_string(content, "enqueuedAt"),
        )


class WorkspaceTaskHandler(MessageHandler):
    """Build progressive sentence-hash output for one queued chapter."""

    def __init__(
        self,
        logger: Logger,
        workspace_repository: WorkspaceRepository,
        workspace_result_repository: WorkspaceResultRepository,
        novel_language_service: NovelLanguageService,
        realtime_hub: RealtimeHub,
        sleeper: Callable[[float], None] = sleep,
    ) -> None:
        self._logger = logger
        self._workspaces = workspace_repository
        self._results = workspace_result_repository
        self._languages = novel_language_service
        self._realtime = realtime_hub
        self._sleep = sleeper

    def handle(self, message: QueueMessage) -> None:
        if message.content is None:
            raise ValueError("Workspace task queue message has no content")
        event = WorkspaceTaskEvent.from_mapping(message.content)
        workspace = self._workspaces.get_by_id(event.workspace_id)
        if workspace is None or workspace.created_by != event.created_by:
            return
        task = _find_task(workspace, event.task_id)
        if not _event_matches_task(task, event):
            return

        claimed = self._claim_task_with_retry(workspace, event)
        if claimed is None:
            return
        claimed_task = _require_task(claimed, event.task_id)
        self._publish_update(claimed, claimed_task.id)
        existing = self._results.get(claimed.id, claimed_task.id)

        try:
            reusable = (
                existing is not None
                and claimed_task.result_available
                and not claimed_task.source_updated
                and not event.refetch
                and existing.provider == event.provider
                and existing.voice == event.voice
            )
            if reusable:
                completed_at = datetime.now(UTC)
                completed = self._update_task_with_retry(
                    claimed,
                    claimed_task.id,
                    WorkspaceTaskStatus.COMPLETED,
                    attempts=claimed_task.attempts,
                    error=None,
                    result_available=True,
                    completed_at=completed_at,
                    source_chapter_updated_at=None,
                    clear_source_updated=False,
                )
            else:
                chapter, sentences = self._languages.get_chapter_content(
                    claimed.novel_id,
                    claimed_task.id,
                    claimed.language,
                )
                now = datetime.now(UTC)
                result = self._results.upsert(
                    WorkspaceResult(
                        id=claimed_task.id,
                        workspace_id=claimed.id,
                        task_id=claimed_task.id,
                        provider=event.provider,
                        voice=event.voice,
                        content_key=[],
                        created_at=now,
                        updated_at=now,
                    )
                )
                for index, sentence in enumerate(sentences):
                    content_key = sha256(sentence.encode("utf-8")).hexdigest()
                    self._logger.info(
                        "Workspace task %s sentence %d/%d hash %s",
                        claimed_task.id,
                        index + 1,
                        len(sentences),
                        content_key,
                    )
                    self._sleep(1)
                    result.content_key.append(content_key)
                    result = self._results.upsert(result)
                completed_at = datetime.now(UTC)
                completed = self._update_task_with_retry(
                    claimed,
                    claimed_task.id,
                    WorkspaceTaskStatus.COMPLETED,
                    attempts=claimed_task.attempts,
                    error=None,
                    result_available=True,
                    completed_at=completed_at,
                    source_chapter_updated_at=chapter.updated_at,
                    clear_source_updated=True,
                )
            self._publish_update(completed, claimed_task.id)
        except Exception as exc:
            latest = self._workspaces.get_by_id(claimed.id) or claimed
            try:
                failed = self._update_task_with_retry(
                    latest,
                    claimed_task.id,
                    WorkspaceTaskStatus.FAILED,
                    attempts=claimed_task.attempts,
                    error=str(exc),
                    result_available=False,
                    completed_at=None,
                    source_chapter_updated_at=None,
                    clear_source_updated=False,
                )
                self._publish_update(failed, claimed_task.id)
            except Exception:
                self._logger.exception("Workspace task failure state could not be saved")
            raise

    def _claim_task_with_retry(
        self,
        workspace: Workspace,
        event: WorkspaceTaskEvent,
    ) -> Workspace | None:
        for _ in range(3):
            try:
                return self._workspaces.claim_task(
                    workspace.id,
                    event.task_id,
                    etag=workspace.etag,
                )
            except WorkspaceConflictError:
                latest = self._workspaces.get_by_id(workspace.id)
                if latest is None:
                    return None
                if not _event_matches_task(_find_task(latest, event.task_id), event):
                    return None
                workspace = latest
            except WorkspaceNotFoundError:
                return None
        raise WorkspaceConflictError("Workspace task claim conflicted repeatedly")

    def _update_task_with_retry(
        self,
        workspace: Workspace,
        task_id: str,
        status: WorkspaceTaskStatus,
        *,
        attempts: int,
        error: str | None,
        result_available: bool,
        completed_at: datetime | None,
        source_chapter_updated_at: datetime | None,
        clear_source_updated: bool,
    ) -> Workspace:
        for _ in range(3):
            try:
                return self._workspaces.update_task(
                    workspace.id,
                    task_id,
                    status,
                    attempts=attempts,
                    error=error,
                    result_available=result_available,
                    completed_at=completed_at,
                    source_chapter_updated_at=source_chapter_updated_at,
                    clear_source_updated=clear_source_updated,
                    etag=workspace.etag,
                )
            except WorkspaceConflictError:
                latest = self._workspaces.get_by_id(workspace.id)
                if latest is None:
                    raise WorkspaceNotFoundError from None
                workspace = latest
        raise WorkspaceConflictError("Workspace task update conflicted repeatedly")

    def _publish_update(self, workspace: Workspace, task_id: str | None = None) -> None:
        self._realtime.publish(
            "workspace.updated",
            build_workspace_updated_payload(workspace, task_id=task_id),
        )


class WorkspaceTaskQueueListener(PollingQueueSubscriber):
    """Queue listener configured for workspace audio tasks."""

    def __init__(
        self,
        logger: Logger,
        workspace_repository: WorkspaceRepository,
        workspace_result_repository: WorkspaceResultRepository,
        novel_language_service: NovelLanguageService,
        realtime_hub: RealtimeHub,
        workers: int = 1,
    ) -> None:
        super().__init__(
            name=WORKSPACE_TASK_QUEUE_NAME,
            logger=logger,
            handler=WorkspaceTaskHandler(
                logger,
                workspace_repository,
                workspace_result_repository,
                novel_language_service,
                realtime_hub,
            ),
            workers=workers,
        )


def build_workspace_task_event(
    workspace: Workspace,
    task: WorkspaceTask,
    *,
    refetch: bool,
) -> dict[str, Any]:
    if task.provider is None or task.voice is None:
        raise ValueError("Workspace task provider and voice are required")
    return {
        "schemaVersion": WORKSPACE_TASK_EVENT_SCHEMA_VERSION,
        "type": WORKSPACE_TASK_EVENT_TYPE,
        "workspaceId": workspace.id,
        "createdBy": workspace.created_by,
        "taskId": task.id,
        "provider": task.provider,
        "voice": task.voice,
        "refetch": refetch,
        "enqueuedAt": datetime.now(UTC).isoformat(),
    }


def build_workspace_updated_payload(
    workspace: Workspace,
    *,
    task_id: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "workspaceId": workspace.id,
        "updatedAt": workspace.updated_at.isoformat(),
        "progress": {
            "total": workspace.progress.total,
            "created": workspace.progress.created,
            "queued": workspace.progress.queued,
            "running": workspace.progress.running,
            "completed": workspace.progress.completed,
            "failed": workspace.progress.failed,
        },
    }
    if task_id is not None:
        payload["taskId"] = task_id
    return payload


def _required_string(content: Mapping[str, Any], key: str) -> str:
    value = content.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"Missing workspace task event field: {key}")
    return value


def _find_task(workspace: Workspace, task_id: str) -> WorkspaceTask | None:
    return next((item for item in workspace.tasks if item.id == task_id), None)


def _require_task(workspace: Workspace, task_id: str) -> WorkspaceTask:
    task = _find_task(workspace, task_id)
    if task is None:
        raise WorkspaceNotFoundError
    return task


def _event_matches_task(
    task: WorkspaceTask | None,
    event: WorkspaceTaskEvent,
) -> bool:
    return bool(
        task is not None
        and not task.source_removed
        and task.status == WorkspaceTaskStatus.QUEUED
        and task.provider == event.provider
        and task.voice == event.voice
    )
