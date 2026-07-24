<script setup lang="ts">
import { breakpointsTailwind } from '@vueuse/core'
import {
  ScrapingSummaryResponse,
  type Anonymous8,
  type CrawlerSummaryResponse,
  type ScrapingCreateResponse,
  type ScrapingDetailResponse
} from '~~/shared/api-services/srv-core.client'

definePageMeta({
  title: 'Scrapings'
})

useHead({ title: 'Scrapings' })

type ScrapingUpdatedPayload = {
  scrapingId: string
  taskId?: string
}

const route = useRoute()
const router = useRouter()
const breakpoints = useBreakpoints(breakpointsTailwind)
const isMobile = breakpoints.smaller('lg')

const scrapings = ref<ScrapingSummaryResponse[]>([])
const continuationToken = ref<string | null>(null)
const loading = ref(true)
const loadingMore = ref(false)
const listError = ref(false)
const newScrapingOpen = ref(false)
const crawlerNames = ref<Record<string, string>>({})
const listRef = ref<{ focusSelected: () => void, focusRow: (id: string) => void } | null>(null)
const detailRef = ref<{ refresh: () => void } | null>(null)
const selectionPushed = ref(false)
const listRequestInFlight = ref(false)
const pendingListRefresh = ref(false)
const deletingId = ref<string | null>(null)
const confirm = useConfirmDialog()
const toast = useToast()
const pendingRealtimeScrapingIds = new Set<string>()
let realtimeRefreshTimer: ReturnType<typeof setTimeout> | undefined

useRealtime().onMessage<ScrapingUpdatedPayload>('scraping.updated', ({ payload }) => {
  if (!payload.scrapingId) return
  pendingRealtimeScrapingIds.add(payload.scrapingId)
  if (realtimeRefreshTimer) return

  realtimeRefreshTimer = setTimeout(() => {
    realtimeRefreshTimer = undefined
    const refreshSelected = selectedId.value
      ? pendingRealtimeScrapingIds.has(selectedId.value)
      : false
    pendingRealtimeScrapingIds.clear()
    void loadScrapings()
    if (refreshSelected) detailRef.value?.refresh()
  }, 200)
})

const selectedId = computed(() => {
  const value = route.query.id
  return typeof value === 'string' && value ? value : null
})

const mobileDetailOpen = computed({
  get: () => Boolean(selectedId.value && isMobile.value),
  set: (value: boolean) => {
    if (!value) closeDetail()
  }
})

onMounted(() => {
  void Promise.all([loadScrapings(), loadCrawlerNames()])
})

onBeforeUnmount(() => {
  if (realtimeRefreshTimer) clearTimeout(realtimeRefreshTimer)
})

async function loadCrawlerNames() {
  try {
    const { crawlers } = useApiClient()
    const response = await crawlers.list_crawlers()
    setCrawlerNames(response.items || [])
  } catch {
    // Crawler names are enhancement text; source hosts remain as the fallback.
  }
}

function setCrawlerNames(crawlers: CrawlerSummaryResponse[]) {
  crawlerNames.value = Object.fromEntries(crawlers.map(item => [item.id, item.name]))
}

function mergeScrapings(
  current: ScrapingSummaryResponse[],
  incoming: ScrapingSummaryResponse[],
  prependIncoming = false
) {
  const ordered = prependIncoming ? [...incoming, ...current] : [...current, ...incoming]
  return [...new Map(ordered.map(item => [item.id, item])).values()]
}

async function loadScrapings(options: { more?: boolean } = {}) {
  if (listRequestInFlight.value) {
    if (!options.more) pendingListRefresh.value = true
    return
  }
  listRequestInFlight.value = true

  if (options.more) loadingMore.value = true
  else loading.value = true

  try {
    const { scrapings: client } = useApiClient()
    const token = options.more && continuationToken.value
      ? continuationToken.value as unknown as Anonymous8
      : undefined
    const response = await client.list_scrapings(50, token, undefined)
    const incoming = response.items || []

    if (options.more) {
      scrapings.value = mergeScrapings(scrapings.value, incoming)
    } else {
      scrapings.value = mergeScrapings([], incoming)
    }

    continuationToken.value = response.continuationToken
      ? String(response.continuationToken)
      : null
    listError.value = false
  } catch {
    listError.value = true
  } finally {
    loading.value = false
    loadingMore.value = false
    listRequestInFlight.value = false
    if (pendingListRefresh.value) {
      pendingListRefresh.value = false
      void loadScrapings()
    }
  }
}

function routeQueryWithSelection(id?: string) {
  const query = { ...route.query }
  delete query.scraping
  if (id) query.id = id
  else delete query.id
  return query
}

async function selectScraping(id: string) {
  if (selectedId.value === id) return
  if (selectedId.value) {
    await router.replace({ query: routeQueryWithSelection(id) })
  } else {
    selectionPushed.value = true
    await router.push({ query: routeQueryWithSelection(id) })
  }
}

function focusListRow(id: string) {
  void nextTick(() => listRef.value?.focusRow(id))
}

async function closeDetail() {
  const closedId = selectedId.value
  if (!closedId) return

  if (selectionPushed.value) {
    selectionPushed.value = false
    router.back()
  } else {
    await router.replace({ query: routeQueryWithSelection() })
  }

  setTimeout(() => focusListRow(closedId), 0)
}

async function clearInaccessibleSelection() {
  const closedId = selectedId.value
  selectionPushed.value = false
  await router.replace({ query: routeQueryWithSelection() })
  if (closedId) focusListRow(closedId)
}

function onCreated(created: ScrapingCreateResponse) {
  scrapings.value = mergeScrapings(
    scrapings.value,
    [created as ScrapingSummaryResponse],
    true
  )
  void selectScraping(created.id)
}

async function deleteScraping(scraping: ScrapingSummaryResponse) {
  const confirmed = await confirm({
    title: 'Delete scraping',
    description: `Delete “${scraping.title}” and its downloaded chapter content? This cannot be undone.`,
    confirmLabel: 'Delete scraping',
    confirmColor: 'error'
  })
  if (!confirmed) return

  deletingId.value = scraping.id
  try {
    const { scrapings: client } = useApiClient()
    await client.delete_scraping(scraping.id)
    scrapings.value = scrapings.value.filter(item => item.id !== scraping.id)

    if (selectedId.value === scraping.id) {
      selectionPushed.value = false
      await router.replace({ query: routeQueryWithSelection() })
    }

    toast.add({
      title: 'Scraping deleted',
      description: `“${scraping.title}” and its downloaded chapters were removed.`,
      icon: 'lucide:trash-2',
      color: 'success'
    })
  } catch {
    toast.add({
      title: 'Unable to delete scraping',
      description: 'The scraping could not be deleted. Please try again.',
      icon: 'lucide:circle-alert',
      color: 'error'
    })
  } finally {
    deletingId.value = null
  }
}

function onDetailUpdated(detail: ScrapingDetailResponse) {
  const existing = scrapings.value.find(item => item.id === detail.id)
  if (existing) {
    existing.status = detail.status
    existing.title = detail.metadata.title
    existing.coverImageUrl = detail.metadata.coverImageUrl
    existing.updatedAt = detail.updatedAt
    existing.progress.total = detail.progress.total
    existing.progress.completed = detail.progress.completed
    existing.progress.failed = detail.progress.failed
    return
  }

  scrapings.value = mergeScrapings(scrapings.value, [
    new ScrapingSummaryResponse({
      id: detail.id,
      crawlerId: detail.crawlerId,
      sourceUrl: detail.sourceUrl,
      title: detail.metadata.title,
      coverImageUrl: detail.metadata.coverImageUrl,
      status: detail.status,
      progress: detail.progress,
      attempts: detail.attempts,
      createdAt: detail.createdAt,
      updatedAt: detail.updatedAt
    })
  ], true)
}
</script>

<template>
  <ScrapingsScrapingList
    ref="listRef"
    :scrapings="scrapings"
    :selected-id="selectedId"
    :crawler-names="crawlerNames"
    :loading="loading"
    :loading-more="loadingMore"
    :error="listError"
    :can-load-more="Boolean(continuationToken)"
    :deleting-id="deletingId"
    @select="selectScraping"
    @delete="deleteScraping"
    @create="newScrapingOpen = true"
    @retry="loadScrapings()"
    @load-more="loadScrapings({ more: true })"
  />

  <ScrapingsScrapingDetail
    v-if="selectedId && !isMobile"
    ref="detailRef"
    :scraping-id="selectedId"
    :crawler-name="crawlerNames[scrapings.find(item => item.id === selectedId)?.crawlerId || '']"
    @close="closeDetail"
    @inaccessible="clearInaccessibleSelection"
    @updated="onDetailUpdated"
  />

  <div
    v-else-if="!isMobile"
    class="hidden flex-1 items-center justify-center p-8 lg:flex"
  >
    <UEmpty
      icon="lucide:book-down"
      title="Select a scraping"
      description="Choose a scraping to view its novel and downloaded chapters."
      size="xl"
    />
  </div>

  <ClientOnly>
    <USlideover
      v-if="isMobile"
      v-model:open="mobileDetailOpen"
      :close="false"
      :ui="{ content: 'w-full max-w-3xl' }"
    >
      <template #content>
        <ScrapingsScrapingDetail
          v-if="selectedId"
          ref="detailRef"
          :scraping-id="selectedId"
          :crawler-name="crawlerNames[scrapings.find(item => item.id === selectedId)?.crawlerId || '']"
          @close="closeDetail"
          @inaccessible="clearInaccessibleSelection"
          @updated="onDetailUpdated"
        />
      </template>
    </USlideover>
  </ClientOnly>

  <ScrapingsNewScrapingModal
    v-model:open="newScrapingOpen"
    @created="onCreated"
    @crawlers-loaded="setCrawlerNames"
  />
</template>
