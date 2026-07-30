<script setup lang="ts">
import type {
  AudioChapterContent,
  AudioWorkspace,
  AudioWorkspaceChapter
} from '~/types/audio-workspace'

const props = defineProps<{
  workspace: AudioWorkspace
  chapter: AudioWorkspaceChapter | null
  position: number
  total: number
  canPrevious: boolean
  canNext: boolean
  mobile?: boolean
}>()
const emit = defineEmits<{
  close: []
  navigate: [offset: number]
}>()
const content = ref<AudioChapterContent | null>(null)
const loading = ref(false)
const error = ref(false)
const characterCount = computed(() =>
  formatCharacterCount(content.value?.content || [])
)

watch(
  () => [props.chapter?.id, props.workspace.language],
  () => void load(),
  { immediate: true }
)

async function load() {
  content.value = null
  error.value = false
  if (!props.chapter?.contentAvailable) return
  loading.value = true
  try {
    content.value = await useAudioWorkspaceApi().getChapter(
      props.workspace.novelId,
      props.chapter.id,
      props.workspace.language
    )
  } catch {
    error.value = true
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <UDashboardPanel id="audio-chapter-reader">
    <UDashboardNavbar :title="content?.title || chapter?.title || 'Chapter content'" :toggle="false">
      <template v-if="mobile" #leading>
        <UButton
          icon="lucide:x"
          color="neutral"
          variant="ghost"
          aria-label="Close chapter"
          @click="emit('close')"
        />
      </template>
      <template #right>
        <span v-if="chapter" class="hidden text-xs text-muted sm:inline">
          {{ position }} / {{ total }}
        </span>
        <UButton
          icon="lucide:chevron-left"
          color="neutral"
          variant="ghost"
          aria-label="Previous chapter"
          :disabled="!canPrevious"
          @click="emit('navigate', -1)"
        />
        <UButton
          icon="lucide:chevron-right"
          color="neutral"
          variant="ghost"
          aria-label="Next chapter"
          :disabled="!canNext"
          @click="emit('navigate', 1)"
        />
      </template>
    </UDashboardNavbar>

    <div class="min-h-0 flex-1 overflow-y-auto">
      <div v-if="loading" class="mx-auto max-w-4xl space-y-4 p-6 sm:p-10" aria-label="Loading chapter">
        <USkeleton class="h-7 w-2/3" />
        <USkeleton v-for="index in 8" :key="index" class="h-20 rounded-lg" />
      </div>

      <div v-else-if="error" class="flex min-h-full items-center justify-center p-6">
        <UAlert
          class="max-w-lg"
          color="error"
          variant="subtle"
          icon="lucide:circle-alert"
          title="Unable to load chapter"
          description="The selected language content could not be opened."
          :actions="[{ label: 'Retry', color: 'error', variant: 'soft', onClick: load }]"
        />
      </div>

      <div v-else-if="chapter && !chapter.contentAvailable" class="flex min-h-full items-center justify-center p-6">
        <UEmpty
          icon="lucide:file-clock"
          :title="workspace.sourceType === 'translation' ? 'Translation unavailable' : 'Content unavailable'"
          description="This chapter does not have content in the workspace’s selected language."
          size="xl"
        />
      </div>

      <article v-else-if="chapter && content" class="mx-auto max-w-4xl px-4 py-8 sm:px-8 sm:py-12">
        <header class="mb-8 border-b border-default pb-6 text-center">
          <p class="mb-2 text-xs font-medium tracking-widest text-primary uppercase">
            Chapter {{ content.chapterNumber ?? position }}
          </p>
          <h1 class="text-2xl font-semibold text-highlighted sm:text-3xl">
            {{ content.title }}
          </h1>
          <p class="mt-2 text-xs tabular-nums text-muted">
            {{ content.content.length }} segments · {{ characterCount }} characters
          </p>
        </header>

        <div v-if="content.content.length" class="space-y-3">
          <section
            v-for="(line, index) in content.content"
            :key="index"
            class="group rounded-lg border border-default bg-default p-4 sm:flex sm:items-start sm:gap-4"
            :aria-labelledby="`audio-line-${index}`"
          >
            <div class="min-w-0 flex-1">
              <p class="mb-2 text-xs font-medium tabular-nums text-muted">
                Segment {{ index + 1 }}
              </p>
              <p :id="`audio-line-${index}`" class="whitespace-pre-wrap text-base/8 text-toned sm:text-lg/9">
                {{ line }}
              </p>
            </div>
            <div class="mt-3 flex shrink-0 gap-2 sm:mt-0">
              <UTooltip text="TTS generation is not available in this release">
                <span>
                  <UButton
                    label="TTS"
                    icon="lucide:waves"
                    color="neutral"
                    variant="soft"
                    size="sm"
                    disabled
                    :aria-label="`Generate speech for segment ${index + 1}`"
                  />
                </span>
              </UTooltip>
              <UTooltip text="No generated audio is available">
                <span>
                  <UButton
                    icon="lucide:play"
                    color="neutral"
                    variant="ghost"
                    size="sm"
                    square
                    disabled
                    :aria-label="`Play segment ${index + 1}`"
                  />
                </span>
              </UTooltip>
            </div>
          </section>
        </div>
        <p v-else class="text-center italic text-muted">
          This chapter has no text segments.
        </p>
      </article>

      <div v-else class="flex min-h-full items-center justify-center p-6">
        <UEmpty
          icon="lucide:audio-lines"
          title="Select a chapter"
          description="Choose a chapter from the outline to prepare its narration."
          size="xl"
        />
      </div>
    </div>
  </UDashboardPanel>
</template>
