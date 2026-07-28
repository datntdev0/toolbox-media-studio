<script setup lang="ts">
import type { TranslationWorkspace } from '~/types/translation-workspace'

const props = defineProps<{ workspace: TranslationWorkspace }>()
const rangeStart = defineModel<string>('rangeStart', { required: true })
const rangeEnd = defineModel<string>('rangeEnd', { required: true })

const emit = defineEmits<{
  configure: []
  start: []
  stop: []
}>()

const rangeStartChapterIndex = computed<number | undefined>({
  get: () => props.workspace.chapters.find(
    chapter => chapter.id === rangeStart.value
  )?.chapterIndex,
  set: (value) => {
    const chapter = props.workspace.chapters.find(item => item.chapterIndex === value)
    if (chapter) rangeStart.value = chapter.id
  }
})
const rangeEndChapterIndex = computed<number | undefined>({
  get: () => props.workspace.chapters.find(
    chapter => chapter.id === rangeEnd.value
  )?.chapterIndex,
  set: (value) => {
    const chapter = props.workspace.chapters.find(item => item.chapterIndex === value)
    if (chapter) rangeEnd.value = chapter.id
  }
})
const firstChapterIndex = computed(() => props.workspace.chapters[0]?.chapterIndex || 1)
const lastChapterIndex = computed(() =>
  props.workspace.chapters.at(-1)?.chapterIndex || 1
)

const startIndex = computed(() =>
  props.workspace.chapters.findIndex(chapter => chapter.id === rangeStart.value)
)
const endIndex = computed(() =>
  props.workspace.chapters.findIndex(chapter => chapter.id === rangeEnd.value)
)
const rangeInvalid = computed(() =>
  startIndex.value < 0 || endIndex.value < startIndex.value
)
const selectedCount = computed(() =>
  rangeInvalid.value ? 0 : endIndex.value - startIndex.value + 1
)
const running = computed(() => props.workspace.status === 'running')
</script>

<template>
  <section aria-labelledby="novel-info-heading" class="w-full">
    <div class="mb-3 flex items-center justify-between">
      <h2 class="font-semibold text-highlighted">
        Start translation chapters by index
      </h2>
      <UButton
        class="ml-auto"
        label="Configure AI"
        icon="lucide:settings-2"
        color="neutral"
        variant="soft"
        size="sm"
        @click="emit('configure')"
      />
    </div>

    <div
      v-if="!workspace.configuration"
      class="flex w-full flex-col gap-3 py-2 sm:flex-row sm:items-center sm:justify-between"
    >
      <div class="flex items-start gap-3">
        <span class="flex size-9 shrink-0 items-center justify-center rounded-lg bg-warning/10">
          <UIcon name="lucide:settings-2" class="size-4 text-warning" />
        </span>
        <div>
          <p class="text-sm font-medium text-highlighted">
            AI translation is not configured
          </p>
          <p class="text-xs text-muted">
            Choose a provider, model, and global prompt before translating chapters.
          </p>
        </div>
      </div>
    </div>

    <div v-else class="space-y-4">
      <div class="flex flex-wrap items-center gap-2">
        <UBadge :label="workspace.targetLanguage.label" icon="lucide:globe-2" variant="subtle" />
        <span class="text-xs text-muted">
          {{ workspace.configuration.providerName }} · {{ workspace.configuration.modelName }}
        </span>
      </div>

      <div class="grid gap-4 sm:grid-cols-2 lg:grid-cols-[1fr_1fr_auto]">
        <UFormField label="Chapter Index From" required>
          <UInputNumber
            v-model="rangeStartChapterIndex"
            :min="firstChapterIndex"
            :max="lastChapterIndex"
            :step="1"
            :disabled="running"
            class="w-full"
          />
        </UFormField>
        <UFormField
          label="Chapter Index To"
          required
          :error="rangeInvalid
            ? 'Choose a chapter index after the starting chapter index.'
            : undefined"
        >
          <UInputNumber
            v-model="rangeEndChapterIndex"
            :min="firstChapterIndex"
            :max="lastChapterIndex"
            :step="1"
            :disabled="running"
            class="w-full"
          />
        </UFormField>
        <div class="flex items-end gap-2">
          <UButton
            label="Start"
            icon="lucide:play"
            size="sm"
            :disabled="running || rangeInvalid"
            @click="emit('start')"
          />
          <UButton
            label="Stop queued"
            icon="lucide:square"
            color="neutral"
            variant="soft"
            size="sm"
            :disabled="!running || workspace.progress.queued === 0"
            @click="emit('stop')"
          />
        </div>
      </div>

      <div class="space-y-1.5">
        <div class="flex justify-between gap-3 text-xs text-muted">
          <span>Translation progress</span>
          <span class="tabular-nums">
            {{ workspace.progress.translated }} / {{ workspace.progress.total }} chapters
          </span>
        </div>
        <UProgress :model-value="workspace.progress.translated" :max="Math.max(workspace.progress.total, 1)" size="xs" />
      </div>

      <p class="text-xs text-muted">
        {{ selectedCount }} {{ selectedCount === 1 ? 'chapter' : 'chapters' }} selected for this translation run.
        Chapter indexes follow novel order and include additional chapters.
      </p>
    </div>
  </section>
</template>
