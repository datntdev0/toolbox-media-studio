import type {
  NovelChapterContent,
  NovelMutationResult,
  NovelWorkspace,
  ScrapingSearchPage
} from '~/types/novel-workspace'
import {
  NovelBindRequest,
  NovelChapterUpdateRequest,
  type Anonymous2,
  type NovelChapterContentResponse,
  type NovelDetailResponse,
  type NovelSyncResponse,
  type ScrapingDetailResponse,
  type ScrapingListResponse,
  type Search
} from '~~/shared/api-services/srv-core.client'

function normalizeChapterContent(payload: NovelChapterContentResponse): NovelChapterContent {
  const content = payload.content
  return {
    id: String(payload.id || ''),
    title: String(payload.title || ''),
    content: Array.isArray(content) ? content.map(String).join('\n\n') : String(content || ''),
    etag: payload.etag ? String(payload.etag) : null,
    updatedAt: payload.updatedAt ? String(payload.updatedAt) : null
  }
}

function normalizeWorkspace(payload: NovelDetailResponse): NovelWorkspace {
  return payload.toJSON() as unknown as NovelWorkspace
}

function normalizeMutation(payload: NovelSyncResponse): NovelMutationResult {
  return payload.toJSON() as unknown as NovelMutationResult
}

function normalizeScrapingPage(payload: ScrapingListResponse): ScrapingSearchPage {
  return payload.toJSON() as unknown as ScrapingSearchPage
}

function normalizeScraping(payload: ScrapingDetailResponse): ScrapingSearchPage['items'][number] {
  return {
    id: String(payload.id),
    crawlerId: String(payload.crawlerId),
    sourceUrl: String(payload.sourceUrl),
    title: String(payload.metadata.title),
    coverImageUrl: payload.metadata.coverImageUrl
      ? String(payload.metadata.coverImageUrl)
      : null,
    progress: {
      total: Number(payload.progress.total || 0),
      completed: Number(payload.progress.completed || 0),
      created: Number(payload.progress.created || 0),
      queued: Number(payload.progress.queued || 0),
      running: Number(payload.progress.running || 0),
      failed: Number(payload.progress.failed || 0)
    },
    updatedAt: payload.updatedAt.toISOString()
  }
}

/** Adapts the generated API client to the reader/editor view model. */
export function useNovelWorkspaceApi() {
  return {
    async getNovel(id: string) {
      const { novels } = useApiClient()
      return normalizeWorkspace(await novels.get_novel(id))
    },
    async getChapter(novelId: string, chapterId: string) {
      const { novels } = useApiClient()
      return normalizeChapterContent(
        await novels.get_novel_chapter(novelId, chapterId, undefined)
      )
    },
    async getScraping(id: string) {
      const { scrapings } = useApiClient()
      return normalizeScraping(await scrapings.get_scraping(id))
    },
    async editChapter(novelId: string, chapterId: string, content: string, etag?: string | null) {
      if (!etag) throw new Error('Chapter concurrency token is unavailable')
      const { novels } = useApiClient()
      const response = await novels.update_novel_chapter(
        novelId,
        chapterId,
        new NovelChapterUpdateRequest({ content, etag })
      )
      return normalizeChapterContent(response)
    },
    async bind(novelId: string, scrapingId: string) {
      const { novels } = useApiClient()
      return normalizeMutation(
        await novels.bind_novel(novelId, new NovelBindRequest({ scrapingId }))
      )
    },
    async sync(novelId: string) {
      const { novels } = useApiClient()
      return normalizeMutation(await novels.sync_novel(novelId))
    },
    async searchScrapings(search: string, limit = 20, continuationToken?: string | null) {
      const { scrapings } = useApiClient()
      const response = await scrapings.list_scrapings(
        limit,
        continuationToken
          ? continuationToken as unknown as Anonymous2
          : undefined,
        search.trim()
          ? search.trim() as unknown as Search
          : undefined
      )
      return normalizeScrapingPage(response)
    }
  }
}
