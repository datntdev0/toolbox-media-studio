import {
  AuthClient,
  CrawlersClient,
  NovelsClient,
  NovelResponse,
  ScrapingsClient,
  ScrapingDetailResponse,
  UsersClient,
  WorkspacesClient
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
    scrapings: new ScrapingsClient(baseUrl, http),
    workspaces: new WorkspacesClient(baseUrl, http),
    async createNovel(body: Record<string, unknown>) {
      const response = await http.fetch(`${baseUrl}/api/novels`, {
        method: 'POST',
        body: JSON.stringify(body),
        headers: { 'Accept': 'application/json', 'Content-Type': 'application/json' }
      })
      if (!response.ok) throw new Error('Unable to create novel')
      return NovelResponse.fromJS(await response.json())
    },
    async updateNovel(id: string, body: Record<string, unknown>) {
      const response = await http.fetch(`${baseUrl}/api/novels/${encodeURIComponent(id)}`, {
        method: 'PUT',
        body: JSON.stringify(body),
        headers: { 'Accept': 'application/json', 'Content-Type': 'application/json' }
      })
      if (!response.ok) throw new Error('Unable to update novel')
      return NovelResponse.fromJS(await response.json())
    },
    async deleteNovel(id: string) {
      const response = await http.fetch(`${baseUrl}/api/novels/${encodeURIComponent(id)}`, { method: 'DELETE' })
      if (!response.ok) throw new Error('Unable to delete novel')
    },
    async updateScraping(id: string, form: FormData) {
      const response = await http.fetch(`${baseUrl}/api/scrapings/${encodeURIComponent(id)}`, {
        method: 'PUT',
        body: form,
        headers: { Accept: 'application/json' }
      })
      if (!response.ok) throw new Error('Unable to update scraping')
      return ScrapingDetailResponse.fromJS(await response.json())
    }
  }
}
