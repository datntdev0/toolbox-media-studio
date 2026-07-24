<script setup lang="ts">
import type { ScrapingSummaryResponse } from '~~/shared/api-services/srv-core.client'
import {
  formatExactTime,
  formatRelativeTime,
  isActiveScraping,
  scrapingActivityMeta,
  sourceHost
} from '~/utils/scrapings'

const props = defineProps<{
  scrapings: ScrapingSummaryResponse[]
  selectedId: string | null
  crawlerNames: Record<string, string>
  loading: boolean
  loadingMore: boolean
  error: boolean
  canLoadMore: boolean
  deletingId: string | null
}>()

const emit = defineEmits<{
  select: [id: string]
  delete: [scraping: ScrapingSummaryResponse]
  create: []
  retry: []
  loadMore: []
}>()

const rowRefs = ref<Record<string, HTMLElement | null>>({})
const failedCovers = reactive(new Set<string>())

function setRowRef(id: string, element: unknown) {
  rowRefs.value[id] = element instanceof HTMLElement ? element : null
}

function select(id: string, focus = false) {
  emit('select', id)
  if (focus) {
    void nextTick(() => rowRefs.value[id]?.focus())
  }
}

function moveSelection(offset: number) {
  if (!props.scrapings.length) return
  const current = props.scrapings.findIndex(item => item.id === props.selectedId)
  const fallback = offset > 0 ? 0 : props.scrapings.length - 1
  const nextIndex = current === -1
    ? fallback
    : Math.min(Math.max(current + offset, 0), props.scrapings.length - 1)
  const next = props.scrapings[nextIndex]
  if (next) select(next.id, true)
}

function sourceLabel(scraping: ScrapingSummaryResponse) {
  return props.crawlerNames[scraping.crawlerId] || sourceHost(scraping.sourceUrl)
}

function activityMeta(scraping: ScrapingSummaryResponse) {
  return scrapingActivityMeta(scraping.progress)
}

function focusSelected() {
  if (props.selectedId) rowRefs.value[props.selectedId]?.focus()
}

function focusRow(id: string) {
  rowRefs.value[id]?.focus()
}

watch(
  () => props.selectedId,
  (id) => {
    if (!id) return
    void nextTick(() => rowRefs.value[id]?.scrollIntoView({ block: 'nearest' }))
  }
)

defineExpose({ focusSelected, focusRow })
</script>

<template>
  <UDashboardPanel
    id="scrapings-list"
    :default-size="25"
    :min-size="20"
    :max-size="30"
    resizable
  >
    <UDashboardNavbar title="Scrapings">
      <template #leading>
        <UDashboardSidebarCollapse />
      </template>

      <template #trailing>
        <UBadge
          v-if="scrapings.length"
          :label="String(scrapings.length)"
          color="neutral"
          variant="subtle"
        />
      </template>

      <template #right>
        <UButton
          label="New Scraping"
          icon="lucide:plus"
          size="sm"
          @click="emit('create')"
        />
      </template>
    </UDashboardNavbar>

    <div class="flex min-h-0 flex-1 flex-col">
      <UAlert
        v-if="error"
        class="m-3 shrink-0"
        color="error"
        variant="subtle"
        icon="lucide:circle-alert"
        title="Unable to load scrapings"
        description="Your scrapings could not be refreshed. Please try again."
        :actions="[{
          label: 'Retry',
          color: 'error',
          variant: 'soft',
          onClick: () => emit('retry')
        }]"
      />

      <div
        v-if="loading && !scrapings.length"
        class="flex-1 divide-y divide-default overflow-hidden"
        aria-label="Loading scrapings"
      >
        <div
          v-for="index in 6"
          :key="index"
          class="flex gap-3 p-4 sm:px-5"
        >
          <USkeleton class="h-14 w-10 shrink-0 rounded" />
          <div class="min-w-0 flex-1 space-y-2">
            <USkeleton class="h-4 w-4/5" />
            <USkeleton class="h-3 w-2/5" />
            <USkeleton class="h-3 w-3/5" />
          </div>
        </div>
      </div>

      <div
        v-else-if="!scrapings.length && !error"
        class="flex flex-1 items-center justify-center p-6"
      >
        <UEmpty
          icon="lucide:download"
          title="No scrapings yet"
          description="Create a reusable chapter manifest, then start the ranges you need."
          :actions="[{
            label: 'New Scraping',
            icon: 'lucide:plus',
            onClick: () => emit('create')
          }]"
        />
      </div>

      <div
        v-else
        role="listbox"
        aria-label="Recent scrapings"
        class="min-h-0 flex-1 divide-y divide-default overflow-y-auto"
      >
        <div
          v-for="scraping in scrapings"
          :key="scraping.id"
          class="group relative w-full border-l-2 transition-colors"
          :class="selectedId === scraping.id
            ? 'border-primary bg-primary/10'
            : 'border-transparent hover:border-primary hover:bg-primary/5'"
        >
          <button
            :ref="element => setRowRef(scraping.id, element)"
            type="button"
            role="option"
            :aria-selected="selectedId === scraping.id"
            :aria-label="`${scraping.title}, ${activityMeta(scraping).label}, ${scraping.progress.completed} of ${scraping.progress.total} chapters`"
            class="flex w-full cursor-pointer gap-3 p-4 pe-12 text-left focus-visible:z-10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-primary sm:ps-5"
            @click="select(scraping.id)"
            @keydown.down.prevent="moveSelection(1)"
            @keydown.up.prevent="moveSelection(-1)"
          >
            <div class="flex h-14 w-10 shrink-0 items-center justify-center overflow-hidden rounded bg-primary/10">
              <img
                v-if="scraping.coverImageUrl && !failedCovers.has(scraping.id)"
                :src="String(scraping.coverImageUrl)"
                :alt="`${scraping.title} cover`"
                class="size-full object-cover"
                @error="failedCovers.add(scraping.id)"
              >
              <UIcon
                v-else
                name="lucide:book-open"
                class="size-5 text-primary/70"
              />
            </div>

            <div class="min-w-0 flex-1">
              <p class="line-clamp-2 text-sm font-semibold text-highlighted">
                {{ scraping.title }}
              </p>
              <p class="mt-0.5 truncate text-xs text-muted">
                {{ sourceLabel(scraping) }}
              </p>

              <div class="mt-2 flex flex-wrap items-center gap-x-2 gap-y-1">
                <UBadge
                  :label="activityMeta(scraping).label"
                  :icon="activityMeta(scraping).icon"
                  :color="activityMeta(scraping).color"
                  variant="subtle"
                  size="sm"
                  :ui="{
                    leadingIcon: activityMeta(scraping).spinning
                      ? 'motion-safe:animate-spin'
                      : undefined
                  }"
                />
                <span class="text-xs text-toned">
                  {{ scraping.progress.completed }} of {{ scraping.progress.total }} chapters
                </span>
              </div>

              <UProgress
                v-if="isActiveScraping(scraping.progress)"
                :model-value="scraping.progress.completed"
                :max="Math.max(scraping.progress.total, 1)"
                size="xs"
                class="mt-2"
              />

              <UTooltip :text="formatExactTime(scraping.updatedAt)">
                <span class="mt-2 inline-block text-xs text-dimmed">
                  Updated {{ formatRelativeTime(scraping.updatedAt) }}
                </span>
              </UTooltip>
            </div>
          </button>

          <UTooltip text="Delete scraping">
            <UButton
              icon="lucide:trash-2"
              color="error"
              variant="ghost"
              size="xs"
              class="absolute end-3 top-3 opacity-70 transition-opacity group-hover:opacity-100 group-focus-within:opacity-100"
              :aria-label="`Delete ${scraping.title}`"
              :loading="deletingId === scraping.id"
              :disabled="Boolean(deletingId && deletingId !== scraping.id)"
              @click.stop="emit('delete', scraping)"
              @keydown.stop
            />
          </UTooltip>
        </div>

        <div v-if="canLoadMore" class="flex justify-center p-4">
          <UButton
            label="Load more"
            color="neutral"
            variant="soft"
            size="sm"
            :loading="loadingMore"
            @click="emit('loadMore')"
          />
        </div>
      </div>
    </div>
  </UDashboardPanel>
</template>
