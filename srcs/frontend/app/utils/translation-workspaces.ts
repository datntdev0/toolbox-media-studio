import type {
  TranslationChapterStatus,
  TranslationWorkspaceStatus
} from '~/types/translation-workspace'

export const workspaceStatusMeta: Record<TranslationWorkspaceStatus, {
  label: string
  color: 'neutral' | 'primary' | 'success' | 'warning' | 'error'
  icon: string
}> = {
  needs_setup: {
    label: 'Needs setup',
    color: 'warning',
    icon: 'lucide:settings-2'
  },
  ready: {
    label: 'Ready',
    color: 'neutral',
    icon: 'lucide:circle-dashed'
  },
  running: {
    label: 'Running',
    color: 'primary',
    icon: 'lucide:loader-circle'
  },
  completed: {
    label: 'Completed',
    color: 'success',
    icon: 'lucide:circle-check'
  },
  stopped: {
    label: 'Stopped',
    color: 'neutral',
    icon: 'lucide:circle-stop'
  },
  failed: {
    label: 'Failed',
    color: 'error',
    icon: 'lucide:circle-x'
  }
}

export const chapterStatusMeta: Record<TranslationChapterStatus, {
  label: string
  shortLabel: string
  color: 'neutral' | 'primary' | 'success' | 'warning' | 'error'
  icon: string
}> = {
  not_started: {
    label: 'Not started',
    shortLabel: 'Not started',
    color: 'neutral',
    icon: 'lucide:circle-dashed'
  },
  queued: {
    label: 'Queued for translation',
    shortLabel: 'Queued',
    color: 'neutral',
    icon: 'lucide:clock-3'
  },
  translating: {
    label: 'Translation in progress',
    shortLabel: 'Translating',
    color: 'primary',
    icon: 'lucide:loader-circle'
  },
  translated: {
    label: 'Translated',
    shortLabel: 'Translated',
    color: 'success',
    icon: 'lucide:circle-check'
  },
  manually_edited: {
    label: 'Manually edited',
    shortLabel: 'Edited',
    color: 'success',
    icon: 'lucide:pencil-line'
  },
  unavailable: {
    label: 'Source unavailable',
    shortLabel: 'Unavailable',
    color: 'warning',
    icon: 'lucide:file-clock'
  },
  failed: {
    label: 'Translation failed',
    shortLabel: 'Failed',
    color: 'error',
    icon: 'lucide:circle-x'
  }
}

export function formatWorkspaceDate(value: string) {
  return new Intl.DateTimeFormat(undefined, {
    month: 'short',
    day: 'numeric',
    year: 'numeric'
  }).format(new Date(value))
}
