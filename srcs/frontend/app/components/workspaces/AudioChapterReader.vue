<script setup lang="ts">
import type {
  AudioChapterContent,
  AudioWorkspace,
  AudioWorkspaceChapter,
  AudioWorkspaceTaskResult
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
const taskResult = ref<AudioWorkspaceTaskResult | null>(null)
const resultError = ref(false)
const activeSentenceIndex = ref<number | null>(null)
const playbackState = ref<'idle' | 'playing' | 'paused'>('idle')
const sequentialPlayMode = ref(false)
let activeAudio: HTMLAudioElement | null = null
let contentRequestId = 0
let resultRequestId = 0
const selectedTask = computed(() =>
  props.workspace.tasks.find(task => task.id === props.chapter?.id) || null
)
const characterCount = computed(() =>
  formatCharacterCount(content.value?.content || [])
)
const audioUrls = computed(() => {
  const sentenceCount = content.value?.content.length || 0
  const result = taskResult.value
  const task = selectedTask.value
  if (
    !result
    || !task
    || task.status !== 'completed'
    || !task.resultAvailable
    || task.sourceUpdated
    || result.workspaceId !== props.workspace.id
    || result.taskId !== task.id
    || result.sentences.length !== sentenceCount
  ) return []

  const urls = Array<string>(sentenceCount)
  for (const sentence of result.sentences) {
    if (
      !Number.isInteger(sentence.index)
      || sentence.index < 0
      || sentence.index >= sentenceCount
      || !sentence.audioUrl
      || urls[sentence.index]
    ) return []
    urls[sentence.index] = sentence.audioUrl
  }
  return urls.every(Boolean) ? urls : []
})
const narrationReady = computed(() =>
  Boolean(content.value?.content.length) && audioUrls.value.length === content.value?.content.length
)

watch(
  () => [props.chapter?.id, props.workspace.language],
  () => void loadContent(),
  { immediate: true }
)

watch(
  () => [
    props.chapter?.id,
    props.workspace.language,
    selectedTask.value?.resultAvailable,
    selectedTask.value?.sourceUpdated,
    selectedTask.value?.completedAt
  ],
  () => void loadTaskResult(),
  { immediate: true }
)

async function loadContent() {
  const requestId = ++contentRequestId
  resetPlayback()
  content.value = null
  error.value = false
  loading.value = false
  const chapter = props.chapter
  if (!chapter?.contentAvailable) return
  loading.value = true
  try {
    const nextContent = await useAudioWorkspaceApi().getChapter(
      props.workspace.novelId,
      chapter.id,
      props.workspace.language
    )
    if (requestId === contentRequestId) content.value = nextContent
  } catch {
    if (requestId === contentRequestId) error.value = true
  } finally {
    if (requestId === contentRequestId) loading.value = false
  }
}

async function loadTaskResult() {
  const requestId = ++resultRequestId
  resetPlayback()
  taskResult.value = null
  resultError.value = false
  const task = selectedTask.value
  if (!task?.resultAvailable || task.sourceUpdated || !props.chapter) return

  try {
    const result = await useAudioWorkspaceApi().getTaskResult(
      props.workspace.id,
      task.id
    )
    if (requestId === resultRequestId) taskResult.value = result
  } catch {
    if (requestId === resultRequestId) resultError.value = true
  }
}

function disposeAudio() {
  if (!activeAudio) return
  activeAudio.onended = null
  activeAudio.onerror = null
  activeAudio.pause()
  activeAudio.removeAttribute('src')
  activeAudio.load()
  activeAudio = null
}

function resetPlayback() {
  disposeAudio()
  activeSentenceIndex.value = null
  playbackState.value = 'idle'
  sequentialPlayMode.value = false
}

function handlePlaybackError(audio: HTMLAudioElement) {
  if (activeAudio !== audio) return
  resetPlayback()
  resultError.value = true
}

async function playSegment(index: number) {
  const url = audioUrls.value[index]
  if (!url) return

  if (activeSentenceIndex.value === index && activeAudio) {
    const audio = activeAudio
    try {
      await audio.play()
      if (activeAudio === audio) playbackState.value = 'playing'
    } catch {
      handlePlaybackError(audio)
    }
    return
  }

  disposeAudio()
  const audio = new Audio(url)
  activeAudio = audio
  activeSentenceIndex.value = index
  playbackState.value = 'playing'
  resultError.value = false
  audio.onended = () => {
    if (activeAudio !== audio) return
    const nextIndex = index + 1
    if (sequentialPlayMode.value && audioUrls.value[nextIndex]) {
      void playSegment(nextIndex)
      return
    }
    resetPlayback()
  }
  audio.onerror = () => handlePlaybackError(audio)

  try {
    await audio.play()
  } catch {
    handlePlaybackError(audio)
  }
}

function toggleSentencePlayback(index: number) {
  if (!audioUrls.value[index]) return
  if (activeSentenceIndex.value === index && playbackState.value === 'playing') {
    sequentialPlayMode.value = false
    pausePlayback()
    return
  }

  sequentialPlayMode.value = false
  void playSegment(index)
}

function pausePlayback() {
  if (playbackState.value !== 'playing' || !activeAudio) return
  activeAudio.pause()
  playbackState.value = 'paused'
}

function playAllSentences() {
  if (!narrationReady.value) return
  if (playbackState.value === 'playing' && sequentialPlayMode.value) {
    pausePlayback()
    return
  }
  if (playbackState.value === 'paused' && sequentialPlayMode.value) {
    void playSegment(activeSentenceIndex.value ?? 0)
    return
  }
  sequentialPlayMode.value = true
  void playSegment(0)
}

function stopAllSentences() {
  resetPlayback()
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
          :icon="sequentialPlayMode && playbackState === 'playing' ? 'lucide:pause' : 'lucide:play'"
          :color="sequentialPlayMode ? 'primary' : 'neutral'"
          variant="ghost"
          :aria-label="sequentialPlayMode && playbackState === 'playing' ? 'Pause all sentences' : 'Play all sentences'"
          :disabled="!narrationReady"
          @click="playAllSentences"
        />
        <UButton
          v-if="sequentialPlayMode"
          icon="lucide:stop-circle"
          color="neutral"
          variant="ghost"
          aria-label="Stop sequential playback"
          @click="stopAllSentences"
        />
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
          :actions="[{ label: 'Retry', color: 'error', variant: 'soft', onClick: loadContent }]"
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
            {{ content.content.length }} sentences · {{ characterCount }} characters
          </p>
        </header>

        <UAlert
          v-if="resultError"
          class="mb-6"
          color="warning"
          variant="subtle"
          icon="lucide:audio-lines"
          title="Narration unavailable"
          description="The chapter text is still available, but its audio could not be loaded or played."
        />

        <div v-if="content.content.length" class="space-y-3">
          <section
            v-for="(line, index) in content.content"
            :key="index"
            class="group rounded-lg border p-4 transition-all duration-300 sm:flex sm:items-start sm:gap-4"
            :class="activeSentenceIndex === index
              ? 'border-primary/70 bg-primary/5 shadow-sm ring-1 ring-primary/30'
              : 'border-default bg-default'"
            :aria-labelledby="`audio-line-${index}`"
            :aria-current="activeSentenceIndex === index ? 'step' : undefined"
          >
            <div class="min-w-0 flex-1">
              <p class="mb-2 flex items-center gap-2 text-xs font-medium tabular-nums text-muted">
                <span>Sentence {{ index + 1 }}</span>
                <span
                  v-if="activeSentenceIndex === index && playbackState === 'playing'"
                  class="inline-flex items-center gap-0.5 text-primary"
                  aria-label="Playing"
                >
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
                :icon="activeSentenceIndex === index && playbackState === 'playing' ? 'lucide:pause' : 'lucide:play'"
                color="neutral"
                variant="ghost"
                size="sm"
                square
                :disabled="!audioUrls[index]"
                :aria-label="activeSentenceIndex === index && playbackState === 'playing'
                  ? `Playing sentence ${index + 1}`
                  : `Play sentence ${index + 1}`"
                @click="toggleSentencePlayback(index)"
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
