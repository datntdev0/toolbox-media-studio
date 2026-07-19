import type { AvatarProps } from '@nuxt/ui'
import type { UserRole } from '~~/shared/api-services/srv-core.client'

// NSwag's Fetch template defaults to `window` when no HTTP implementation is
// supplied. The application always supplies one, but this declaration keeps
// the generated module type-checkable in Nuxt's server TypeScript context.
declare global {
  const window: Record<string, unknown>
}

declare module '#app' {
  interface PageMeta {
    auth?: {
      roles?: UserRole[]
    }
  }
}

export {}

export type UserStatus = 'subscribed' | 'unsubscribed' | 'bounced'
export type SaleStatus = 'paid' | 'failed' | 'refunded'

export interface User {
  id: number
  name: string
  email: string
  avatar?: AvatarProps
  status: UserStatus
  location: string
}

export interface Mail {
  id: number
  unread?: boolean
  from: User
  subject: string
  body: string
  date: string
}

export interface Member {
  name: string
  username: string
  role: 'member' | 'owner'
  avatar: AvatarProps
}

export interface Stat {
  title: string
  icon: string
  value: number | string
  variation: number
  formatter?: (value: number) => string
}

export interface Sale {
  id: string
  date: string
  status: SaleStatus
  email: string
  amount: number
}

export interface Notification {
  id: number
  unread?: boolean
  sender: User
  body: string
  date: string
}

export type Period = 'daily' | 'weekly' | 'monthly'

export interface Range {
  start: Date
  end: Date
}
