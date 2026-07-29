<script setup lang="ts">
import type { TranslationWorkspace } from '~/types/translation-workspace'

const props = withDefaults(defineProps<{
  workspace: TranslationWorkspace
  syncing?: boolean
  starting?: boolean
  stopping?: boolean
}>(), {
  syncing: false,
  starting: false,
  stopping: false
})
const rangeStart = defineModel<string>('rangeStart', { required: true })
const rangeEnd = defineModel<string>('rangeEnd', { required: true })
const refetch = defineModel<boolean>('refetch', { default: false })
const force = defineModel<boolean>('force', { default: false })

const emit = defineEmits<{
  configure: []
  sync: []
  start: []
  stop: []
}>()

const availableChapters = computed(() =>
  props.workspace.chapters.filter(chapter => !chapter.sourceRemoved)
)
const rangeStartChapterIndex = computed<number | undefined>({
  get: () => availableChapters.value.find(
    chapter => chapter.id === rangeStart.value
  )?.chapterIndex,
  set: (value) => {
    const chapter = availableChapters.value.find(item => item.chapterIndex === value)
    if (chapter) rangeStart.value = chapter.id
  }
})
const rangeEndChapterIndex = computed<number | undefined>({
  get: () => availableChapters.value.find(
    chapter => chapter.id === rangeEnd.value
  )?.chapterIndex,
  set: (value) => {
    const chapter = availableChapters.value.find(item => item.chapterIndex === value)
    if (chapter) rangeEnd.value = chapter.id
  }
})
const firstChapterIndex = computed(() => availableChapters.value[0]?.chapterIndex || 1)
const lastChapterIndex = computed(() =>
  availableChapters.value.at(-1)?.chapterIndex || 1
)

const startIndex = computed(() =>
  availableChapters.value.findIndex(chapter => chapter.id === rangeStart.value)
)
const endIndex = computed(() =>
  availableChapters.value.findIndex(chapter => chapter.id === rangeEnd.value)
)
const rangeInvalid = computed(() =>
  startIndex.value < 0 || endIndex.value < startIndex.value
)
const busy = computed(() => props.syncing || props.starting || props.stopping)
</script>

<template>
  <section aria-labelledby="novel-info-heading" class="w-full">
    <div class="mb-3 flex items-center justify-between">
      <h2 class="font-semibold text-highlighted">
        Start translation chapters by index
      </h2>
      <div class="ml-auto flex items-center gap-2">
        <UButton
          label="Sync chapters"
          icon="lucide:refresh-cw"
          color="neutral"
          variant="ghost"
          size="sm"
          :loading="syncing"
          :disabled="busy"
          @click="emit('sync')"
        />
        <UButton
          label="Configure AI"
          icon="lucide:settings-2"
          color="neutral"
          variant="soft"
          size="sm"
          :disabled="busy"
          @click="emit('configure')"
        />
      </div>
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
            :disabled="busy || !availableChapters.length"
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
            :disabled="busy || !availableChapters.length"
            class="w-full"
          />
        </UFormField>
        <div class="flex items-end gap-2">
          <UButton
            label="Start"
            icon="lucide:play"
            size="sm"
            :loading="starting"
            :disabled="busy || rangeInvalid || !availableChapters.length"
            @click="emit('start')"
          />
          <UButton
            label="Stop queued"
            icon="lucide:square"
            color="neutral"
            variant="soft"
            size="sm"
            :loading="stopping"
            :disabled="busy || workspace.progress.queued === 0"
            @click="emit('stop')"
          />
        </div>
      </div>

      <div class="flex flex-wrap gap-x-5 gap-y-2">
        <UCheckbox
          v-model="refetch"
          label="Refetch existing results"
          description="Regenerate translated chapters and source-updated content."
          :disabled="busy"
        />
        <UCheckbox
          v-model="force"
          label="Force queued or running tasks"
          description="Republish tasks already claimed by a run."
          :disabled="busy"
        />
      </div>
    </div>
  </section>
</template>
