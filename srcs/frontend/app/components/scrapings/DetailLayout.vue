<script setup lang="ts">
import {
  ApiException,
  type ScrapingDetailResponse
} from '~~/shared/api-services/srv-core.client'
import {
  scrapingActivityMeta,
  sourceHost
} from '~/utils/scrapings'

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
const selectedDetailTab = ref('overview')
const activityMeta = computed(() => detail.value
  ? scrapingActivityMeta(detail.value.progress)
  : null)

const sourceLabel = computed(() => props.crawlerName || sourceHost(detail.value?.sourceUrl))

watch(
  () => props.scrapingId,
  () => {
    detail.value = null
    error.value = false
    selectedDetailTab.value = 'overview'
    void loadDetail()
  }
)

onMounted(() => void loadDetail())

defineExpose({
  refresh: () => loadDetail(true)
})

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
    error.value = false
    emit('updated', response)
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

    <div
      v-else-if="detail"
      class="flex min-h-0 w-full flex-1 flex-col overflow-hidden p-4 sm:p-6"
    >
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
      </section>

      <ScrapingsOverviewSection
        v-show="selectedDetailTab === 'overview'"
        :scraping-id="props.scrapingId"
        :detail="detail"
        :source-label="sourceLabel"
        role="tabpanel"
        aria-label="Overview"
        @updated="detail = $event; emit('updated', $event)"
      />

      <ScrapingsChapterList
        v-if="selectedDetailTab === 'chapters'"
        :scraping-id="props.scrapingId"
        :tasks="detail.tasks"
        :progress="detail.progress"
        @refresh="loadDetail(true)"
      />
    </div>
  </UDashboardPanel>
</template>
