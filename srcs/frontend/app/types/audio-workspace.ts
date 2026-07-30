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
  createdAt: string
  updatedAt: string
}

export interface AudioChapterContent {
  id: string
  title: string
  chapterNumber: number | null
  content: string[]
}
