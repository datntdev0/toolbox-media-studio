import {
  AuthClient,
  CrawlersClient,
  NovelsClient,
  ScrapingsClient,
  UsersClient
} from '~~/shared/api-services/srv-core.client'

type GeneratedHttp = {
  fetch(url: RequestInfo, init?: RequestInit): Promise<Response>
}

/** Creates NSwag clients configured for the current runtime and auth token. */
export function useApiClient() {
  const config = useRuntimeConfig()
  const token = useState<string | null>('auth:access-token', () => null)
  const baseUrl = String(config.public.servUrl || '').replace(/\/+$/, '')

  const http: GeneratedHttp = {
    fetch(url, init = {}) {
      const headers = new Headers(init.headers)
      if (token.value) headers.set('Authorization', `Bearer ${token.value}`)

      return globalThis.fetch(url, {
        ...init,
        headers
      })
    }
  }

  return {
    auth: new AuthClient(baseUrl, http),
    users: new UsersClient(baseUrl, http),
    novels: new NovelsClient(baseUrl, http),
    crawlers: new CrawlersClient(baseUrl, http),
    scrapings: new ScrapingsClient(baseUrl, http)
  }
}
