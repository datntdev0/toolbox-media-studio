<script setup lang="ts">
import type { ScrapingSearchItem } from '~/types/novel-workspace'

const open = defineModel<boolean>('open', { default: false })
const emit = defineEmits<{ bind: [scrapingId: string] }>()
const props = defineProps<{ binding: boolean }>()

const search = ref('')
const items = ref<ScrapingSearchItem[]>([])
const continuationToken = ref<string | null>(null)
const selectedId = ref<string | null>(null)
const loading = ref(false)
const loadingMore = ref(false)
const error = ref(false)
let searchTimer: ReturnType<typeof setTimeout> | undefined

watch(open, (value) => {
  if (value) {
    selectedId.value = null
    void load()
  }
})

watch(search, () => {
  if (!open.value) return
  if (searchTimer) clearTimeout(searchTimer)
  searchTimer = setTimeout(() => void load(), 300)
})

onBeforeUnmount(() => {
  if (searchTimer) clearTimeout(searchTimer)
})

async function load(more = false) {
  if (more) loadingMore.value = true
  else loading.value = true
  error.value = false
  try {
    const response = await useNovelWorkspaceApi().searchScrapings(
      search.value,
      20,
      more ? continuationToken.value : null
    )
    items.value = more ? [...items.value, ...(response.items || [])] : response.items || []
    continuationToken.value = response.continuationToken || null
  } catch {
    error.value = true
    if (!more) items.value = []
  } finally {
    loading.value = false
    loadingMore.value = false
  }
}

function choose(item: ScrapingSearchItem) {
  if (!props.binding) selectedId.value = item.id
}
</script>

<template>
  <UModal
    v-model:open="open"
    title="Bind a scraping"
    description="Choose the source whose current chapter manifest and downloaded content should be copied into this novel."
    :dismissible="!binding"
    :ui="{ content: 'sm:max-w-3xl' }"
  >
    <template #body>
      <div class="space-y-4">
        <UAlert
          color="neutral"
          variant="subtle"
          icon="lucide:copy"
          title="This creates an independent novel copy"
          description="Later source changes are only applied when you choose Sync. Manual chapter edits are preserved."
        />

        <UInput
          v-model="search"
          icon="lucide:search"
          placeholder="Search all scrapings..."
          autofocus
          class="w-full"
        />

        <div v-if="loading" class="space-y-2" aria-label="Loading scrapings">
          <USkeleton v-for="index in 5" :key="index" class="h-20 rounded-lg" />
        </div>

        <UAlert
          v-else-if="error"
          color="error"
          variant="subtle"
          icon="lucide:circle-alert"
          title="Unable to search scrapings"
          description="Please try again."
          :actions="[{ label: 'Retry', color: 'error', variant: 'soft', onClick: () => load() }]"
        />

        <div
          v-else-if="items.length"
          class="max-h-96 space-y-2 overflow-y-auto pr-1"
          role="listbox"
          aria-label="Scraping search results"
        >
          <button
            v-for="item in items"
            :key="item.id"
            type="button"
            class="flex w-full items-center gap-3 rounded-lg border p-3 text-left transition-colors focus-visible:outline-2 focus-visible:outline-primary"
            :class="selectedId === item.id ? 'border-primary bg-primary/5' : 'border-default hover:bg-elevated/60'"
            :aria-selected="selectedId === item.id"
            role="option"
            @click="choose(item)"
          >
            <div class="flex size-12 shrink-0 items-center justify-center overflow-hidden rounded-md bg-primary/10">
              <img
                v-if="item.coverImageUrl"
                :src="item.coverImageUrl"
                :alt="`${item.title} cover`"
                class="size-full object-cover"
              >
              <UIcon v-else name="lucide:book-open" class="size-5 text-primary/70" />
            </div>
            <div class="min-w-0 flex-1">
              <p class="truncate font-medium text-highlighted">
                {{ item.title }}
              </p>
              <p class="truncate text-xs text-muted">
                {{ item.sourceUrl }}
              </p>
              <p class="mt-1 text-xs text-toned">
                {{ item.progress?.completed || 0 }} of {{ item.progress?.total || 0 }} chapters downloaded
              </p>
            </div>
            <UIcon
              :name="selectedId === item.id ? 'lucide:circle-check' : 'lucide:circle'"
              class="size-5 shrink-0"
              :class="selectedId === item.id ? 'text-primary' : 'text-dimmed'"
            />
          </button>

          <div v-if="continuationToken" class="flex justify-center pt-2">
            <UButton
              label="Load more"
              color="neutral"
              variant="soft"
              :loading="loadingMore"
              @click="load(true)"
            />
          </div>
        </div>

        <UEmpty
          v-else
          icon="lucide:search-x"
          :title="search ? 'No scrapings found' : 'No scrapings available'"
          :description="search ? 'Try a different search term.' : 'Create a scraping before binding this novel.'"
          variant="subtle"
          size="sm"
        />
      </div>
    </template>

    <template #footer>
      <div class="flex w-full justify-end gap-2">
        <UButton
          label="Cancel"
          color="neutral"
          variant="subtle"
          :disabled="binding"
          @click="open = false"
        />
        <UButton
          label="Bind scraping"
          icon="lucide:link"
          :loading="binding"
          :disabled="!selectedId"
          @click="selectedId && emit('bind', selectedId)"
        />
      </div>
    </template>
  </UModal>
</template>
