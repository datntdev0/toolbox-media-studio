<script setup lang="ts">
import type { AccordionItem } from '@nuxt/ui'
import {
  ApiException,
  ScrapingStatus,
  ScrapingTaskStatus,
  type ScrapingDetailResponse,
  type ScrapingResultResponse,
  type ScrapingTaskResponse
} from '~~/shared/api-services/srv-core.client'
import {
  formatExactTime,
  scrapingStatusMeta,
  scrapingTaskStatusMeta,
  sourceHost
} from '~/utils/scrapings'

type ChapterItem = AccordionItem & {
  task: ScrapingTaskResponse
}

const CHAPTER_HEADER_HEIGHT = 52
const CHAPTER_BODY_HEIGHT = 468
const CHAPTER_OVERSCAN = 6

const props = defineProps<{
  scrapingId: string
  crawlerName?: string
}>()

const emit = defineEmits<{
  close: []
  inaccessible: []
  updated: [detail: ScrapingDetailResponse]
}>()

const detail = ref<ScrapingDetailResponse | null>(null)
const loading = ref(true)
const refreshing = ref(false)
const error = ref(false)
const requestInFlight = ref(false)
const failedCover = ref(false)
const openTaskId = ref<string>()
const chapterContainer = ref<HTMLElement | null>(null)
const chapterScrollTop = shallowRef(0)
const pendingChapterScrollTop = shallowRef(0)
let chapterScrollFrame: number | undefined
const resultLoading = reactive<Record<string, boolean>>({})
const resultErrors = reactive<Record<string, string>>({})
const resultCache = useState<Record<string, ScrapingResultResponse>>(
  'scrapings:result-cache',
  () => ({})
)

const statusMeta = computed(() => detail.value
  ? scrapingStatusMeta[detail.value.status]
  : scrapingStatusMeta[ScrapingStatus.Queued])

const sortedTasks = computed(() => [...(detail.value?.tasks || [])]
  .sort((a, b) => a.manifestIndex - b.manifestIndex))

const chapterItems = computed<ChapterItem[]>(() => sortedTasks.value.map(task => ({
  value: task.id,
  label: chapterLabel(task),
  disabled: !task.resultAvailable,
  task,
  ui: {
    trigger: 'h-[52px] border-b border-default py-0',
    body: 'h-[468px] overflow-y-auto pb-5 pt-2'
  }
})))

const { height: measuredChapterViewportHeight } = useElementSize(chapterContainer)
const expandedChapterIndex = computed(() => openTaskId.value
  ? chapterItems.value.findIndex(item => item.value === openTaskId.value)
  : -1)
const chapterViewportHeight = computed(() => {
  const expandedHeight = expandedChapterIndex.value >= 0 ? CHAPTER_BODY_HEIGHT : 0
  return `${Math.min(Math.max(
    chapterItems.value.length * CHAPTER_HEADER_HEIGHT + expandedHeight,
    CHAPTER_HEADER_HEIGHT
  ), 680)}px`
})
const chapterVirtualRange = computed(() => {
  const itemCount = chapterItems.value.length
  if (!itemCount) return { start: 0, end: 0 }

  const start = Math.max(
    0,
    chapterIndexAtOffset(chapterScrollTop.value) - CHAPTER_OVERSCAN
  )
  const viewportHeight = measuredChapterViewportHeight.value || 680
  const end = Math.min(
    itemCount,
    chapterIndexAtOffset(chapterScrollTop.value + viewportHeight) + CHAPTER_OVERSCAN + 1
  )
  return { start, end }
})
const visibleChapterItems = computed(() => chapterItems.value.slice(
  chapterVirtualRange.value.start,
  chapterVirtualRange.value.end
))
const chapterWrapperStyle = computed(() => {
  const start = chapterVirtualRange.value.start
  const expandedBeforeStart = expandedChapterIndex.value >= 0
    && expandedChapterIndex.value < start
  const marginTop = start * CHAPTER_HEADER_HEIGHT
    + (expandedBeforeStart ? CHAPTER_BODY_HEIGHT : 0)
  const totalHeight = chapterItems.value.length * CHAPTER_HEADER_HEIGHT
    + (expandedChapterIndex.value >= 0 ? CHAPTER_BODY_HEIGHT : 0)

  return {
    height: `${Math.max(totalHeight - marginTop, 0)}px`,
    marginTop: `${marginTop}px`,
    width: '100%'
  }
})

const sourceLabel = computed(() => props.crawlerName || sourceHost(detail.value?.sourceUrl))

watch(
  () => props.scrapingId,
  () => {
    detail.value = null
    error.value = false
    failedCover.value = false
    openTaskId.value = undefined
    chapterScrollTop.value = 0
    pendingChapterScrollTop.value = 0
    if (chapterContainer.value) chapterContainer.value.scrollTop = 0
    void loadDetail()
  }
)

watch(openTaskId, (taskId) => {
  if (taskId) void loadResult(taskId)
})

onMounted(() => void loadDetail())
onBeforeUnmount(() => {
  if (chapterScrollFrame !== undefined) cancelAnimationFrame(chapterScrollFrame)
})

function cacheKey(taskId: string) {
  return `${props.scrapingId}:${taskId}`
}

function chapterIndexAtOffset(offset: number) {
  const itemCount = chapterItems.value.length
  if (!itemCount) return 0

  const expandedIndex = expandedChapterIndex.value
  if (expandedIndex < 0) {
    return Math.min(Math.floor(Math.max(offset, 0) / CHAPTER_HEADER_HEIGHT), itemCount - 1)
  }

  const expandedTop = expandedIndex * CHAPTER_HEADER_HEIGHT
  const expandedBottom = expandedTop + CHAPTER_HEADER_HEIGHT + CHAPTER_BODY_HEIGHT
  if (offset < expandedTop) {
    return Math.min(Math.floor(Math.max(offset, 0) / CHAPTER_HEADER_HEIGHT), itemCount - 1)
  }
  if (offset < expandedBottom) return expandedIndex

  return Math.min(
    Math.floor((offset - CHAPTER_BODY_HEIGHT) / CHAPTER_HEADER_HEIGHT),
    itemCount - 1
  )
}

function onChapterScroll(event: Event) {
  pendingChapterScrollTop.value = (event.currentTarget as HTMLElement).scrollTop
  if (chapterScrollFrame !== undefined) return

  chapterScrollFrame = requestAnimationFrame(() => {
    chapterScrollTop.value = pendingChapterScrollTop.value
    chapterScrollFrame = undefined
  })
}

function chapterLabel(task: ScrapingTaskResponse) {
  const title = task.title || 'Untitled chapter'
  if (task.chapterNumber === undefined || task.chapterNumber === null) return title
  const number = String(task.chapterNumber)
  return new RegExp(`\\b${number.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}\\b`).test(title)
    ? title
    : `Chapter ${number}: ${title}`
}

function taskMeta(task: ScrapingTaskResponse) {
  if (task.status === ScrapingTaskStatus.Completed && !task.resultAvailable) {
    return {
      label: 'Unavailable',
      color: 'neutral' as const,
      icon: 'lucide:circle-dashed'
    }
  }
  return scrapingTaskStatusMeta[task.status]
}

function isSpinning(task: ScrapingTaskResponse) {
  return task.status === ScrapingTaskStatus.Processing
}

function errorStatus(cause: unknown) {
  return cause instanceof ApiException ? cause.status : undefined
}

async function loadDetail(background = false) {
  if (requestInFlight.value) return
  requestInFlight.value = true
  if (background) refreshing.value = true
  else loading.value = true

  try {
    const { scrapings } = useApiClient()
    const response = await scrapings.get_scraping(props.scrapingId)
    detail.value = response
    error.value = false
    emit('updated', response)

    if (
      openTaskId.value
      && !response.tasks?.find(task => task.id === openTaskId.value && task.resultAvailable)
    ) {
      openTaskId.value = undefined
    }
  } catch (cause) {
    if (errorStatus(cause) === 404) {
      emit('inaccessible')
    } else {
      error.value = true
    }
  } finally {
    loading.value = false
    refreshing.value = false
    requestInFlight.value = false
  }
}

async function loadResult(taskId: string) {
  const key = cacheKey(taskId)
  if (resultCache.value[key] || resultLoading[key]) return
  resultLoading[key] = true
  resultErrors[key] = ''

  try {
    const { scrapings } = useApiClient()
    resultCache.value[key] = await scrapings.get_scraping_result(props.scrapingId, taskId)
  } catch (cause) {
    if (errorStatus(cause) === 409) {
      openTaskId.value = undefined
      await loadDetail(true)
    } else {
      resultErrors[key] = 'This chapter could not be loaded.'
    }
  } finally {
    resultLoading[key] = false
  }
}

function resultFor(taskId: string) {
  return resultCache.value[cacheKey(taskId)]
}
</script>

<template>
  <UDashboardPanel id="scrapings-detail">
    <UDashboardNavbar :title="detail?.metadata.title || 'Scraping'" :toggle="false">
      <template #leading>
        <UTooltip text="Close scraping">
          <UButton
            icon="lucide:x"
            color="neutral"
            variant="ghost"
            class="-ms-1.5"
            aria-label="Close scraping detail"
            @click="emit('close')"
          />
        </UTooltip>
      </template>

      <template #right>
        <UBadge
          v-if="detail"
          :label="statusMeta.label"
          :icon="statusMeta.icon"
          :color="statusMeta.color"
          variant="subtle"
          :ui="{
            leadingIcon: detail.status === ScrapingStatus.Processing
              ? 'motion-safe:animate-spin'
              : undefined
          }"
        />

        <UTooltip text="Refresh scraping">
          <UButton
            icon="lucide:refresh-cw"
            color="neutral"
            variant="ghost"
            aria-label="Refresh scraping"
            :loading="refreshing"
            @click="loadDetail(true)"
          />
        </UTooltip>
      </template>
    </UDashboardNavbar>

    <div class="min-h-0 flex-1 overflow-y-auto p-4 sm:p-6">
      <div v-if="loading && !detail" class="space-y-6" aria-label="Loading scraping">
        <div class="space-y-3">
          <USkeleton class="h-4 w-56" />
          <USkeleton class="h-2 w-full" />
        </div>
        <USkeleton class="h-64 rounded-xl" />
        <div class="space-y-3">
          <USkeleton v-for="index in 6" :key="index" class="h-12 w-full" />
        </div>
      </div>

      <UAlert
        v-else-if="error && !detail"
        color="error"
        variant="subtle"
        icon="lucide:circle-alert"
        title="Unable to load scraping"
        description="This scraping could not be opened. Please try again."
        :actions="[{
          label: 'Retry',
          color: 'error',
          variant: 'soft',
          onClick: () => loadDetail()
        }]"
      />

      <div v-else-if="detail" class="mx-auto flex w-full max-w-5xl flex-col gap-7">
        <section aria-labelledby="scraping-progress-heading" class="space-y-3">
          <div class="flex flex-wrap items-center justify-between gap-2">
            <div>
              <h2 id="scraping-progress-heading" class="font-semibold text-highlighted">
                Scraping progress
              </h2>
              <p class="text-sm text-muted">
                {{ detail.progress.completed }} of {{ detail.progress.total }} chapters downloaded
              </p>
            </div>
            <span class="text-sm font-medium text-toned">
              {{ statusMeta.label }}
            </span>
          </div>
          <UProgress
            :model-value="detail.progress.completed"
            :max="Math.max(detail.progress.total, 1)"
            size="sm"
          />

          <UAlert
            v-if="detail.status === ScrapingStatus.Retrying"
            color="warning"
            variant="subtle"
            icon="lucide:rotate-ccw"
            title="Retrying automatically"
            description="The source was temporarily unavailable. Downloading will resume automatically."
          />
          <UAlert
            v-else-if="detail.status === ScrapingStatus.Failed"
            color="error"
            variant="subtle"
            icon="lucide:circle-x"
            title="Scraping failed"
            :description="String(detail.lastError || 'The scraping could not be completed.')"
          />
        </section>

        <UPageCard
          orientation="horizontal"
          reverse
          variant="naked"
          class="overflow-hidden rounded-xl border border-default bg-elevated/30"
          :ui="{
            container: 'flex flex-row items-center gap-4 p-4 sm:p-4 lg:flex lg:flex-row lg:items-center lg:gap-4',
            wrapper: 'min-w-0 p-5 sm:p-3 sm:py-0',
            title: 'line-clamp-2 text-2xl',
            description: 'line-clamp-5'
          }"
        >
          <div class="flex min-h-52 w-full shrink-0 items-center justify-center overflow-hidden bg-primary/10 sm:w-40">
            <img
              v-if="detail.metadata.coverImageUrl && !failedCover"
              :src="String(detail.metadata.coverImageUrl)"
              :alt="`${detail.metadata.title} cover`"
              class="h-64 w-full object-cover sm:h-full"
              @error="failedCover = true"
            >
            <UIcon v-else name="lucide:book-open" class="size-10 text-primary/70" />
          </div>

          <template #title>
            <div class="flex justify-between">
              <h1 class="text-2xl font-semibold text-highlighted">
                {{ detail.metadata.title }}
              </h1>
              <UButton
                :label="sourceLabel"
                icon="lucide:external-link"
                color="neutral"
                variant="link"
                class="h-auto p-0"
                :to="detail.sourceUrl"
                target="_blank"
                rel="noopener noreferrer"
                :aria-label="`${sourceLabel} source (opens in a new tab)`"
              />
            </div>
          </template>

          <template #description>
            <p class="text-sm/6 text-muted">
              {{ String(detail.metadata.description || 'No description available.') }}
            </p>
          </template>

          <template #footer>
            <div class="space-y-4 text-sm">
              <dl class="grid gap-x-6 gap-y-3 sm:grid-cols-3">
                <div>
                  <dt class="text-muted">
                    Author
                  </dt>
                  <dd class="font-medium text-highlighted">
                    {{ String(detail.metadata.author || 'Unknown author') }}
                  </dd>
                </div>
                <div>
                  <dt class="text-muted">
                    Category
                  </dt>
                  <dd class="font-medium text-highlighted">
                    {{ String(detail.metadata.category || 'Uncategorized') }}
                  </dd>
                </div>
                <div v-if="detail.metadata.protagonists?.length">
                  <p class="mb-2 text-muted">
                    Protagonists
                  </p>
                  <div class="flex flex-wrap gap-2">
                    <UBadge
                      v-for="protagonist in detail.metadata.protagonists"
                      :key="protagonist"
                      :label="protagonist"
                      color="neutral"
                      variant="subtle"
                    />
                  </div>
                </div>
              </dl>

              <dl class="grid gap-x-6 gap-y-3 sm:grid-cols-2">
                <div>
                  <dt class="text-muted">
                    Source updated
                  </dt>
                  <dd class="font-medium text-highlighted">
                    {{ String(detail.metadata.updatedDate || 'Unknown date') }}
                  </dd>
                </div>
                <div>
                  <dt class="text-muted">
                    Metadata fetched
                  </dt>
                  <dd class="font-medium text-highlighted">
                    {{ formatExactTime(detail.metadata.fetchedAt) }}
                  </dd>
                </div>
              </dl>
            </div>
          </template>
        </UPageCard>

        <section aria-labelledby="chapters-heading">
          <div class="mb-3 flex flex-wrap items-end justify-between gap-2">
            <div>
              <h2 id="chapters-heading" class="text-lg font-semibold text-highlighted">
                Chapters
              </h2>
              <p class="text-sm text-muted">
                {{ detail.progress.completed }} downloaded of {{ detail.progress.total }}
              </p>
            </div>
          </div>
          <UProgress
            :model-value="detail.progress.completed"
            :max="Math.max(detail.progress.total, 1)"
            size="xs"
            class="mb-4"
          />

          <div
            v-if="chapterItems.length"
            ref="chapterContainer"
            class="touch-pan-y overflow-y-auto overscroll-contain rounded-lg border border-default [contain:strict] [overflow-anchor:none]"
            :style="{ height: chapterViewportHeight }"
            @scroll.passive="onChapterScroll"
          >
            <div
              class="[overflow-anchor:none]"
              :style="chapterWrapperStyle"
            >
              <UAccordion
                v-model="openTaskId"
                :items="visibleChapterItems"
                type="single"
                collapsible
                :unmount-on-hide="false"
                class="px-4"
              >
                <template #default="{ item }">
                  <span class="min-w-0 flex-1 truncate text-left">
                    {{ item.label }}
                  </span>
                </template>

                <template #leading="{ item }">
                  <UIcon
                    :name="taskMeta(item.task).icon"
                    class="size-4 shrink-0"
                    :class="[
                      isSpinning(item.task) && 'motion-safe:animate-spin',
                      taskMeta(item.task).color === 'success' && 'text-success',
                      taskMeta(item.task).color === 'warning' && 'text-warning',
                      taskMeta(item.task).color === 'error' && 'text-error',
                      taskMeta(item.task).color === 'primary' && 'text-primary',
                      taskMeta(item.task).color === 'neutral' && 'text-muted'
                    ]"
                  />
                </template>

                <template #trailing="{ item, open }">
                  <div class="ms-auto flex shrink-0 items-center gap-2">
                    <UBadge
                      :label="taskMeta(item.task).label"
                      :color="taskMeta(item.task).color"
                      variant="subtle"
                      size="sm"
                    />
                    <UIcon
                      v-if="item.task.resultAvailable"
                      name="lucide:chevron-down"
                      class="ms-1 size-4 shrink-0 text-muted transition-transform"
                      :class="open && 'rotate-180'"
                    />
                  </div>
                </template>

                <template #body="{ item }">
                  <div :aria-label="`${item.label} content`">
                    <div
                      v-if="resultLoading[cacheKey(item.task.id)]"
                      class="space-y-3 py-2"
                      aria-label="Loading chapter content"
                    >
                      <USkeleton
                        v-for="index in 5"
                        :key="index"
                        class="h-4"
                        :class="index % 2 === 0 ? 'w-11/12' : 'w-full'"
                      />
                    </div>

                    <UAlert
                      v-else-if="resultErrors[cacheKey(item.task.id)]"
                      color="error"
                      variant="subtle"
                      icon="lucide:circle-alert"
                      title="Unable to load chapter"
                      :description="resultErrors[cacheKey(item.task.id)]"
                      :actions="[{
                        label: 'Retry',
                        color: 'error',
                        variant: 'soft',
                        onClick: () => loadResult(item.task.id)
                      }]"
                    />

                    <article
                      v-else-if="resultFor(item.task.id)"
                      class="mx-auto max-w-3xl space-y-3 py-1 text-sm/6 text-toned"
                    >
                      <p
                        v-for="(paragraph, index) in resultFor(item.task.id)?.content || []"
                        :key="index"
                      >
                        {{ paragraph }}
                      </p>
                      <p v-if="!resultFor(item.task.id)?.content?.length" class="italic text-muted">
                        This chapter has no text content.
                      </p>
                    </article>
                  </div>
                </template>
              </UAccordion>
            </div>
          </div>

          <UEmpty
            v-else
            icon="lucide:book-open"
            title="No chapters"
            description="This scraping does not contain a chapter manifest."
            variant="subtle"
            size="sm"
          />
        </section>
      </div>
    </div>
  </UDashboardPanel>
</template>
