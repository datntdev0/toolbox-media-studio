import type {
  TranslationApiRecord,
  TranslationConfigurationInput,
  TranslationWorkspace,
  TranslationWorkspaceStatus
} from '~/types/translation-workspace'
import { resolveLanguage } from '~/constants/supported-languages'
import { translationProviders } from '~/utils/translation-workspace-fixtures'
import {
  TranslationCreateRequest,
  type TranslationResponse,
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

export function normalizeTranslationWorkspace(record: TranslationApiRecord): TranslationWorkspace {
  const novel = record.novel
  const total = Number(novel?.chapterCount || 0)
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
    progress: { total, translated: 0, queued: 0, running: 0, failed: 0 },
    configuration: configuration
      ? {
          ...configuration,
          providerName: provider?.label || configuration.providerId,
          modelName: model?.label || configuration.modelId
        }
      : null,
    chapters: [],
    updatedAt: record.updatedAt,
    etag: record.etag || null
  }
}

function toApiRecord(response: TranslationResponse): TranslationApiRecord {
  return response.toJSON() as unknown as TranslationApiRecord
}

export function useTranslationWorkspaceApi() {
  const { translations } = useApiClient()
  return {
    async list() {
      const response = await translations.list_translations(50, undefined)
      return response.items.map(item => normalizeTranslationWorkspace(toApiRecord(item)))
    },
    async get(id: string) {
      return normalizeTranslationWorkspace(
        toApiRecord(await translations.get_translation(id))
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
      return toApiRecord(response)
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
      return toApiRecord(response)
    },
    async delete(id: string) {
      return translations.delete_translation(id)
    }
  }
}
