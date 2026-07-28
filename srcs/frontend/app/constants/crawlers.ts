export type SupportedCrawler = {
  id: string
  name: string
  hosts: string[]
  metadataSupported: boolean
}

export const SUPPORTED_CRAWLERS: SupportedCrawler[] = [
  {
    id: 'novel543',
    name: 'Novel543',
    hosts: ['www.novel543.com'],
    metadataSupported: true
  }
]
