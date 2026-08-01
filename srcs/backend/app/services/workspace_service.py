"""Application service for media workspaces."""

from datetime import UTC, datetime

from app.domain.novels import NovelChapter
from app.domain.workspaces import (
    Workspace,
    WorkspacePage,
    WorkspaceProgress,
    WorkspaceSourceType,
    WorkspaceTask,
    WorkspaceTaskStatus,
    WorkspaceType,
    WorkspaceView,
)
from app.repositories.workspace_repository import (
    WorkspaceConflictError,
    WorkspaceNotFoundError,
    WorkspaceRepository,
)
from app.repositories.workspace_result_repository import WorkspaceResultRepository
from app.services.novel_language_service import NovelLanguageService


class WorkspaceService:
    """Coordinate workspace persistence and live novel information."""

    def __init__(
        self,
        workspaces: WorkspaceRepository,
        languages: NovelLanguageService,
        results: WorkspaceResultRepository,
    ) -> None:
        self._workspaces = workspaces
        self._languages = languages
        self._results = results

    def create(self, workspace: Workspace) -> WorkspaceView:
        self._languages.validate_language(workspace.novel_id, workspace.language)
        return self._to_view(self._workspaces.create(workspace), detail=False)

    def list(
        self,
        workspace_type: WorkspaceType | None,
        limit: int,
        continuation_token: str | None,
    ) -> tuple[list[WorkspaceView], str | None]:
        page: WorkspacePage = self._workspaces.list(
            workspace_type,
            limit,
            continuation_token,
        )
        return (
            [self._to_view(workspace, detail=False) for workspace in page.items],
            page.continuation_token,
        )

    def get_by_id(self, id: str) -> WorkspaceView | None:
        workspace = self._workspaces.get_by_id(id)
        if workspace is None:
            return None
        self._languages.validate_language(workspace.novel_id, workspace.language)
        return self._to_view(workspace, detail=True)

    def update(self, id: str, title: str, updated_by: str) -> WorkspaceView:
        workspace = self._workspaces.get_by_id(id)
        if workspace is None:
            raise WorkspaceNotFoundError
        workspace.title = title.strip()
        workspace.updated_by = updated_by
        workspace.updated_at = datetime.now(UTC)
        return self._to_view(
            self._workspaces.update(workspace, workspace.etag),
            detail=False,
        )

    def delete(self, id: str, deleted_by: str) -> None:
        if self._workspaces.get_by_id(id) is None:
            raise WorkspaceNotFoundError
        self._results.delete_by_workspace(id)
        self._workspaces.delete(id, deleted_by)

    def sync_tasks(self, id: str, *, updated_by: str) -> WorkspaceView:
        """Reconcile a workspace task manifest with its available language content."""

        for _ in range(3):
            workspace = self._workspaces.get_by_id(id)
            if workspace is None:
                raise WorkspaceNotFoundError
            chapters = [
                chapter
                for chapter in self._languages.list_chapters(
                    workspace.novel_id,
                    workspace.language,
                )
                if chapter.content_available and not chapter.source_removed
            ]
            _synchronize_tasks(workspace, chapters)
            workspace.progress = WorkspaceProgress.from_tasks(workspace.tasks)
            workspace.updated_by = updated_by
            workspace.updated_at = datetime.now(UTC)
            try:
                updated = self._workspaces.update(workspace, workspace.etag)
            except WorkspaceConflictError:
                continue
            return self._to_view(updated, detail=True)
        raise WorkspaceSyncConflictError("Workspace has changed")

    def _to_view(self, workspace: Workspace, *, detail: bool) -> WorkspaceView:
        novel = self._languages.get_novel(workspace.novel_id)
        if novel is None:
            return WorkspaceView(
                workspace=workspace,
                novel=None,
                source_type=WorkspaceSourceType.TRANSLATION,
                source_available=False,
                chapters=[],
            )

        source_type, source_available = self._languages.describe_language(
            novel,
            workspace.language,
        )
        chapters = (
            self._languages.list_chapters(novel.id, workspace.language)
            if detail and source_available
            else []
        )
        return WorkspaceView(
            workspace=workspace,
            novel=novel,
            source_type=source_type,
            source_available=source_available,
            chapters=chapters,
        )


class WorkspaceSyncConflictError(Exception):
    """Raised when a workspace task manifest cannot be synchronized."""


def _task_from_chapter(chapter: NovelChapter) -> WorkspaceTask:
    return WorkspaceTask(
        id=chapter.id,
        title=chapter.title,
        chapter_number=chapter.chapter_number,
        manifest_index=chapter.manifest_index,
        source_chapter_updated_at=chapter.updated_at,
    )


def _synchronize_tasks(workspace: Workspace, chapters: list[NovelChapter]) -> None:
    current = {task.id: task for task in workspace.tasks}
    active_ids: set[str] = set()
    for chapter in sorted(chapters, key=lambda item: (item.manifest_index, item.id)):
        active_ids.add(chapter.id)
        task = current.get(chapter.id)
        if task is None:
            workspace.tasks.append(_task_from_chapter(chapter))
            continue
        source_is_newer = chapter.updated_at > task.source_chapter_updated_at
        task.title = chapter.title
        task.chapter_number = chapter.chapter_number
        task.manifest_index = chapter.manifest_index
        task.source_removed = False
        if source_is_newer and task.result_available:
            task.source_updated = True
        if source_is_newer:
            task.source_chapter_updated_at = chapter.updated_at

    for task in workspace.tasks:
        if task.id in active_ids or task.source_removed:
            continue
        task.source_removed = True
        if task.status == WorkspaceTaskStatus.QUEUED:
            task.status = WorkspaceTaskStatus.CREATED

    workspace.tasks.sort(key=lambda item: (item.manifest_index, item.id))
