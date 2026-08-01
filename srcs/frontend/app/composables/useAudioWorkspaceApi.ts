import type {
  AudioChapterContent,
  AudioLanguageOption,
  AudioWorkspace,
  AudioWorkspaceChapter,
  AudioWorkspaceNovel,
  AudioWorkspaceTask,
  AudioWorkspaceTaskResult,
  AudioWorkspaceTaskStatus
} from '~/types/audio-workspace'
import {
  WorkspaceCreateRequest,
  WorkspaceStartRequest,
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

const taskStatuses = new Set<AudioWorkspaceTaskStatus>([
  'created',
  'queued',
  'running',
  'completed',
  'failed'
])

function normalizeTask(value: unknown): AudioWorkspaceTask {
  const task = asRecord(value)
  const status = String(task.status || 'created') as AudioWorkspaceTaskStatus
  return {
    id: String(task.id || ''),
    title: String(task.title || 'Untitled chapter'),
    chapterNumber: task.chapterNumber == null ? null : Number(task.chapterNumber),
    manifestIndex: Number(task.manifestIndex || 0),
    status: taskStatuses.has(status) ? status : 'created',
    attempts: Number(task.attempts || 0),
    lastError: task.lastError ? String(task.lastError) : null,
    resultAvailable: Boolean(task.resultAvailable),
    completedAt: task.completedAt ? asDateString(task.completedAt) : null,
    sourceChapterUpdatedAt: asDateString(task.sourceChapterUpdatedAt),
    sourceUpdated: Boolean(task.sourceUpdated),
    sourceRemoved: Boolean(task.sourceRemoved),
    provider: task.provider ? String(task.provider) : null,
    voice: task.voice ? String(task.voice) : null
  }
}

function normalizeTaskResult(value: unknown): AudioWorkspaceTaskResult {
  const result = asRecord(value)
  return {
    taskId: String(result.taskId || ''),
    workspaceId: String(result.workspaceId || ''),
    provider: String(result.provider || ''),
    voice: String(result.voice || ''),
    sentences: Array.isArray(result.sentences)
      ? result.sentences.map((value) => {
          const sentence = asRecord(value)
          return {
            index: Number(sentence.index),
            audioUrl: String(sentence.audioUrl || '')
          }
        })
      : [],
    createdAt: asDateString(result.createdAt),
    updatedAt: asDateString(result.updatedAt)
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
    tasks: Array.isArray(record.tasks) ? record.tasks.map(normalizeTask) : [],
    progress: {
      total: Number(asRecord(record.progress).total || 0),
      created: Number(asRecord(record.progress).created || 0),
      queued: Number(asRecord(record.progress).queued || 0),
      running: Number(asRecord(record.progress).running || 0),
      completed: Number(asRecord(record.progress).completed || 0),
      failed: Number(asRecord(record.progress).failed || 0)
    },
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
    async start(id: string, body: {
      provider: string
      voice: string
      chapterIndexFrom: number
      chapterIndexTo: number
      refetch: boolean
      force: boolean
    }) {
      const { workspaces } = useApiClient()
      const response = await workspaces.start_workspace(
        id,
        new WorkspaceStartRequest(body)
      )
      return normalizeAudioWorkspace(response.toJSON())
    },
    async stop(id: string) {
      const { workspaces } = useApiClient()
      const response = await workspaces.stop_workspace(id)
      return normalizeAudioWorkspace(response.toJSON())
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
    },
    async getTaskResult(id: string, taskId: string) {
      const { workspaces } = useApiClient()
      const response = await workspaces.get_workspace_task_result(id, taskId)
      return normalizeTaskResult(response.toJSON())
    }
  }
}
