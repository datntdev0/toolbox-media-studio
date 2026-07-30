"""Generic media workspace domain models."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from app.domain.novels import Novel, NovelChapter


class WorkspaceType(StrEnum):
    """Supported media workspace types."""

    AUDIO = "audio"


class WorkspaceSourceType(StrEnum):
    """Kinds of novel content selected by a workspace."""

    ORIGINAL = "original"
    TRANSLATION = "translation"


@dataclass(slots=True)
class Workspace:
    """Persisted media workspace."""

    id: str
    title: str
    type: WorkspaceType
    novel_id: str
    language: str
    created_by: str
    created_at: datetime
    updated_by: str
    updated_at: datetime
    deleted_at: datetime | None = None
    deleted_by: str | None = None
    etag: str | None = None


@dataclass(slots=True)
class WorkspacePage:
    """Paged workspace list."""

    items: list[Workspace]
    continuation_token: str | None


@dataclass(slots=True)
class WorkspaceView:
    """Workspace enriched with its current novel and selected source."""

    workspace: Workspace
    novel: Novel | None
    source_type: WorkspaceSourceType
    source_available: bool
    chapters: list[NovelChapter]
