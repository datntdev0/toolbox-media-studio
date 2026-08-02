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

export const translationProviders: TranslationProviderOption[] = [
  {
    id: 'foundry',
    label: 'Built-in Microsoft Foundry',
    icon: 'simple-icons:microsoft',
    models: [
      {
        id: 'gpt-5-mini',
        label: 'GPT-5 mini',
        description: 'Balanced quality and throughput for chapter translation.'
      },
      {
        id: 'gpt-5-nano',
        label: 'GPT-5 nano',
        description: 'Fast, economical translation for quick previews.'
      }
    ]
  }
]

export const DEFAULT_TRANSLATION_PROMPT = 'You are a professional literary translator. Translate faithfully while preserving names, dialogue, tone, paragraph breaks, and narrative intent.'

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
  taskExists: boolean
  chapterIndex: number
  number: number
  title: string
  translatedTitle: string | null
  status: TranslationChapterStatus
  originalParagraphs: string[]
  translatedParagraphs: string[]
  attempts: number
  lastError: string | null
  resultAvailable: boolean
  contentAvailable: boolean
  sourceUpdated: boolean
  sourceRemoved: boolean
}

export interface TranslationResult {
  title: string
  content: string[]
}

export interface TranslationWorkspace {
  id: string
  name: string
  novelId: string
  novelTitle: string
  novelChapterCount: number
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

export interface TranslationListApiRecord {
  items: TranslationApiRecord[]
  continuationToken?: string | null
}
