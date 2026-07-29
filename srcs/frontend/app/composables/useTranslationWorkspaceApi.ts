import type {
  TranslationApiRecord,
  TranslationChapterStatus,
  TranslationConfigurationInput,
  TranslationDetailApiRecord,
  TranslationSyncChanges,
  TranslationTaskApiRecord,
  TranslationWorkspace,
  TranslationWorkspaceStatus
} from '~/types/translation-workspace'
import { resolveLanguage } from '~/constants/supported-languages'
import { translationProviders } from '~/utils/translation-workspace-fixtures'
import {
  TranslationCreateRequest,
  TranslationStartRequest,
  TranslationUpdateRequest
} from '~~/shared/api-services/srv-core.client'

const statuses = new Set<TranslationWorkspaceStatus>([
  'needs_setup',
  'ready',
  'running',
  'completed',
  'stopped',
  'failed'
])

function normalizeTaskStatus(task: TranslationTaskApiRecord): TranslationChapterStatus {
  if (task.sourceRemoved) return 'unavailable'
  const statuses: Record<TranslationTaskApiRecord['status'], TranslationChapterStatus> = {
    created: 'not_started',
    queued: 'queued',
    running: 'translating',
    completed: 'translated',
    failed: 'failed'
  }
  return statuses[task.status]
}

export function normalizeTranslationWorkspace(
  record: TranslationApiRecord | TranslationDetailApiRecord
): TranslationWorkspace {
  const novel = record.novel
  const detail = 'progress' in record ? record : null
  const total = Number(detail?.progress.total ?? novel?.chapterCount ?? 0)
  const configuration = record.configuration
  const provider = translationProviders.find(item => item.id === configuration?.providerId)
  const model = provider?.models.find(item => item.id === configuration?.modelId)
  return {
    id: record.id,
    name: record.name,
    novelId: record.novelId,
    novelTitle: novel?.title || 'Novel unavailable',
    coverImageUrl: novel?.coverImageUrl || null,
    sourceLanguage: resolveLanguage(novel?.language),
    targetLanguage: resolveLanguage(record.targetLanguage),
    status: statuses.has(record.status) ? record.status : 'needs_setup',
    progress: {
      total,
      created: Number(detail?.progress.created || 0),
      translated: Number(detail?.progress.completed || 0),
      queued: Number(detail?.progress.queued || 0),
      running: Number(detail?.progress.running || 0),
      failed: Number(detail?.progress.failed || 0)
    },
    configuration: configuration
      ? {
          ...configuration,
          providerName: provider?.label || configuration.providerId,
          modelName: model?.label || configuration.modelId
        }
      : null,
    chapters: (detail?.tasks || [])
      .map(task => ({
        id: task.id,
        chapterIndex: task.manifestIndex + 1,
        number: task.chapterNumber ?? task.manifestIndex + 1,
        title: task.title,
        status: normalizeTaskStatus(task),
        originalParagraphs: [],
        translatedParagraphs: [],
        attempts: Number(task.attempts || 0),
        lastError: task.lastError || null,
        resultAvailable: Boolean(task.resultAvailable),
        sourceUpdated: Boolean(task.sourceUpdated),
        sourceRemoved: Boolean(task.sourceRemoved)
      }))
      .sort((left, right) => left.chapterIndex - right.chapterIndex),
    updatedAt: record.updatedAt,
    etag: record.etag || null
  }
}

function toRecord<T>(response: { toJSON: () => unknown }): T {
  return response.toJSON() as T
}

export function useTranslationWorkspaceApi() {
  const { translations } = useApiClient()
  return {
    async list() {
      const response = await translations.list_translations(50, undefined)
      return response.items.map(item =>
        normalizeTranslationWorkspace(toRecord<TranslationApiRecord>(item))
      )
    },
    async get(id: string) {
      return normalizeTranslationWorkspace(
        toRecord<TranslationDetailApiRecord>(await translations.get_translation(id))
      )
    },
    async create(body: {
      name: string
      novelId: string
      targetLanguage: string
    }) {
      const response = await translations.create_translation(
        new TranslationCreateRequest(body)
      )
      return toRecord<TranslationApiRecord>(response)
    },
    async update(
      id: string,
      body: {
        name: string
        novelId: string
        targetLanguage: string
        configuration: TranslationConfigurationInput | null
        etag?: string | null
      }
    ) {
      const response = await translations.update_translation(
        id,
        new TranslationUpdateRequest({
          ...body,
          configuration: body.configuration as never,
          etag: body.etag as never
        })
      )
      return toRecord<TranslationApiRecord>(response)
    },
    async delete(id: string) {
      return translations.delete_translation(id)
    },
    async sync(id: string) {
      const response = await translations.sync_translation(id)
      return {
        workspace: normalizeTranslationWorkspace(
          toRecord<TranslationDetailApiRecord>(response.translation)
        ),
        changes: toRecord<TranslationSyncChanges>(response.changes)
      }
    },
    async start(
      id: string,
      body: {
        chapterIndexFrom: number
        chapterIndexTo: number
        refetch: boolean
        force: boolean
      }
    ) {
      const response = await translations.start_translation(
        id,
        new TranslationStartRequest(body)
      )
      return normalizeTranslationWorkspace(toRecord<TranslationDetailApiRecord>(response))
    },
    async stop(id: string) {
      const response = await translations.stop_translation(id)
      return normalizeTranslationWorkspace(toRecord<TranslationDetailApiRecord>(response))
    },
    async getResult(id: string, taskId: string) {
      const response = await translations.get_translation_result(id, taskId)
      return (response.content || []).map(String)
    }
  }
}
