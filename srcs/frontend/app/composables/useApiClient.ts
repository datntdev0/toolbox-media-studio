import {
  AuthClient,
  NovelsClient,
  NovelResponse,
  ScrapingsClient,
  ScrapingDetailResponse,
  TranslationsClient,
  UsersClient,
  WorkspacesClient
} from '~~/shared/api-services/srv-core.client'

type GeneratedHttp = {
  fetch(url: RequestInfo, init?: RequestInit): Promise<Response>
}

type NovelExportDownload = {
  blob: Blob
  filename: string
}

function exportErrorMessage(payload: unknown): string | null {
  if (!payload || typeof payload !== 'object') return null
  const detail = (payload as { detail?: unknown }).detail
  if (typeof detail === 'string' && detail.trim()) return detail
  if (!Array.isArray(detail)) return null

  const messages = detail
    .map(item => typeof item === 'object' && item
      ? (item as { msg?: unknown }).msg
      : null)
    .filter((message): message is string => typeof message === 'string' && Boolean(message.trim()))
  return messages.length ? messages.join(', ') : null
}

async function getResponseErrorMessage(response: Response, fallback: string): Promise<string> {
  try {
    const message = exportErrorMessage(await response.json())
    if (message) return message
  } catch {
    // Keep the fallback when the server did not return a JSON error body.
  }
  return fallback
}

function exportFilename(contentDisposition: string | null): string {
  const encodedMatch = contentDisposition?.match(/filename\*=UTF-8''([^;]+)/i)
  const plainMatch = contentDisposition?.match(/filename=(?:"([^"]+)"|([^;\s]+))/i)
  const encodedFilename = encodedMatch?.[1]
  const rawFilename = encodedFilename
    ? (() => {
        try {
          return decodeURIComponent(encodedFilename)
        } catch {
          return encodedFilename
        }
      })()
    : plainMatch?.[1] || plainMatch?.[2] || 'novel-export.zip'
  const safeFilename = [...rawFilename]
    .filter((character) => {
      const code = character.charCodeAt(0)
      return code >= 32 && code !== 127 && character !== '/' && character !== '\\'
    })
    .join('')
    .trim()
  return safeFilename.toLowerCase().endsWith('.zip')
    ? safeFilename || 'novel-export.zip'
    : `${safeFilename || 'novel-export'}.zip`
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
    scrapings: new ScrapingsClient(baseUrl, http),
    translations: new TranslationsClient(baseUrl, http),
    workspaces: new WorkspacesClient(baseUrl, http),
    async downloadNovelExport(id: string): Promise<NovelExportDownload> {
      const response = await http.fetch(`${baseUrl}/api/novels/${encodeURIComponent(id)}/export`, {
        method: 'GET',
        headers: { Accept: 'application/zip' }
      })
      if (!response.ok) {
        throw new Error(await getResponseErrorMessage(response, 'Unable to export novel'))
      }
      return {
        blob: await response.blob(),
        filename: exportFilename(response.headers.get('Content-Disposition'))
      }
    },
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
    async uploadNovelCover(id: string, file: File) {
      const body = new FormData()
      body.set('coverImage', file)
      const response = await http.fetch(`${baseUrl}/api/novels/${encodeURIComponent(id)}/cover`, {
        method: 'PUT',
        body,
        headers: { Accept: 'application/json' }
      })
      if (!response.ok) throw new Error('Unable to upload novel cover')
      return NovelResponse.fromJS(await response.json())
    },
    async deleteNovel(id: string) {
      const response = await http.fetch(`${baseUrl}/api/novels/${encodeURIComponent(id)}`, { method: 'DELETE' })
      if (!response.ok) throw new Error('Unable to delete novel')
    },
    async previewTranslation(body: {
      provider: string
      model: string
      language: string
      instruction: string
      chapter: string
    }) {
      const response = await http.fetch(`${baseUrl}/api/translations/preview`, {
        method: 'POST',
        body: JSON.stringify(body),
        headers: { 'Accept': 'application/json', 'Content-Type': 'application/json' }
      })
      if (!response.ok) {
        let message = 'Unable to generate translation preview'
        try {
          const error = await response.json() as { detail?: string | Array<{ msg?: string }> }
          if (typeof error.detail === 'string') message = error.detail
          else if (Array.isArray(error.detail)) message = error.detail.map(item => item.msg).filter(Boolean).join(', ') || message
        } catch {
          // Keep the generic message when the server did not return JSON.
        }
        throw new Error(message)
      }
      return await response.json() as { title: string, content: string[] }
    },
    async updateScraping(id: string, body: Record<string, unknown>) {
      const response = await http.fetch(`${baseUrl}/api/scrapings/${encodeURIComponent(id)}`, {
        method: 'PUT',
        body: JSON.stringify(body),
        headers: { 'Accept': 'application/json', 'Content-Type': 'application/json' }
      })
      if (!response.ok) throw new Error('Unable to update scraping')
      return ScrapingDetailResponse.fromJS(await response.json())
    },
    async uploadScrapingCover(id: string, file: File) {
      const body = new FormData()
      body.set('coverImage', file)
      const response = await http.fetch(`${baseUrl}/api/scrapings/${encodeURIComponent(id)}/cover`, {
        method: 'PUT',
        body,
        headers: { Accept: 'application/json' }
      })
      if (!response.ok) throw new Error('Unable to upload scraping cover')
      return ScrapingDetailResponse.fromJS(await response.json())
    }
  }
}
