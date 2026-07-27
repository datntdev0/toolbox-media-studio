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
const filterItems = [
  { label: 'All statuses', value: 'all' },
  { label: 'Not started', value: 'not_started' },
  { label: 'In progress', value: 'translating' },
  { label: 'Translated', value: 'translated' },
  { label: 'Manually edited', value: 'manually_edited' },
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

        <div class="space-y-2">
          <button
            v-for="chapter in filteredChapters"
            :key="chapter.id"
            type="button"
            class="flex w-full items-center gap-3 rounded-lg border px-3 py-3 text-left transition-colors focus-visible:outline-2 focus-visible:outline-primary"
            :class="selectedId === chapter.id
              ? 'border-primary bg-primary/10'
              : 'border-default hover:bg-elevated/60'"
            :aria-current="selectedId === chapter.id ? 'true' : undefined"
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
              </span>
            </span>
            <UIcon
              v-if="selectedId === chapter.id"
              name="lucide:chevron-right"
              class="size-4 shrink-0 text-primary"
            />
          </button>
        </div>

        <UEmpty
          v-if="!filteredChapters.length"
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
