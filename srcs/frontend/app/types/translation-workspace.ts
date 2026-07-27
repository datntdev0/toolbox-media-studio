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

export interface TranslationConfiguration {
  providerId: string
  providerName: string
  modelId: string
  modelName: string
  globalPrompt: string
  previewChapterId: string
  previewParagraphs: string[]
  previewGeneratedAt: string
}

export interface TranslationProgress {
  total: number
  translated: number
  queued: number
  running: number
  failed: number
}

export interface TranslationChapter {
  id: string
  number: number
  title: string
  status: TranslationChapterStatus
  originalParagraphs: string[]
  translatedParagraphs: string[]
}

export interface TranslationWorkspace {
  id: string
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
}
