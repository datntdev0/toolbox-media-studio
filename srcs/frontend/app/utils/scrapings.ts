import { format, formatDistanceToNowStrict } from 'date-fns'
import {
  ScrapingStatus,
  ScrapingTaskStatus
} from '~~/shared/api-services/srv-core.client'

export const scrapingStatusMeta = {
  [ScrapingStatus.Queued]: {
    label: 'Queued',
    color: 'neutral',
    icon: 'lucide:clock-3'
  },
  [ScrapingStatus.Processing]: {
    label: 'Processing',
    color: 'primary',
    icon: 'lucide:loader-circle'
  },
  [ScrapingStatus.Retrying]: {
    label: 'Retrying',
    color: 'warning',
    icon: 'lucide:rotate-ccw'
  },
  [ScrapingStatus.Completed]: {
    label: 'Completed',
    color: 'success',
    icon: 'lucide:circle-check'
  },
  [ScrapingStatus.Failed]: {
    label: 'Failed',
    color: 'error',
    icon: 'lucide:circle-x'
  }
} as const

export const scrapingTaskStatusMeta = {
  [ScrapingTaskStatus.Pending]: {
    label: 'Pending',
    color: 'neutral',
    icon: 'lucide:clock-3'
  },
  [ScrapingTaskStatus.Processing]: {
    label: 'Processing',
    color: 'primary',
    icon: 'lucide:loader-circle'
  },
  [ScrapingTaskStatus.Retrying]: {
    label: 'Retrying',
    color: 'warning',
    icon: 'lucide:rotate-ccw'
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

export function isActiveScraping(status: ScrapingStatus) {
  return status !== ScrapingStatus.Completed && status !== ScrapingStatus.Failed
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
