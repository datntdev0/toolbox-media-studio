<script setup lang="ts">
import type {
  TranslationChapter,
  TranslationChapterStatus,
  TranslationWorkspace
} from '~/types/translation-workspace'
import { chapterStatusMeta } from '~/utils/translation-workspaces'

const props = defineProps<{
  workspace: TranslationWorkspace
  selectedId: string | null
}>()
const open = defineModel<boolean>('open', { default: false })
const emit = defineEmits<{ select: [chapter: TranslationChapter] }>()

const search = ref('')
const statusFilter = ref<'all' | TranslationChapterStatus>('all')
const chapterListRef = ref<HTMLElement | null>(null)
const scrollTop = ref(0)
const viewportHeight = ref(640)
const rowHeight = 80
const overscan = 3
const filterItems = [
  { label: 'All statuses', value: 'all' },
  { label: 'Not started', value: 'not_started' },
  { label: 'Queued', value: 'queued' },
  { label: 'In progress', value: 'translating' },
  { label: 'Translated', value: 'translated' },
  { label: 'Manually edited', value: 'manually_edited' },
  { label: 'Source unavailable', value: 'unavailable' },
  { label: 'Failed', value: 'failed' }
]

const filteredChapters = computed(() => {
  const query = search.value.trim().toLowerCase()
  return props.workspace.chapters.filter((chapter) => {
    const matchesSearch = !query
      || chapter.title.toLowerCase().includes(query)
      || String(chapter.number).includes(query)
    const matchesStatus = statusFilter.value === 'all'
      || chapter.status === statusFilter.value
    return matchesSearch && matchesStatus
  })
})

const visibleChapters = computed(() => {
  const start = Math.max(0, Math.floor(scrollTop.value / rowHeight) - overscan)
  const end = Math.min(
    filteredChapters.value.length,
    Math.ceil((scrollTop.value + viewportHeight.value) / rowHeight) + overscan
  )

  return filteredChapters.value.slice(start, end).map((chapter, index) => ({
    chapter,
    index: start + index
  }))
})

const virtualListHeight = computed(() => filteredChapters.value.length * rowHeight)

function updateViewport() {
  const list = chapterListRef.value
  if (!list) return
  scrollTop.value = list.scrollTop
  viewportHeight.value = list.clientHeight
}

watch(filteredChapters, async () => {
  scrollTop.value = 0
  await nextTick()
  if (chapterListRef.value) chapterListRef.value.scrollTop = 0
  updateViewport()
})

watch(open, async (isOpen) => {
  if (!isOpen) return
  await nextTick()
  updateViewport()
})
</script>

<template>
  <USlideover
    v-model:open="open"
    title="Chapters"
    :description="`${workspace.progress.translated} of ${workspace.progress.total} chapters translated`"
    :ui="{ content: 'w-full max-w-lg' }"
  >
    <template #body>
      <div class="flex h-full min-h-0 flex-col gap-4">
        <div class="grid gap-2 sm:grid-cols-[1fr_11rem]">
          <UInput
            v-model="search"
            icon="lucide:search"
            placeholder="Find chapter"
            aria-label="Search chapters"
          />
          <USelect
            v-model="statusFilter"
            :items="filterItems"
            value-key="value"
            label-key="label"
            aria-label="Filter chapter status"
          />
        </div>

        <div
          v-if="filteredChapters.length"
          ref="chapterListRef"
          class="min-h-0 flex-1 overflow-y-auto"
          aria-label="Chapter list"
          @scroll.passive="updateViewport"
        >
          <div class="relative" :style="{ height: `${virtualListHeight}px` }">
            <button
              v-for="{ chapter, index } in visibleChapters"
              :key="chapter.id"
              type="button"
              class="absolute flex h-[72px] w-full items-center gap-3 rounded-lg border px-3 py-3 text-left transition-colors focus-visible:outline-2 focus-visible:outline-primary"
              :class="selectedId === chapter.id
                ? 'border-primary bg-primary/10'
                : 'border-default hover:bg-elevated/60'"
              :style="{ transform: `translateY(${index * rowHeight}px)` }"
              :aria-current="selectedId === chapter.id ? 'true' : undefined"
              :aria-posinset="index + 1"
              :aria-setsize="filteredChapters.length"
              @click="emit('select', chapter)"
            >
              <span class="w-7 shrink-0 text-center text-xs tabular-nums text-muted">
                {{ chapter.number }}
              </span>
              <span class="min-w-0 flex-1">
                <span class="block truncate text-sm font-medium text-highlighted">
                  {{ chapter.title }}
                </span>
                <span class="mt-0.5 flex items-center gap-1 text-xs text-muted">
                  <UIcon
                    :name="chapterStatusMeta[chapter.status].icon"
                    class="size-3.5"
                    :class="chapter.status === 'translating' ? 'animate-spin' : ''"
                  />
                  {{ chapterStatusMeta[chapter.status].shortLabel }}
                  <span v-if="chapter.sourceUpdated" class="text-warning">
                    · Source updated
                  </span>
                </span>
              </span>
              <UIcon
                v-if="selectedId === chapter.id"
                name="lucide:chevron-right"
                class="size-4 shrink-0 text-primary"
              />
            </button>
          </div>
        </div>

        <UEmpty
          v-else
          icon="lucide:search-x"
          title="No chapters found"
          description="Try another search term or status."
          variant="subtle"
          size="sm"
        />
      </div>
    </template>
  </USlideover>
</template>
