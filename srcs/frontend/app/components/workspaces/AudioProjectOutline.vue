<script setup lang="ts">
import type { AudioWorkspace, AudioWorkspaceChapter } from '~/types/audio-workspace'
import { resolveLanguage } from '~/constants/supported-languages'

const props = defineProps<{
  workspace: AudioWorkspace
  selectedId: string | null
}>()
const emit = defineEmits<{
  select: [chapter: AudioWorkspaceChapter]
  edit: []
}>()
const search = ref('')
const failedCover = ref(false)
const language = computed(() => resolveLanguage(props.workspace.language))
const filteredChapters = computed(() => {
  const query = search.value.trim().toLowerCase()
  if (!query) return props.workspace.chapters
  return props.workspace.chapters.filter(chapter =>
    chapter.title.toLowerCase().includes(query)
    || String(chapter.chapterNumber || '').includes(query)
  )
})

const tasksByManifestIndex = computed(() => new Map(
  props.workspace.tasks.map(task => [task.manifestIndex, task])
))

const chapterSubtitle = (chapter: AudioWorkspaceChapter) => {
  if (!chapter.contentAvailable) {
    return props.workspace.sourceType === 'translation'
      ? 'Translation unavailable'
      : 'Content unavailable'
  }

  const task = tasksByManifestIndex.value.get(chapter.manifestIndex)
  if (!task) return null

  if (task.status === 'failed') {
    return task.lastError ? `Audio generation failed: ${task.lastError}` : 'Audio generation failed'
  }
  if (task.status === 'completed') {
    return task.resultAvailable ? 'Audio ready' : 'Audio generation completed without a result'
  }
  if (task.status === 'running') return 'Generating audio'
  if (task.status === 'queued') return 'Audio queued'
  return 'Audio generation pending'
}
</script>

<template>
  <div class="flex min-h-0 flex-1 flex-col overflow-hidden">
    <div class="flex min-h-0 flex-1 flex-col gap-5 overflow-y-auto p-4 sm:p-5">
      <section aria-labelledby="audio-project-heading">
        <div class="mb-3 flex items-center justify-between gap-2">
          <h2 id="audio-project-heading" class="font-semibold text-highlighted">
            Audio project
          </h2>
          <UButton
            label="Edit title"
            icon="lucide:pencil"
            size="sm"
            color="neutral"
            variant="ghost"
            @click="emit('edit')"
          />
        </div>
        <div class="rounded-lg border border-default bg-elevated/30 p-3">
          <p class="font-medium text-highlighted">
            {{ workspace.title }}
          </p>
          <div class="mt-2 flex flex-wrap gap-2">
            <UBadge
              :label="workspace.sourceType === 'original' ? 'Original' : 'Translated'"
              :icon="workspace.sourceType === 'original' ? 'lucide:book-open' : 'lucide:languages'"
              variant="subtle"
            />
            <UBadge
              :label="workspace.language === 'original' ? 'Unspecified language' : language.label"
              icon="lucide:globe-2"
              color="neutral"
              variant="subtle"
            />
            <UBadge
              v-if="!workspace.sourceAvailable"
              label="Unavailable"
              icon="lucide:circle-alert"
              color="warning"
              variant="subtle"
            />
          </div>
          <div class="space-y-1.5 pt-2">
            <div class="flex justify-between gap-3 text-xs text-muted">
              <span>Audio progress</span>
              <span class="tabular-nums">
                {{ workspace.progress.completed }} / {{ workspace.progress.total }} chapters
              </span>
            </div>
            <UProgress
              :model-value="workspace.progress.completed"
              :max="Math.max(workspace.progress.total, 1)"
              size="xs"
            />
            <div class="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted">
              <span class="inline-flex items-center gap-1.5">
                <UIcon name="lucide:clock-3" class="size-3.5" />
                <span class="tabular-nums">{{ workspace.progress.queued }}</span>
                queued
              </span>
              <span class="inline-flex items-center gap-1.5">
                <UIcon
                  name="lucide:loader-circle"
                  class="size-3.5"
                  :class="workspace.progress.running ? 'animate-spin' : undefined"
                />
                <span class="tabular-nums">{{ workspace.progress.running }}</span>
                running
              </span>
            </div>
          </div>
        </div>
      </section>

      <USeparator />

      <section v-if="workspace.novel" aria-labelledby="library-info-heading">
        <div class="mb-3 flex items-center justify-between gap-2">
          <h2 id="library-info-heading" class="font-semibold text-highlighted">
            Library information
          </h2>
          <UButton
            label="Open"
            icon="lucide:external-link"
            size="sm"
            color="neutral"
            variant="ghost"
            :to="`/library/novels/${workspace.novel.id}`"
          />
        </div>
        <div class="flex gap-4">
          <div class="flex w-18 h-full shrink-0 items-center justify-center overflow-hidden rounded-lg bg-primary/10">
            <img
              v-if="workspace.novel.coverImageUrl && !failedCover"
              :src="workspace.novel.coverImageUrl"
              :alt="`${workspace.novel.title} cover`"
              class="size-full object-cover"
              @error="failedCover = true"
            >
            <UIcon v-else name="lucide:book-open" class="size-7 text-primary/70" />
          </div>
          <div class="min-w-0 flex-1 space-y-2">
            <h1 class="text-lg font-semibold text-highlighted">
              {{ workspace.novel.title }}
            </h1>
            <div v-if="workspace.novel.tags.length" class="flex flex-wrap gap-1.5">
              <UBadge
                v-for="tag in workspace.novel.tags"
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
                  {{ workspace.novel.author || 'Unknown' }}
                </dd>
              </div>
              <div>
                <dt class="text-xs text-muted">
                  Original language
                </dt>
                <dd class="truncate text-toned">
                  {{ workspace.novel.language
                    ? resolveLanguage(workspace.novel.language).label
                    : 'Unspecified' }}
                </dd>
              </div>
              <div>
                <dt class="text-xs text-muted">
                  Status
                </dt>
                <dd class="capitalize text-toned">
                  {{ workspace.novel.status }}
                </dd>
              </div>
              <div>
                <dt class="text-xs text-muted">
                  Chapters
                </dt>
                <dd class="text-toned">
                  {{ workspace.novel.chapterCount }}
                </dd>
              </div>
            </dl>
          </div>
        </div>
      </section>

      <UAlert
        v-else
        color="warning"
        variant="subtle"
        icon="lucide:book-x"
        title="Novel unavailable"
        description="The Library novel referenced by this workspace could not be found."
      />

      <USeparator />

      <section aria-labelledby="audio-chapters-heading" class="flex min-h-0 flex-1 flex-col">
        <div class="mb-3 flex items-end justify-between gap-2">
          <div>
            <h2 id="audio-chapters-heading" class="font-semibold text-highlighted">
              Chapters
            </h2>
            <p class="text-xs text-muted">
              {{ filteredChapters.length }} of {{ workspace.chapters.length }}
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
              <span v-if="chapterSubtitle(chapter)" aria-label="chapter-subtitle" class="block truncate text-xs text-muted">
                {{ chapterSubtitle(chapter) }}
              </span>
            </span>
            <span class="flex shrink-0 gap-1">
              <UTooltip v-if="chapter.sourceUpdated" text="Source content changed">
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
          :title="search ? 'No chapters found' : 'No chapters available'"
          :description="search ? 'Try a different search term.' : 'The selected source has no chapters yet.'"
          variant="subtle"
          size="sm"
        />
      </section>
    </div>
  </div>
</template>
