"""Translation task result domain models and API contracts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


@dataclass(slots=True)
class TranslationResult:
    """Persisted translated content for one embedded task."""

    id: str
    translation_id: str
    task_id: str
    title: str
    chapter_number: int | None
    content: list[str]
    created_at: datetime
    updated_at: datetime
    etag: str | None = None


class TranslationResultResponse(BaseModel):
    """Translated content returned for one task."""

    model_config = ConfigDict(populate_by_name=True)

    translation_id: str = Field(alias="translationId")
    task_id: str = Field(alias="taskId")
    title: str
    chapter_number: int | None = Field(default=None, alias="chapterNumber")
    content: list[str] = Field(default_factory=list)
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")


class TranslationResultUpdateRequest(BaseModel):
    """Manual translated content supplied for one chapter task."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    content: str
    title: str = ""


def to_translation_result_response(
    result: TranslationResult,
) -> TranslationResultResponse:
    return TranslationResultResponse(
        translation_id=result.translation_id,
        task_id=result.task_id,
        title=result.title,
        chapter_number=result.chapter_number,
        content=result.content,
        created_at=result.created_at,
        updated_at=result.updated_at,
    )
