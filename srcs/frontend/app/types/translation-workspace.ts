export type TranslationWorkspaceStatus
  = | 'needs_setup'
    | 'ready'
    | 'running'
    | 'completed'
    | 'stopped'
    | 'failed'

export type TranslationChapterStatus
  = | 'not_started'
    | 'queued'
    | 'translating'
    | 'translated'
    | 'manually_edited'
    | 'unavailable'
    | 'failed'

export interface TranslationLanguageOption {
  code: string
  label: string
  nativeLabel: string
}

export interface TranslationNovelOption {
  id: string
  title: string
  sourceLanguage: TranslationLanguageOption
  chapterCount: number
  coverImageUrl: string | null
}

export interface TranslationModelOption {
  id: string
  label: string
  description: string
}

export interface TranslationProviderOption {
  id: string
  label: string
  icon: string
  models: TranslationModelOption[]
}

export interface TranslationConfigurationInput {
  providerId: string
  modelId: string
  globalPrompt: string
}

export interface TranslationConfiguration extends TranslationConfigurationInput {
  providerName: string
  modelName: string
}

export interface TranslationProgress {
  total: number
  created: number
  translated: number
  queued: number
  running: number
  failed: number
}

export interface TranslationChapter {
  id: string
  chapterIndex: number
  number: number
  title: string
  status: TranslationChapterStatus
  originalParagraphs: string[]
  translatedParagraphs: string[]
  attempts: number
  lastError: string | null
  resultAvailable: boolean
  sourceUpdated: boolean
  sourceRemoved: boolean
}

export interface TranslationWorkspace {
  id: string
  name: string
  novelId: string
  novelTitle: string
  coverImageUrl: string | null
  sourceLanguage: TranslationLanguageOption
  targetLanguage: TranslationLanguageOption
  status: TranslationWorkspaceStatus
  progress: TranslationProgress
  configuration: TranslationConfiguration | null
  chapters: TranslationChapter[]
  updatedAt: string
  etag: string | null
}

export interface TranslationNovelApiRecord {
  id: string
  title: string
  coverImageUrl?: string | null
  language?: string | null
  chapterCount?: number
}

export interface TranslationApiRecord {
  id: string
  name: string
  novelId: string
  targetLanguage: string
  configuration?: TranslationConfigurationInput | null
  status: TranslationWorkspaceStatus
  novel?: TranslationNovelApiRecord | null
  createdAt: string
  updatedAt: string
  etag?: string | null
}

export interface TranslationTaskApiRecord {
  id: string
  title: string
  chapterNumber?: number | null
  manifestIndex: number
  status: 'created' | 'queued' | 'running' | 'completed' | 'failed'
  attempts: number
  lastError?: string | null
  resultAvailable: boolean
  completedAt?: string | null
  sourceChapterUpdatedAt: string
  sourceUpdated: boolean
  sourceRemoved: boolean
}

export interface TranslationDetailApiRecord extends TranslationApiRecord {
  progress: {
    total: number
    created: number
    queued: number
    running: number
    completed: number
    failed: number
  }
  tasks?: TranslationTaskApiRecord[]
}

export interface TranslationSyncChanges {
  added: number
  refreshed: number
  preserved: number
  removed: number
}

export interface TranslationListApiRecord {
  items: TranslationApiRecord[]
  continuationToken?: string | null
}
