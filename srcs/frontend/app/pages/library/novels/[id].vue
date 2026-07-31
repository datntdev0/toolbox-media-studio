<script setup lang="ts">
import { breakpointsTailwind } from '@vueuse/core'
import type { NovelResponse } from '~~/shared/api-services/srv-core.client'
import type {
  NovelChapterContent,
  NovelChapterSummary,
  NovelMutationResult,
  NovelWorkspace,
  ScrapingSearchItem
} from '~/types/novel-workspace'

definePageMeta({ middleware: ['auth'] })

const route = useRoute()
const router = useRouter()
const toast = useToast()
const breakpoints = useBreakpoints(breakpointsTailwind)
const isMobile = breakpoints.smaller('lg')

const novel = ref<NovelWorkspace | null>(null)
const loading = ref(true)
const error = ref(false)
const bindOpen = ref(false)
const binding = ref(false)
const syncing = ref(false)
const boundScraping = ref<ScrapingSearchItem | null>(null)
const sourceLoading = ref(false)
const sourceUnavailable = ref(false)
const editingNovel = ref<NovelResponse | null>(null)
const readerRef = ref<{ confirmDiscard: () => Promise<boolean>, refresh: () => void } | null>(null)

const novelId = computed(() => String(route.params.id || ''))
const selectedId = computed(() => {
  const value = route.query.chapter
  return typeof value === 'string' && value ? value : null
})
const selectedIndex = computed(() => novel.value?.chapters.findIndex(item => item.id === selectedId.value) ?? -1)
const selectedChapter = computed(() => selectedIndex.value >= 0 ? novel.value?.chapters[selectedIndex.value] || null : null)
const bindingUnavailable = computed(() => Boolean(
  novel.value?.binding && sourceUnavailable.value
))
const mobileReaderOpen = computed({
  get: () => Boolean(isMobile.value && selectedChapter.value),
  set: (value: boolean) => {
    if (!value) void closeReader()
  }
})
const editOpen = computed({
  get: () => Boolean(editingNovel.value),
  set: (value: boolean) => {
    if (!value) editingNovel.value = null
  }
})

onMounted(() => void loadNovel())
watch(novelId, () => void loadNovel())
watch(isMobile, (mobile) => {
  if (!mobile && novel.value && !selectedChapter.value) void selectDefaultChapter()
})
onBeforeRouteLeave(async () => {
  return readerRef.value ? await readerRef.value.confirmDiscard() : true
})

useHead(() => ({
  title: novel.value?.title ? `Library > Novel > ${novel.value.title}` : 'Novel'
}))

async function loadNovel() {
  if (!novelId.value || !useRuntimeConfig().public.servUrl) {
    loading.value = false
    return
  }
  loading.value = true
  error.value = false
  try {
    novel.value = await useNovelWorkspaceApi().getNovel(novelId.value)
    await loadBoundScraping()
    if (!isMobile.value || selectedId.value) await selectDefaultChapter()
  } catch {
    error.value = true
  } finally {
    loading.value = false
  }
}

async function loadBoundScraping() {
  const scrapingId = novel.value?.binding?.scrapingId
  boundScraping.value = null
  sourceUnavailable.value = false
  if (!scrapingId) return

  sourceLoading.value = true
  try {
    boundScraping.value = await useNovelWorkspaceApi().getScraping(scrapingId)
  } catch {
    sourceUnavailable.value = true
  } finally {
    sourceLoading.value = false
  }
}

async function selectDefaultChapter() {
  if (!novel.value?.chapters.length) return
  if (selectedChapter.value) return
  const first = novel.value.chapters.find(chapter => chapter.contentAvailable) || novel.value.chapters[0]
  if (first) await replaceChapter(first.id)
}

function queryWithChapter(id?: string) {
  const query = { ...route.query }
  if (id) query.chapter = id
  else delete query.chapter
  return query
}

async function replaceChapter(id?: string) {
  await router.replace({ query: queryWithChapter(id) })
}

async function selectChapter(chapter: NovelChapterSummary) {
  if (chapter.id === selectedId.value) return
  if (readerRef.value && !await readerRef.value.confirmDiscard()) return
  await replaceChapter(chapter.id)
}

async function navigateChapter(offset: number) {
  if (!novel.value || selectedIndex.value < 0) return
  const chapter = novel.value.chapters[selectedIndex.value + offset]
  if (chapter) await selectChapter(chapter)
}

async function closeReader() {
  if (readerRef.value && !await readerRef.value.confirmDiscard()) return
  await replaceChapter()
}

async function applyMutation(result: NovelMutationResult, action: 'bind' | 'sync') {
  novel.value = result.novel
  await loadBoundScraping()
  const changes = result.changes
  const details = [
    changes.added ? `${changes.added} added` : '',
    changes.refreshed ? `${changes.refreshed} refreshed` : '',
    changes.preserved ? `${changes.preserved} edits preserved` : '',
    changes.removed ? `${changes.removed} marked removed` : ''
  ].filter(Boolean).join(', ')
  toast.add({
    title: action === 'bind' ? 'Scraping bound' : 'Novel synced',
    description: details || 'The novel is already up to date.',
    color: 'success',
    icon: action === 'bind' ? 'lucide:link' : 'lucide:refresh-cw'
  })
}

async function bindScraping(scrapingId: string) {
  binding.value = true
  try {
    await applyMutation(await useNovelWorkspaceApi().bind(novelId.value, scrapingId), 'bind')
    bindOpen.value = false
    if (!isMobile.value) await selectDefaultChapter()
  } catch (cause) {
    const status = (cause as { status?: number })?.status
    toast.add({
      title: 'Unable to bind scraping',
      description: status === 409
        ? 'This novel is already bound or already contains chapters.'
        : 'The scraping could not be copied. Please try again.',
      color: 'error',
      icon: 'lucide:circle-alert'
    })
  } finally {
    binding.value = false
  }
}

async function syncNovel() {
  syncing.value = true
  try {
    await applyMutation(await useNovelWorkspaceApi().sync(novelId.value), 'sync')
    await nextTick()
    readerRef.value?.refresh()
  } catch (cause) {
    const status = (cause as { status?: number })?.status
    if (status === 404) sourceUnavailable.value = true
    toast.add({
      title: status === 404 ? 'Scraping source unavailable' : 'Unable to sync novel',
      description: status === 404
        ? 'The bound scraping can no longer be found. Novel chapters remain available.'
        : 'No changes were applied. Please try again.',
      color: 'error',
      icon: 'lucide:circle-alert'
    })
  } finally {
    syncing.value = false
  }
}

function onChapterSaved(updated: NovelChapterContent) {
  if (!novel.value) return
  const chapter = novel.value.chapters.find(item => item.id === updated.id)
  if (!chapter) return
  chapter.manuallyEdited = true
  chapter.sourceUpdated = false
  chapter.contentAvailable = true
  chapter.etag = updated.etag
  chapter.updatedAt = updated.updatedAt
}

function openNovelEditor() {
  if (novel.value) editingNovel.value = novel.value as unknown as NovelResponse
}

async function onNovelUpdated() {
  editingNovel.value = null
  await loadNovel()
}
</script>

<template>
  <UDashboardPanel
    id="novel-outline"
    :default-size="40"
    :min-size="30"
    :max-size="55"
    resizable
  >
    <UDashboardNavbar :title="novel?.title || 'Novel'">
      <template #leading>
        <UDashboardSidebarCollapse />
      </template>
      <template #right>
        <UButton
          label="Library"
          icon="lucide:arrow-left"
          to="/library/novels"
          color="neutral"
          variant="ghost"
          size="sm"
        />
      </template>
    </UDashboardNavbar>

    <div v-if="loading" class="min-h-0 flex-1 space-y-5 overflow-hidden p-5" aria-label="Loading novel">
      <USkeleton class="h-36 rounded-xl" />
      <USkeleton class="h-36 rounded-xl" />
      <USkeleton v-for="index in 5" :key="index" class="h-12 rounded-lg" />
    </div>

    <div v-else-if="error || !novel" class="flex min-h-0 flex-1 items-center justify-center p-5">
      <UAlert
        class="max-w-md"
        color="error"
        variant="subtle"
        icon="lucide:circle-alert"
        title="Unable to load novel"
        description="Please return to the library or try again."
        :actions="[{ label: 'Retry', color: 'error', variant: 'soft', onClick: loadNovel }]"
      />
    </div>

    <template v-else>
      <UAlert
        v-if="bindingUnavailable"
        class="m-4 mb-0"
        color="warning"
        variant="subtle"
        icon="lucide:unlink"
        title="Scraping source unavailable"
        description="The saved binding and novel chapters are still available."
      />
      <LibraryNovelOutline
        :novel="novel"
        :selected-id="selectedId"
        :syncing="syncing"
        :scraping="boundScraping"
        :source-loading="sourceLoading"
        :source-unavailable="bindingUnavailable"
        @select="selectChapter"
        @edit="openNovelEditor"
        @bind="bindOpen = true"
        @sync="syncNovel"
      />
    </template>
  </UDashboardPanel>

  <LibraryNovelReader
    v-if="novel && !isMobile"
    ref="readerRef"
    :novel-id="novelId"
    :chapter="selectedChapter"
    :position="selectedIndex + 1"
    :total="novel.chapters.length"
    :can-previous="selectedIndex > 0"
    :can-next="selectedIndex >= 0 && selectedIndex < novel.chapters.length - 1"
    @navigate="navigateChapter"
    @saved="onChapterSaved"
  />

  <div v-else-if="!isMobile" class="hidden flex-1 items-center justify-center p-8 lg:flex">
    <UEmpty
      icon="lucide:book-open"
      title="Novel reader"
      description="The selected chapter will appear here."
      size="xl"
    />
  </div>

  <ClientOnly>
    <USlideover
      v-if="isMobile"
      v-model:open="mobileReaderOpen"
      :close="false"
      :ui="{ content: 'w-full max-w-none' }"
    >
      <template #content>
        <LibraryNovelReader
          v-if="novel && selectedChapter"
          ref="readerRef"
          mobile
          :novel-id="novelId"
          :chapter="selectedChapter"
          :position="selectedIndex + 1"
          :total="novel.chapters.length"
          :can-previous="selectedIndex > 0"
          :can-next="selectedIndex < novel.chapters.length - 1"
          @close="closeReader"
          @navigate="navigateChapter"
          @saved="onChapterSaved"
        />
      </template>
    </USlideover>
  </ClientOnly>

  <LibraryNovelBindingModal
    v-model:open="bindOpen"
    :binding="binding"
    @bind="bindScraping"
  />

  <LibraryUpdateNovelModal
    v-if="editingNovel"
    v-model:open="editOpen"
    :novel="editingNovel"
    @updated="onNovelUpdated"
  />
</template>
