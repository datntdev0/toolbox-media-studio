"""Persisted outputs produced by audio workspace tasks."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(slots=True)
class WorkspaceResult:
    """Ordered sentence hashes and audio URLs for one workspace chapter task."""

    id: str
    workspace_id: str
    task_id: str
    provider: str
    voice: str
    created_at: datetime
    updated_at: datetime
    content_key: list[str] = field(default_factory=list)
    audio_urls: list[str] = field(default_factory=list)
    etag: str | None = None
