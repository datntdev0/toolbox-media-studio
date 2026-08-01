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
  starting?: boolean
  stopping?: boolean
}>()
const emit = defineEmits<{
  close: []
  navigate: [offset: number]
  start: []
  stop: []
}>()
const provider = defineModel<string>('provider', { required: true })
const voice = defineModel<string>('voice', { required: true })
const chapterIndexFrom = defineModel<number>('chapterIndexFrom', { required: true })
const chapterIndexTo = defineModel<number>('chapterIndexTo', { required: true })
const refetch = defineModel<boolean>('refetch', { default: false })
const force = defineModel<boolean>('force', { default: false })
const content = ref<AudioChapterContent | null>(null)
const loading = ref(false)
const error = ref(false)
const activeSegmentIndex = ref<number | null>(null)
const playbackState = ref<'idle' | 'playing' | 'paused'>('idle')
const playbackTimer = ref<ReturnType<typeof setTimeout> | null>(null)
const characterCount = computed(() =>
  formatCharacterCount(content.value?.content || [])
)

watch(
  () => [props.chapter?.id, props.workspace.language],
  () => void load(),
  { immediate: true }
)

async function load() {
  resetPlayback()
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

function clearPlaybackTimer() {
  if (playbackTimer.value) {
    clearTimeout(playbackTimer.value)
    playbackTimer.value = null
  }
}

function resetPlayback() {
  clearPlaybackTimer()
  activeSegmentIndex.value = null
  playbackState.value = 'idle'
}

function schedulePlayback() {
  clearPlaybackTimer()
  playbackTimer.value = setTimeout(() => {
    playbackTimer.value = null
    if (playbackState.value !== 'playing' || activeSegmentIndex.value === null) return

    activeSegmentIndex.value = null
    playbackState.value = 'idle'
  }, 5000)
}

function playSegment(index: number) {
  if (!content.value?.content[index]) return

  clearPlaybackTimer()
  activeSegmentIndex.value = index
  playbackState.value = 'playing'
  schedulePlayback()
}

function toggleSegmentPlayback(index: number) {
  if (activeSegmentIndex.value === index && playbackState.value === 'playing') {
    pausePlayback()
    return
  }

  playSegment(index)
}

function pausePlayback() {
  if (playbackState.value !== 'playing') return
  clearPlaybackTimer()
  playbackState.value = 'paused'
}

onBeforeUnmount(resetPlayback)
</script>

<template>
  <UDashboardPanel id="audio-chapter-reader">
    <UDashboardNavbar
      :title="content?.title || chapter?.title || 'Chapter content'"
      :toggle="false"
      :ui="{
        root: 'h-auto min-w-0 flex-wrap items-start gap-y-2 py-2',
        left: 'max-w-[calc(100%-7rem)]',
        center: 'order-3 flex min-w-0 basis-full',
        right: 'ml-auto'
      }"
    >
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

    <UDashboardToolbar class="py-4">
      <WorkspacesAudioRunToolbar
        v-model:provider="provider"
        v-model:voice="voice"
        v-model:chapter-index-from="chapterIndexFrom"
        v-model:chapter-index-to="chapterIndexTo"
        v-model:refetch="refetch"
        v-model:force="force"
        :workspace="workspace"
        :starting="starting"
        :stopping="stopping"
        @start="emit('start')"
        @stop="emit('stop')"
      />
    </UDashboardToolbar>

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
            class="group rounded-lg border p-4 transition-all duration-300 sm:flex sm:items-start sm:gap-4"
            :class="activeSegmentIndex === index
              ? 'border-primary/70 bg-primary/5 shadow-sm ring-1 ring-primary/30'
              : 'border-default bg-default'"
            :aria-labelledby="`audio-line-${index}`"
            :aria-current="activeSegmentIndex === index ? 'step' : undefined"
          >
            <div class="min-w-0 flex-1">
              <p class="mb-2 flex items-center gap-2 text-xs font-medium tabular-nums text-muted">
                <span>Segment {{ index + 1 }}</span>
                <span v-if="activeSegmentIndex === index" class="inline-flex items-center gap-0.5 text-primary" aria-label="Playing">
                  <span class="h-3 w-0.5 animate-pulse rounded-full bg-current" />
                  <span class="h-2 w-0.5 animate-pulse rounded-full bg-current [animation-delay:120ms]" />
                  <span class="h-4 w-0.5 animate-pulse rounded-full bg-current [animation-delay:240ms]" />
                </span>
              </p>
              <p :id="`audio-line-${index}`" class="whitespace-pre-wrap text-base/8 text-toned sm:text-lg/9">
                {{ line }}
              </p>
            </div>
            <div class="mt-3 flex shrink-0 gap-2 sm:mt-0">
              <UButton
                :icon="activeSegmentIndex === index && playbackState === 'playing' ? 'lucide:pause' : 'lucide:play'"
                color="neutral"
                variant="ghost"
                size="sm"
                square
                :aria-label="activeSegmentIndex === index && playbackState === 'playing'
                  ? `Playing segment ${index + 1}`
                  : `Play segment ${index + 1}`"
                @click="toggleSegmentPlayback(index)"
              />
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
