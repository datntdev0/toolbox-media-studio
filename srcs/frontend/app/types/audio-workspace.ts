export type AudioWorkspaceSourceType = 'original' | 'translation'

export interface AudioLanguageOption {
  code: string
  sourceType: AudioWorkspaceSourceType
}

export interface AudioWorkspaceNovel {
  id: string
  title: string
  description: string | null
  coverImageUrl: string | null
  language: string | null
  author: string | null
  tags: string[]
  status: string
  chapterCount: number
}

export interface AudioWorkspaceChapter {
  id: string
  title: string
  chapterNumber: number | null
  manifestIndex: number
  contentAvailable: boolean
  sourceUpdated: boolean
  sourceRemoved: boolean
}

export type AudioWorkspaceTaskStatus
  = | 'created'
    | 'queued'
    | 'running'
    | 'completed'
    | 'failed'

export interface AudioWorkspaceTask {
  id: string
  title: string
  chapterNumber: number | null
  manifestIndex: number
  status: AudioWorkspaceTaskStatus
  attempts: number
  lastError: string | null
  resultAvailable: boolean
  completedAt: string | null
  sourceChapterUpdatedAt: string
  sourceUpdated: boolean
  sourceRemoved: boolean
  provider: string | null
  voice: string | null
}

export interface AudioWorkspaceProgress {
  total: number
  created: number
  queued: number
  running: number
  completed: number
  failed: number
}

export interface AudioWorkspace {
  id: string
  title: string
  type: 'audio'
  novelId: string
  language: string
  sourceType: AudioWorkspaceSourceType
  sourceAvailable: boolean
  chapterCount: number
  novel: AudioWorkspaceNovel | null
  chapters: AudioWorkspaceChapter[]
  tasks: AudioWorkspaceTask[]
  progress: AudioWorkspaceProgress
  createdAt: string
  updatedAt: string
}

export interface AudioChapterContent {
  id: string
  title: string
  chapterNumber: number | null
  content: string[]
}

export interface AudioWorkspaceTaskResultSentence {
  index: number
  audioUrl: string
}

export interface AudioWorkspaceTaskResult {
  taskId: string
  workspaceId: string
  provider: string
  voice: string
  sentences: AudioWorkspaceTaskResultSentence[]
  createdAt: string
  updatedAt: string
}
