"""Persisted outputs produced by audio workspace tasks."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

WORKSPACE_RESULT_SCHEMA_VERSION = 2


@dataclass(slots=True)
class WorkspaceResult:
    """Chapter-level audio and subtitle artifacts for one workspace task."""

    id: str
    workspace_id: str
    task_id: str
    provider: str
    voice: str
    created_at: datetime
    updated_at: datetime
    schema_version: int = WORKSPACE_RESULT_SCHEMA_VERSION
    content_key: list[str] = field(default_factory=list)
    audio_url: str | None = None
    subtitle_url: str | None = None
    etag: str | None = None

    @property
    def artifacts_available(self) -> bool:
        """Whether this result uses the current schema and has both artifacts."""

        return bool(
            self.schema_version == WORKSPACE_RESULT_SCHEMA_VERSION
            and self.content_key
            and self.audio_url
            and self.subtitle_url
        )
