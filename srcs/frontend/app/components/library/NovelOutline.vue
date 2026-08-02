<script setup lang="ts">
import type {
  NovelChapterSummary,
  NovelWorkspace,
  ScrapingSearchItem
} from '~/types/novel-workspace'

const props = defineProps<{
  novel: NovelWorkspace
  selectedId: string | null
  syncing: boolean
  scraping?: ScrapingSearchItem | null
  sourceLoading?: boolean
  sourceUnavailable?: boolean
}>()

const emit = defineEmits<{
  select: [chapter: NovelChapterSummary]
  edit: []
  bind: []
  sync: []
}>()

const search = ref('')
const failedCover = ref(false)

const filteredChapters = computed(() => {
  const query = search.value.trim().toLowerCase()
  if (!query) return props.novel.chapters
  return props.novel.chapters.filter(chapter =>
    chapter.title.toLowerCase().includes(query)
    || String(chapter.chapterNumber || '').includes(query)
  )
})

function readValue(value: unknown, fallback = '') {
  if (!value) return fallback
  if (typeof value === 'string') return value
  if (typeof value !== 'object') return String(value)
  const record = value as Record<string, unknown>
  return String(record.name ?? record.value ?? record.text ?? fallback)
}
</script>

<template>
  <div class="flex min-h-0 flex-1 flex-col overflow-hidden">
    <div class="flex min-h-0 flex-1 flex-col gap-5 overflow-y-auto p-4 sm:p-5">
      <section aria-labelledby="novel-info-heading">
        <div class="mb-3 flex items-center justify-between">
          <h2 id="novel-info-heading" class="font-semibold text-highlighted">
            Novel information
          </h2>
          <div class="flex gap-2">
            <UButton
              label="Edit"
              icon="lucide:pencil"
              size="sm"
              color="neutral"
              variant="ghost"
              @click="emit('edit')"
            />
            <UButton
              v-if="novel.binding"
              label="Sync"
              icon="lucide:refresh-cw"
              size="sm"
              color="neutral"
              variant="soft"
              :loading="syncing"
              :disabled="sourceLoading || sourceUnavailable"
              @click="emit('sync')"
            />
          </div>
        </div>
        <div class="flex gap-4">
          <div class="flex w-18 h-full shrink-0 items-center justify-center overflow-hidden rounded-lg bg-primary/10">
            <img
              v-if="readValue(novel.coverImageUrl) && !failedCover"
              :src="readValue(novel.coverImageUrl)"
              :alt="`${novel.title} cover`"
              class="size-full object-cover"
              @error="failedCover = true"
            >
            <UIcon v-else name="lucide:book-open" class="size-7 text-primary/70" />
          </div>
          <div class="min-w-0 flex-1 space-y-2">
            <h1 class="text-lg font-semibold text-highlighted">
              {{ novel.title }}
            </h1>
            <div v-if="novel.tags?.length" class="flex flex-wrap gap-1.5">
              <UBadge
                v-for="tag in novel.tags"
                :key="tag"
                :label="tag"
                color="neutral"
                variant="subtle"
                size="sm"
              />
            </div>
            <dl class="flex flex-row flex-wrap justify-between gap-x-3 gap-y-2 text-sm">
              <div>
                <dt class="text-xs text-muted">
                  Author
                </dt>
                <dd class="truncate text-toned">
                  {{ readValue(novel.author, 'Unknown') }}
                </dd>
              </div>
              <div>
                <dt class="text-xs text-muted">
                  Language
                </dt>
                <dd class="truncate text-toned">
                  {{ readValue(novel.language, 'Unknown') }}
                </dd>
              </div>
              <div>
                <dt class="text-xs text-muted">
                  Chapters
                </dt>
                <dd class="text-toned">
                  {{ novel.chapterCount }}
                </dd>
              </div>
            </dl>
          </div>
        </div>
        <p class="mt-3 line-clamp-4 text-sm/6 text-muted">
          {{ readValue(novel.description, 'No description available.') }}
        </p>
      </section>

      <section aria-labelledby="binding-heading">
        <div class="mb-3 flex items-center gap-2">
          <UButton
            v-if="novel.binding"
            :to="`/scrapings?id=${encodeURIComponent(novel.binding.scrapingId)}`"
            icon="lucide:external-link"
            color="neutral"
            variant="ghost"
            size="sm"
            aria-label="Open bound scraping"
          />
          <div>
            <h2 id="binding-heading" class="font-semibold text-highlighted">
              Scraping source
            </h2>
            <p class="text-xs text-muted">
              Binding is permanent for this novel.
            </p>
          </div>
        </div>

        <div v-if="novel.binding" class="flex flex-row gap-4 rounded-lg border border-default bg-elevated/30 p-3">
          <div class="flex items-center gap-3">
            <div class="flex size-11 shrink-0 items-center justify-center overflow-hidden rounded-md bg-primary/10">
              <img
                v-if="scraping?.coverImageUrl"
                :src="scraping.coverImageUrl"
                :alt="`${scraping.title} cover`"
                class="size-full object-cover"
              >
              <UIcon v-else name="lucide:link" class="size-5 text-primary/70" />
            </div>
            <div class="min-w-0 flex-1">
              <template v-if="scraping">
                <p class="truncate font-medium text-highlighted">
                  {{ scraping.title }}
                </p>
                <p class="truncate text-xs text-muted">
                  {{ scraping.crawlerId || scraping.sourceUrl }}
                </p>
              </template>
              <template v-else-if="sourceLoading">
                <USkeleton class="mb-1 h-4 w-32" />
                <USkeleton class="h-3 w-24" />
              </template>
              <template v-else>
                <p class="truncate font-medium text-highlighted">
                  Scraping unavailable
                </p>
                <p class="truncate text-xs text-muted">
                  {{ novel.binding.scrapingId }}
                </p>
              </template>
            </div>
            <UBadge
              v-if="sourceUnavailable"
              label="Unavailable"
              icon="lucide:unlink"
              color="warning"
              variant="subtle"
              size="sm"
            />
          </div>
          <div v-if="scraping" class="flex-1 mt-3 space-y-1.5">
            <div class="flex items-center justify-between gap-2 text-xs text-muted">
              <span>Downloaded chapters</span>
              <span>{{ scraping.progress.completed }} / {{ scraping.progress.total }}</span>
            </div>
            <UProgress
              :model-value="scraping.progress.completed"
              :max="Math.max(scraping.progress.total, 1)"
              size="xs"
            />
          </div>
        </div>

        <UEmpty
          v-else
          icon="lucide:link-2-off"
          title="No scraping bound"
          description="Bind a scraping to copy its chapter list and downloaded content."
          variant="subtle"
          size="sm"
          :actions="[{ label: 'Bind scraping', icon: 'lucide:link', onClick: () => emit('bind') }]"
        />
      </section>

      <USeparator />

      <section aria-labelledby="chapter-list-heading" class="flex min-h-0 flex-1 flex-col">
        <div class="mb-3 flex items-end justify-between gap-2">
          <div>
            <h2 id="chapter-list-heading" class="font-semibold text-highlighted">
              Chapters
            </h2>
            <p class="text-xs text-muted">
              {{ filteredChapters.length }} of {{ novel.chapters.length }}
            </p>
          </div>
          <UInput
            v-model="search"
            icon="lucide:search"
            placeholder="Find chapter"
            size="sm"
            class="w-40"
          />
        </div>

        <div
          v-if="filteredChapters.length"
          aria-label="chapter-list"
          class="min-h-0 flex-1 overflow-y-auto rounded-lg border border-default"
        >
          <button
            v-for="chapter in filteredChapters"
            :key="chapter.id"
            type="button"
            class="flex w-full items-center gap-3 border-b border-default px-3 py-2.5 text-left last:border-b-0 focus-visible:z-10 focus-visible:outline-2 focus-visible:outline-primary"
            :class="selectedId === chapter.id ? 'bg-primary/10' : 'hover:bg-elevated/50'"
            @click="emit('select', chapter)"
          >
            <span class="w-8 shrink-0 text-center text-xs tabular-nums text-muted">
              {{ chapter.chapterNumber ?? chapter.manifestIndex + 1 }}
            </span>
            <span class="min-w-0 flex-1">
              <span class="block truncate text-sm font-medium text-highlighted">{{ chapter.title }}</span>
              <span v-if="!chapter.contentAvailable" class="block text-xs text-muted">Content unavailable</span>
            </span>
            <span class="flex shrink-0 gap-1">
              <UTooltip v-if="chapter.manuallyEdited" text="Manually edited">
                <UIcon name="lucide:pencil-line" class="size-4 text-primary" />
              </UTooltip>
              <UTooltip v-if="chapter.sourceUpdated" text="Newer source content available">
                <UIcon name="lucide:refresh-cw-dot" class="size-4 text-warning" />
              </UTooltip>
              <UTooltip v-if="chapter.sourceRemoved" text="Removed from source">
                <UIcon name="lucide:unlink" class="size-4 text-error" />
              </UTooltip>
              <UIcon
                v-if="selectedId === chapter.id"
                name="lucide:chevron-right"
                class="size-4 text-primary"
              />
            </span>
          </button>
        </div>

        <UEmpty
          v-else
          icon="lucide:book-open"
          :title="search ? 'No chapters found' : 'No chapters yet'"
          :description="search ? 'Try a different search term.' : 'Bind a scraping to add chapters to this novel.'"
          variant="subtle"
          size="sm"
        />
      </section>
    </div>
  </div>
</template>
