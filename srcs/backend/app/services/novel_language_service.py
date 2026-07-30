"""Resolve original and translated novel language content."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass

from app.domain.novels import Novel, NovelChapter
from app.domain.translation_results import TranslationResult
from app.domain.translations import Translation
from app.domain.workspaces import WorkspaceSourceType
from app.repositories.novel_chapter_repository import NovelChapterRepository
from app.repositories.novel_repository import NovelRepository
from app.repositories.translation_repository import TranslationRepository
from app.repositories.translation_result_repository import TranslationResultRepository

ORIGINAL_LANGUAGE_FALLBACK = "original"


class NovelLanguageNotFoundError(Exception):
    """Raised when a novel or requested language is unavailable."""


class NovelLanguageContentNotFoundError(Exception):
    """Raised when chapter content is unavailable in the requested language."""


@dataclass(frozen=True, slots=True)
class NovelLanguage:
    """One language selectable for a novel."""

    code: str
    source_type: WorkspaceSourceType


class NovelLanguageService:
    """Use one deterministic translation project per novel language."""

    def __init__(
        self,
        novels: NovelRepository,
        chapters: NovelChapterRepository,
        translations: TranslationRepository,
        results: TranslationResultRepository,
    ) -> None:
        self._novels = novels
        self._chapters = chapters
        self._translations = translations
        self._results = results

    def list_languages(self, novel_id: str) -> list[NovelLanguage]:
        novel = self._require_novel(novel_id)
        original = self.original_language(novel)
        languages = [
            NovelLanguage(
                code=original,
                source_type=WorkspaceSourceType.ORIGINAL,
            )
        ]
        seen = {original.casefold()}
        for translation in self._translations.list_by_novel(novel.id):
            code = translation.target_language.strip()
            key = code.casefold()
            if not code or key in seen:
                continue
            seen.add(key)
            languages.append(
                NovelLanguage(
                    code=code,
                    source_type=WorkspaceSourceType.TRANSLATION,
                )
            )
        return languages

    def validate_language(self, novel_id: str, language: str) -> NovelLanguage:
        normalized = language.strip()
        option = next(
            (
                item
                for item in self.list_languages(novel_id)
                if item.code.casefold() == normalized.casefold()
            ),
            None,
        )
        if option is None:
            raise NovelLanguageNotFoundError("Novel language not found")
        return option

    def describe_language(
        self,
        novel: Novel,
        language: str,
    ) -> tuple[WorkspaceSourceType, bool]:
        if language.casefold() == self.original_language(novel).casefold():
            return WorkspaceSourceType.ORIGINAL, True
        translation = self.resolve_translation(novel.id, language)
        return WorkspaceSourceType.TRANSLATION, translation is not None

    def list_chapters(self, novel_id: str, language: str) -> list[NovelChapter]:
        novel = self._require_novel(novel_id)
        chapters = self._chapters.list(novel.id).items
        if language.casefold() == self.original_language(novel).casefold():
            return chapters

        translation = self.resolve_translation(novel.id, language)
        if translation is None:
            raise NovelLanguageNotFoundError("Novel language not found")
        tasks = {task.id: task for task in translation.tasks}
        results = {
            result.task_id: result
            for result in self._results.list_by_translation(translation.id)
        }
        resolved: list[NovelChapter] = []
        for chapter in chapters:
            item = deepcopy(chapter)
            task = tasks.get(item.id)
            result = results.get(task.id) if task and task.result_available else None
            item.content_available = result is not None
            item.source_updated = bool(task and task.source_updated)
            item.source_removed = bool(task and task.source_removed)
            if result is not None:
                item.title = result.title
                item.chapter_number = result.chapter_number
                item.updated_at = result.updated_at
                item.etag = result.etag
            resolved.append(item)
        return resolved

    def get_chapter_content(
        self,
        novel_id: str,
        chapter_id: str,
        language: str | None,
    ) -> tuple[NovelChapter, list[str]]:
        novel = self._require_novel(novel_id)
        chapter = self._chapters.get(novel.id, chapter_id)
        if chapter is None:
            raise NovelLanguageContentNotFoundError("Novel chapter not found")

        requested = language.strip() if language else self.original_language(novel)
        if requested.casefold() == self.original_language(novel).casefold():
            if not chapter.content_available:
                raise NovelLanguageContentNotFoundError("Novel chapter content not found")
            return chapter, list(chapter.content)

        translation = self.resolve_translation(novel.id, requested)
        if translation is None:
            raise NovelLanguageNotFoundError("Novel language not found")
        task = next((item for item in translation.tasks if item.id == chapter.id), None)
        if task is None or not task.result_available:
            raise NovelLanguageContentNotFoundError("Translated chapter content not found")
        result = self._results.get(translation.id, task.id)
        if result is None:
            raise NovelLanguageContentNotFoundError("Translated chapter content not found")
        return self._translated_chapter(chapter, task.source_updated, task.source_removed, result)

    def resolve_translation(
        self,
        novel_id: str,
        language: str,
    ) -> Translation | None:
        requested = language.strip().casefold()
        return next(
            (
                translation
                for translation in self._translations.list_by_novel(novel_id)
                if translation.target_language.strip().casefold() == requested
            ),
            None,
        )

    def get_novel(self, novel_id: str) -> Novel | None:
        return self._novels.get_by_id(novel_id)

    @staticmethod
    def original_language(novel: Novel) -> str:
        language = str(novel.language or "").strip()
        return language or ORIGINAL_LANGUAGE_FALLBACK

    def _require_novel(self, novel_id: str) -> Novel:
        novel = self._novels.get_by_id(novel_id)
        if novel is None:
            raise NovelLanguageNotFoundError("Novel not found")
        return novel

    @staticmethod
    def _translated_chapter(
        chapter: NovelChapter,
        source_updated: bool,
        source_removed: bool,
        result: TranslationResult,
    ) -> tuple[NovelChapter, list[str]]:
        translated = deepcopy(chapter)
        translated.title = result.title
        translated.chapter_number = result.chapter_number
        translated.content_available = True
        translated.manually_edited = False
        translated.source_updated = source_updated
        translated.source_removed = source_removed
        translated.updated_at = result.updated_at
        translated.etag = result.etag
        return translated, list(result.content)
