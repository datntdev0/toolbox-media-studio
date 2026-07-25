export interface ScrapingProgress {
  total: number
  completed: number
  created?: number
  queued?: number
  running?: number
  failed?: number
}

export interface NovelBinding {
  scrapingId: string
  boundAt: string
  lastSyncedAt: string
}

export interface NovelChapterSummary {
  id: string
  title: string
  manifestIndex: number
  chapterNumber?: number | null
  contentAvailable: boolean
  manuallyEdited: boolean
  sourceUpdated: boolean
  sourceRemoved: boolean
  updatedAt?: string | null
  etag?: string | null
}

export interface NovelWorkspace {
  id: string
  title: string
  description?: unknown
  coverImageUrl?: unknown
  language?: unknown
  author?: unknown
  tags: string[]
  notes?: unknown
  status: string
  createdAt: string
  updatedAt: string
  etag?: string | null
  chapterCount: number
  binding?: NovelBinding | null
  chapters: NovelChapterSummary[]
}

export interface NovelChapterContent {
  id: string
  title: string
  content: string
  etag?: string | null
  updatedAt?: string | null
}

export interface NovelSyncChanges {
  added: number
  refreshed: number
  preserved: number
  removed: number
}

export interface NovelMutationResult {
  novel: NovelWorkspace
  changes: NovelSyncChanges
}

export interface ScrapingSearchItem {
  id: string
  crawlerId: string
  sourceUrl: string
  title: string
  coverImageUrl?: string | null
  progress: ScrapingProgress
  updatedAt: string
}

export interface ScrapingSearchPage {
  items: ScrapingSearchItem[]
  continuationToken?: string | null
}
