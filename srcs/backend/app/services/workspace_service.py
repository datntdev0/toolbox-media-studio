"""Application service for media workspaces."""

from datetime import UTC, datetime

from app.domain.workspaces import (
    Workspace,
    WorkspacePage,
    WorkspaceSourceType,
    WorkspaceType,
    WorkspaceView,
)
from app.repositories.workspace_repository import (
    WorkspaceNotFoundError,
    WorkspaceRepository,
)
from app.services.novel_language_service import NovelLanguageService


class WorkspaceService:
    """Coordinate workspace persistence and live novel information."""

    def __init__(
        self,
        workspaces: WorkspaceRepository,
        languages: NovelLanguageService,
    ) -> None:
        self._workspaces = workspaces
        self._languages = languages

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
        return self._to_view(self._workspaces.update(workspace), detail=False)

    def delete(self, id: str, deleted_by: str) -> None:
        self._workspaces.delete(id, deleted_by)

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
