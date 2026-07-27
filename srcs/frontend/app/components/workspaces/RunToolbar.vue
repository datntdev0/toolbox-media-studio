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

const rangeStartNumber = computed<number | undefined>({
  get: () => props.workspace.chapters.find(chapter => chapter.id === rangeStart.value)?.number,
  set: (value) => {
    const chapter = props.workspace.chapters.find(item => item.number === value)
    if (chapter) rangeStart.value = chapter.id
  }
})
const rangeEndNumber = computed<number | undefined>({
  get: () => props.workspace.chapters.find(chapter => chapter.id === rangeEnd.value)?.number,
  set: (value) => {
    const chapter = props.workspace.chapters.find(item => item.number === value)
    if (chapter) rangeEnd.value = chapter.id
  }
})
const firstChapterNumber = computed(() => props.workspace.chapters[0]?.number || 1)
const lastChapterNumber = computed(() => props.workspace.chapters.at(-1)?.number || 1)

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
        Start translation chapter by range
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
        <UFormField label="Chapter from" required>
          <UInputNumber
            v-model="rangeStartNumber"
            :min="firstChapterNumber"
            :max="lastChapterNumber"
            :step="1"
            :disabled="running"
            class="w-full"
          />
        </UFormField>
        <UFormField
          label="Chapter to"
          required
          :error="rangeInvalid ? 'Choose a chapter after the starting chapter.' : undefined"
        >
          <UInputNumber
            v-model="rangeEndNumber"
            :min="firstChapterNumber"
            :max="lastChapterNumber"
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
      </p>
    </div>
  </section>
</template>
