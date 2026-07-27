import type {
  TranslationWorkspace,
  TranslationWorkspaceStatus,
  WorkspaceApiRecord
} from '~/types/translation-workspace'
import { resolveLanguage } from '~/constants/supported-languages'
import {
  type Kind,
  WorkspaceCreateRequest,
  WorkspaceKind,
  type WorkspaceResponse,
  WorkspaceUpdateRequest
} from '~~/shared/api-services/srv-core.client'

const statuses = new Set<TranslationWorkspaceStatus>([
  'needs_setup',
  'ready',
  'running',
  'completed',
  'stopped',
  'failed'
])

export function normalizeTranslationWorkspace(record: WorkspaceApiRecord): TranslationWorkspace {
  const novel = record.novel
  const total = Number(novel?.chapterCount || 0)
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
    configuration: null,
    chapters: [],
    updatedAt: record.updatedAt,
    etag: record.etag || null
  }
}

function toApiRecord(response: WorkspaceResponse): WorkspaceApiRecord {
  return response.toJSON() as unknown as WorkspaceApiRecord
}

export function useTranslationWorkspaceApi() {
  const { workspaces } = useApiClient()
  return {
    async list() {
      const response = await workspaces.list_workspaces(
        WorkspaceKind.Translation as unknown as Kind,
        50,
        undefined
      )
      return response.items.map(item => normalizeTranslationWorkspace(toApiRecord(item)))
    },
    async get(id: string) {
      return normalizeTranslationWorkspace(
        toApiRecord(await workspaces.get_workspace(id))
      )
    },
    async create(body: {
      name: string
      novelId: string
      targetLanguage: string
    }) {
      const response = await workspaces.create_workspace(
        new WorkspaceCreateRequest({
          ...body,
          kind: WorkspaceKind.Translation
        })
      )
      return toApiRecord(response)
    },
    async update(
      id: string,
      body: {
        name: string
        novelId: string
        targetLanguage: string
        etag?: string | null
      }
    ) {
      const response = await workspaces.update_workspace(
        id,
        new WorkspaceUpdateRequest({
          ...body,
          etag: body.etag as never
        })
      )
      return toApiRecord(response)
    },
    async delete(id: string) {
      return workspaces.delete_workspace(id)
    }
  }
}
