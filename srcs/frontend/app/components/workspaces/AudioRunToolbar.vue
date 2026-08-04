<script setup lang="ts">
import type { AudioWorkspace } from '~/types/audio-workspace'

const props = withDefaults(defineProps<{
  workspace: AudioWorkspace
  starting?: boolean
  stopping?: boolean
}>(), {
  starting: false,
  stopping: false
})

const provider = defineModel<string>('provider', { required: true })
const voice = defineModel<string>('voice', { required: true })
const chapterIndexFrom = defineModel<number>('chapterIndexFrom', { required: true })
const chapterIndexTo = defineModel<number>('chapterIndexTo', { required: true })
const refetch = defineModel<boolean>('refetch', { default: false })
const force = defineModel<boolean>('force', { default: false })

const emit = defineEmits<{
  start: []
  stop: []
}>()

const providers = ['Built-in Microsoft Foundry']
const voices = ['vi-VN-HoaiMyNeural', 'vi-VN-NamMinhNeural']
const availableChapters = computed(() =>
  props.workspace.chapters.filter(chapter => chapter.contentAvailable && !chapter.sourceRemoved)
)
const firstChapterIndex = computed(() =>
  (availableChapters.value[0]?.manifestIndex ?? 0) + 1
)
const lastChapterIndex = computed(() =>
  (availableChapters.value.at(-1)?.manifestIndex ?? 0) + 1
)
const rangeInvalid = computed(() =>
  !availableChapters.value.length
  || chapterIndexFrom.value > chapterIndexTo.value
  || chapterIndexFrom.value < firstChapterIndex.value
  || chapterIndexTo.value > lastChapterIndex.value
)
const busy = computed(() => props.starting || props.stopping)
</script>

<template>
  <section aria-labelledby="audio-run-heading" class="w-full">
    <div class="mb-3 flex items-center justify-between">
      <h2 id="audio-run-heading" class="font-semibold text-highlighted">
        Start audio chapters by index
      </h2>
    </div>

    <div class="space-y-4">
      <div class="flex flex-row justify-between gap-4">
        <div class="flex flex-row gap-2">
          <UFormField label="Provider">
            <USelect
              v-model="provider"
              :items="providers"
              :disabled="busy"
              class="w-full"
              aria-label="TTS provider"
            />
          </UFormField>
          <UFormField label="Voice">
            <USelect
              v-model="voice"
              :items="voices"
              :disabled="busy"
              class="w-full"
              aria-label="TTS voice"
            />
          </UFormField>
        </div>
        <div class="flex flex-row gap-2">
          <UFormField label="Chapter Index From" required>
            <UInputNumber
              v-model="chapterIndexFrom"
              :min="firstChapterIndex"
              :max="lastChapterIndex"
              :step="1"
              :disabled="busy || !availableChapters.length"
              class="w-[150px]"
            />
          </UFormField>
          <UFormField label="Chapter Index To" required>
            <UInputNumber
              v-model="chapterIndexTo"
              :min="firstChapterIndex"
              :max="lastChapterIndex"
              :step="1"
              :disabled="busy || !availableChapters.length"
              class="w-[150px]"
            />
          </UFormField>
        </div>
      </div>

      <div class="flex flex-wrap items-start justify-between gap-x-5 gap-y-2">
        <div class="flex items-end gap-2">
          <UCheckbox
            v-model="refetch"
            label="Refetch existing results"
            description="Regenerate audio for chapters."
            :disabled="busy"
          />
          <UCheckbox
            v-model="force"
            label="Force queued or running tasks"
            description="Republish tasks already claimed."
            :disabled="busy"
          />
        </div>
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
    </div>
  </section>
</template>
