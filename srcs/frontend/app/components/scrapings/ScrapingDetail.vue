<script setup lang="ts">
import type { AccordionItem } from '@nuxt/ui'
import {
  ApiException,
  ScrapingStartRequest,
  ScrapingTaskStatus,
  type ScrapingDetailResponse,
  type ScrapingResultResponse,
  type ScrapingTaskResponse
} from '~~/shared/api-services/srv-core.client'
import {
  formatExactTime,
  scrapingActivityMeta,
  scrapingTaskStatusMeta,
  sourceHost
} from '~/utils/scrapings'

type ChapterItem = AccordionItem & {
  task: ScrapingTaskResponse
}

const CHAPTER_HEADER_HEIGHT = 52
const CHAPTER_BODY_HEIGHT = 468
const CHAPTER_OVERSCAN = 6
const detailTabItems = [{
  label: 'Overview',
  value: 'overview',
  icon: 'lucide:layout-dashboard'
}, {
  label: 'Chapters',
  value: 'chapters',
  icon: 'lucide:list-tree'
}]

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
const pendingBackgroundRefresh = ref(false)
const failedCover = ref(false)
const openTaskId = ref<string>()
const chapterContainer = ref<HTMLElement | null>(null)
const chapterScrollTop = shallowRef(0)
const pendingChapterScrollTop = shallowRef(0)
let chapterScrollFrame: number | undefined
const resultLoading = reactive<Record<string, boolean>>({})
const resultErrors = reactive<Record<string, string>>({})
const starting = ref(false)
const stopping = ref(false)
const startError = ref('')
const rangeInitializedFor = ref('')
const selectedDetailTab = ref('overview')
const startState = reactive({
  chapterFrom: 1,
  chapterTo: 1,
  refetch: false,
  force: false
})
const toast = useToast()
const resultCache = useState<Record<string, ScrapingResultResponse>>(
  'scrapings:result-cache',
  () => ({})
)

const activityMeta = computed(() => detail.value
  ? scrapingActivityMeta(detail.value.progress)
  : null)

const sortedTasks = computed(() => [...(detail.value?.tasks || [])]
  .sort((a, b) => a.manifestIndex - b.manifestIndex))
const numberedTasks = computed(() => sortedTasks.value.filter(
  task => parsedChapterNumber(task) !== null
))
const hasUnnumberedTasks = computed(
  () => numberedTasks.value.length !== sortedTasks.value.length
)
const startValidationError = computed(() => {
  if (!Number.isInteger(startState.chapterFrom) || startState.chapterFrom < 1) {
    return 'Chapter from must be a positive whole number.'
  }
  if (!Number.isInteger(startState.chapterTo) || startState.chapterTo < 1) {
    return 'Chapter to must be a positive whole number.'
  }
  if (startState.chapterFrom > startState.chapterTo) {
    return 'Chapter from must be less than or equal to chapter to.'
  }
  return ''
})

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
    startError.value = ''
    rangeInitializedFor.value = ''
    selectedDetailTab.value = 'overview'
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

defineExpose({
  refresh: () => loadDetail(true)
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
  const chapterNumber = parsedChapterNumber(task)
  if (chapterNumber === null) return title
  const number = String(chapterNumber)
  return new RegExp(`\\b${number.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}\\b`).test(title)
    ? title
    : `Chapter ${number}: ${title}`
}

function parsedChapterNumber(task: ScrapingTaskResponse) {
  const value = task.chapterNumber as unknown
  if (typeof value === 'number' && Number.isInteger(value)) return value
  return null
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
  return task.status === ScrapingTaskStatus.Running
}

function errorStatus(cause: unknown) {
  return cause instanceof ApiException ? cause.status : undefined
}

async function loadDetail(background = false) {
  if (requestInFlight.value) {
    if (background) pendingBackgroundRefresh.value = true
    return
  }
  requestInFlight.value = true
  if (background) refreshing.value = true
  else loading.value = true

  try {
    const { scrapings } = useApiClient()
    const response = await scrapings.get_scraping(props.scrapingId)
    detail.value = response
    initializeChapterRange(response)
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
    if (pendingBackgroundRefresh.value) {
      pendingBackgroundRefresh.value = false
      void loadDetail(true)
    }
  }
}

function initializeChapterRange(response: ScrapingDetailResponse) {
  if (rangeInitializedFor.value === response.id) return
  const numbers = (response.tasks || [])
    .map(parsedChapterNumber)
    .filter((number): number is number => number !== null)
  if (numbers.length) {
    startState.chapterFrom = Math.min(...numbers)
    startState.chapterTo = Math.max(...numbers)
  }
  rangeInitializedFor.value = response.id
}

async function startTasks() {
  startError.value = startValidationError.value
  if (startError.value || !detail.value) return
  const expectedQueuedCount = (detail.value.tasks || []).filter((task) => {
    const chapterNumber = parsedChapterNumber(task)
    if (
      chapterNumber === null
      || chapterNumber < startState.chapterFrom
      || chapterNumber > startState.chapterTo
    ) {
      return false
    }
    return startState.force
      || ![ScrapingTaskStatus.Queued, ScrapingTaskStatus.Running].includes(task.status)
  }).length
  starting.value = true
  try {
    const { scrapings } = useApiClient()
    const response = await scrapings.start_scraping(
      props.scrapingId,
      new ScrapingStartRequest({
        chapterFrom: startState.chapterFrom,
        chapterTo: startState.chapterTo,
        refetch: startState.refetch,
        force: startState.force
      })
    )
    detail.value = response
    emit('updated', response)
    startError.value = ''
    toast.add({
      title: expectedQueuedCount > 0 ? 'Chapter tasks queued' : 'No new tasks queued',
      description: expectedQueuedCount > 0
        ? `Queued chapters ${startState.chapterFrom}–${startState.chapterTo}.`
        : 'The selected tasks are already queued or running.',
      icon: expectedQueuedCount > 0 ? 'lucide:play' : 'lucide:info',
      color: expectedQueuedCount > 0 ? 'success' : 'neutral'
    })
  } catch (cause) {
    const publicationFailed = errorStatus(cause) === 503
    startError.value = publicationFailed
      ? 'Some tasks could not be published. Enable force and start the range again.'
      : validationMessage(cause) || 'The selected chapter range could not be started.'
  } finally {
    starting.value = false
  }
}

async function stopQueuedTasks() {
  if (!detail.value?.progress.queued) return
  stopping.value = true
  startError.value = ''
  try {
    const { scrapings } = useApiClient()
    const response = await scrapings.stop_scraping(props.scrapingId)
    detail.value = response
    emit('updated', response)
    toast.add({
      title: 'Queued tasks stopped',
      description: 'Running chapters will continue; queued chapters are ready to start again.',
      icon: 'lucide:square',
      color: 'neutral'
    })
  } catch {
    startError.value = 'Queued tasks could not be stopped. Please try again.'
  } finally {
    stopping.value = false
  }
}

function validationMessage(cause: unknown) {
  if (!cause || typeof cause !== 'object') return ''
  const detail = (cause as { detail?: string | Array<{ msg?: string }> }).detail
  if (typeof detail === 'string') return detail
  return detail?.find(item => item.msg)?.msg || ''
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
          v-if="activityMeta"
          :label="activityMeta.label"
          :icon="activityMeta.icon"
          :color="activityMeta.color"
          variant="subtle"
          :ui="{
            leadingIcon: activityMeta.spinning
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
            <div class="flex flex-wrap gap-2 text-xs">
              <UBadge
                :label="`${detail.progress.created} ready`"
                color="neutral"
                variant="subtle"
              />
              <UBadge
                v-if="detail.progress.queued"
                :label="`${detail.progress.queued} queued`"
                color="neutral"
                variant="subtle"
              />
              <UBadge
                v-if="detail.progress.running"
                :label="`${detail.progress.running} running`"
                color="primary"
                variant="subtle"
              />
              <UBadge
                v-if="detail.progress.failed"
                :label="`${detail.progress.failed} failed`"
                color="error"
                variant="subtle"
              />
            </div>
          </div>
          <UProgress
            :model-value="detail.progress.completed"
            :max="Math.max(detail.progress.total, 1)"
            size="sm"
          />

          <UTabs
            v-model="selectedDetailTab"
            :items="detailTabItems"
            :content="false"
            class="w-full"
          />

          <div
            v-show="selectedDetailTab === 'overview'"
            class="space-y-7 pt-1"
            role="tabpanel"
            aria-label="Overview"
          >
            <UPageCard title="Start scraping chapter by range" variant="subtle">
              <div class="grid gap-4 sm:grid-cols-2 lg:grid-cols-[1fr_1fr_auto]">
                <UFormField label="Chapter from" name="chapterFrom" required>
                  <UInputNumber
                    v-model="startState.chapterFrom"
                    :min="1"
                    :step="1"
                    :disabled="starting || stopping || !numberedTasks.length"
                    class="w-full"
                  />
                </UFormField>
                <UFormField label="Chapter to" name="chapterTo" required>
                  <UInputNumber
                    v-model="startState.chapterTo"
                    :min="1"
                    :step="1"
                    :disabled="starting || stopping || !numberedTasks.length"
                    class="w-full"
                  />
                </UFormField>
                <div class="flex items-end gap-2">
                  <UButton
                    label="Start"
                    icon="lucide:play"
                    :loading="starting"
                    :disabled="stopping || !numberedTasks.length || Boolean(startValidationError)"
                    @click="startTasks"
                  />
                  <UButton
                    label="Stop queued"
                    icon="lucide:square"
                    color="neutral"
                    variant="soft"
                    :loading="stopping"
                    :disabled="starting || detail.progress.queued === 0"
                    @click="stopQueuedTasks"
                  />
                </div>
              </div>

              <div class="mt-4 grid gap-3 sm:grid-cols-2">
                <USwitch
                  v-model="startState.refetch"
                  label="Refetch chapter content"
                  description="Bypass saved results and crawler caches."
                  :disabled="starting || stopping"
                />
                <USwitch
                  v-model="startState.force"
                  label="Force active tasks"
                  description="Requeue queued or running tasks; concurrent workers may race."
                  :disabled="starting || stopping"
                />
              </div>

              <UAlert
                v-if="startError || startValidationError"
                class="mt-4"
                color="error"
                variant="subtle"
                icon="lucide:circle-alert"
                title="Unable to start this range"
                :description="startError || startValidationError"
              />
              <p v-else-if="hasUnnumberedTasks" class="mt-4 text-xs text-muted">
                Chapters without a parsed number remain visible in Chapters but cannot be selected by range.
              </p>
              <p v-else-if="!numberedTasks.length" class="mt-4 text-xs text-muted">
                This manifest has no numbered chapters to start.
              </p>
            </UPageCard>

            <UPageCard
              orientation="horizontal"
              reverse
              variant="naked"
              class="overflow-hidden rounded-xl border border-default bg-elevated/30"
              :ui="{
                container: 'flex flex-row items-start gap-4 p-4 sm:p-4 lg:flex lg:flex-row lg:items-start lg:gap-4',
                wrapper: 'min-w-0 p-0 sm:p-0 sm:py-0',
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
                  {{ String(detail.metadata.description || 'No description available.').trim() }}
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
          </div>

          <section
            v-show="selectedDetailTab === 'chapters'"
            class="pt-1"
            aria-labelledby="chapters-heading"
            role="tabpanel"
          >
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
                    <div class="min-w-0 flex-1 text-left">
                      <p class="truncate">
                        {{ item.label }}
                      </p>
                      <p v-if="item.task.lastError" class="truncate text-xs text-error">
                        {{ String(item.task.lastError) }}
                      </p>
                    </div>
                  </template>

                  <template #leading="{ item }">
                    <UIcon
                      :name="taskMeta(item.task).icon"
                      class="size-4 shrink-0"
                      :class="[
                        isSpinning(item.task) && 'motion-safe:animate-spin',
                        taskMeta(item.task).color === 'success' && 'text-success',
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
                      <UAlert
                        v-if="item.task.lastError"
                        class="mb-4"
                        color="error"
                        variant="subtle"
                        icon="lucide:circle-alert"
                        title="Latest fetch failed"
                        :description="String(item.task.lastError)"
                      />
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
        </section>
      </div>
    </div>
  </UDashboardPanel>
</template>
