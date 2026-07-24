import { format, formatDistanceToNowStrict } from 'date-fns'
import {
  ScrapingTaskStatus,
  type ScrapingProgressResponse
} from '~~/shared/api-services/srv-core.client'

export const scrapingTaskStatusMeta = {
  [ScrapingTaskStatus.Created]: {
    label: 'Created',
    color: 'neutral',
    icon: 'lucide:circle-dashed'
  },
  [ScrapingTaskStatus.Queued]: {
    label: 'Queued',
    color: 'neutral',
    icon: 'lucide:clock-3'
  },
  [ScrapingTaskStatus.Running]: {
    label: 'Running',
    color: 'primary',
    icon: 'lucide:loader-circle'
  },
  [ScrapingTaskStatus.Completed]: {
    label: 'Downloaded',
    color: 'success',
    icon: 'lucide:circle-check'
  },
  [ScrapingTaskStatus.Failed]: {
    label: 'Failed',
    color: 'error',
    icon: 'lucide:circle-x'
  }
} as const

export function scrapingActivityMeta(progress: ScrapingProgressResponse) {
  if (progress.running > 0) {
    return {
      label: `${progress.running} running`,
      color: 'primary' as const,
      icon: 'lucide:loader-circle',
      spinning: true
    }
  }
  if (progress.queued > 0) {
    return {
      label: `${progress.queued} queued`,
      color: 'neutral' as const,
      icon: 'lucide:clock-3',
      spinning: false
    }
  }
  if (progress.failed > 0) {
    return {
      label: `${progress.failed} failed`,
      color: 'error' as const,
      icon: 'lucide:circle-x',
      spinning: false
    }
  }
  if (progress.completed === progress.total && progress.total > 0) {
    return {
      label: 'Downloaded',
      color: 'success' as const,
      icon: 'lucide:circle-check',
      spinning: false
    }
  }
  return {
    label: `${progress.created} ready`,
    color: 'neutral' as const,
    icon: 'lucide:circle-dashed',
    spinning: false
  }
}

export function isActiveScraping(progress: ScrapingProgressResponse) {
  return progress.queued > 0 || progress.running > 0
}

export function formatRelativeTime(value: Date | string | undefined) {
  if (!value) return 'Unknown'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return 'Unknown'
  return formatDistanceToNowStrict(date, { addSuffix: true })
}

export function formatExactTime(value: Date | string | undefined) {
  if (!value) return 'Unknown time'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return 'Unknown time'
  return format(date, 'PPpp')
}

export function sourceHost(value: string | undefined) {
  if (!value) return 'Unknown source'
  try {
    return new URL(value).hostname.replace(/^www\./, '')
  } catch {
    return value
  }
}
