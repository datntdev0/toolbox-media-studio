import type {
  AudioChapterContent,
  AudioLanguageOption,
  AudioWorkspace,
  AudioWorkspaceChapter,
  AudioWorkspaceNovel
} from '~/types/audio-workspace'
import {
  WorkspaceCreateRequest,
  WorkspaceType,
  WorkspaceUpdateRequest
} from '~~/shared/api-services/srv-core.client'

type ApiRecord = Record<string, unknown>

function asRecord(value: unknown): ApiRecord {
  return value && typeof value === 'object' ? value as ApiRecord : {}
}

function asDateString(value: unknown) {
  if (value instanceof Date) return value.toISOString()
  return String(value || '')
}

function normalizeNovel(value: unknown): AudioWorkspaceNovel | null {
  const novel = asRecord(value)
  if (!novel.id) return null
  return {
    id: String(novel.id),
    title: String(novel.title || 'Novel unavailable'),
    description: novel.description ? String(novel.description) : null,
    coverImageUrl: novel.coverImageUrl ? String(novel.coverImageUrl) : null,
    language: novel.language ? String(novel.language) : null,
    author: novel.author ? String(novel.author) : null,
    tags: Array.isArray(novel.tags) ? novel.tags.map(String) : [],
    status: String(novel.status || 'draft'),
    chapterCount: Number(novel.chapterCount || 0)
  }
}

function normalizeChapter(value: unknown): AudioWorkspaceChapter {
  const chapter = asRecord(value)
  return {
    id: String(chapter.id || ''),
    title: String(chapter.title || 'Untitled chapter'),
    chapterNumber: chapter.chapterNumber == null ? null : Number(chapter.chapterNumber),
    manifestIndex: Number(chapter.manifestIndex || 0),
    contentAvailable: Boolean(chapter.contentAvailable),
    sourceUpdated: Boolean(chapter.sourceUpdated),
    sourceRemoved: Boolean(chapter.sourceRemoved)
  }
}

export function normalizeAudioWorkspace(value: unknown): AudioWorkspace {
  const record = asRecord(value)
  return {
    id: String(record.id || ''),
    title: String(record.title || 'Audio workspace'),
    type: 'audio',
    novelId: String(record.novelId || ''),
    language: String(record.language || ''),
    sourceType: record.sourceType === 'translation' ? 'translation' : 'original',
    sourceAvailable: Boolean(record.sourceAvailable),
    chapterCount: Number(record.chapterCount || 0),
    novel: normalizeNovel(record.novel),
    chapters: Array.isArray(record.chapters)
      ? record.chapters.map(normalizeChapter)
      : [],
    createdAt: asDateString(record.createdAt),
    updatedAt: asDateString(record.updatedAt)
  }
}

export function useAudioWorkspaceApi() {
  return {
    async list() {
      const { workspaces } = useApiClient()
      const response = await workspaces.list_workspaces(
        'audio' as never,
        100,
        undefined
      )
      return response.items.map(item => normalizeAudioWorkspace(item.toJSON()))
    },
    async get(id: string) {
      const { workspaces } = useApiClient()
      const response = await workspaces.get_workspace(id)
      return normalizeAudioWorkspace(response.toJSON())
    },
    async create(body: { title: string, novelId: string, language: string }) {
      const { workspaces } = useApiClient()
      const response = await workspaces.create_workspace(
        new WorkspaceCreateRequest({
          ...body,
          type: WorkspaceType.Audio
        })
      )
      return normalizeAudioWorkspace(response.toJSON())
    },
    async update(id: string, title: string) {
      const { workspaces } = useApiClient()
      const response = await workspaces.update_workspace(
        id,
        new WorkspaceUpdateRequest({ title })
      )
      return normalizeAudioWorkspace(response.toJSON())
    },
    async delete(id: string) {
      const { workspaces } = useApiClient()
      await workspaces.delete_workspace(id)
    },
    async listLanguages(novelId: string) {
      const { novels } = useApiClient()
      const response = await novels.list_novel_languages(novelId)
      return response.items.map(item => ({
        code: String(item.code),
        sourceType: item.sourceType === 'translation' ? 'translation' : 'original'
      } satisfies AudioLanguageOption))
    },
    async getChapter(novelId: string, chapterId: string, language: string) {
      const { novels } = useApiClient()
      const response = await novels.get_novel_chapter(
        novelId,
        chapterId,
        language as never
      )
      return {
        id: String(response.id),
        title: String(response.title),
        chapterNumber: response.chapterNumber == null
          ? null
          : Number(response.chapterNumber),
        content: (response.content || []).map(String)
      } satisfies AudioChapterContent
    }
  }
}
