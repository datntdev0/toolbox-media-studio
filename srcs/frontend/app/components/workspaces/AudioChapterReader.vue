<script setup lang="ts">
import type {
  AudioChapterContent,
  AudioSubtitleCue,
  AudioWorkspace,
  AudioWorkspaceChapter,
  AudioWorkspaceTaskResult
} from '~/types/audio-workspace'
import { parseChapterSrt } from '~/utils/audio-subtitles'

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
const exporting = ref(false)
const activeSentenceIndex = ref<number | null>(null)
const playbackState = ref<'idle' | 'playing' | 'paused'>('idle')
const playbackMode = ref<'chapter' | 'sentence' | null>(null)
const subtitleCues = ref<AudioSubtitleCue[]>([])
const toast = useToast()
let activeAudio: HTMLAudioElement | null = null
let subtitleAbortController: AbortController | null = null
let sentenceEndTimer: ReturnType<typeof setTimeout> | null = null
let contentRequestId = 0
let resultRequestId = 0
const selectedTask = computed(() =>
  props.workspace.tasks.find(task => task.id === props.chapter?.id) || null
)
const characterCount = computed(() =>
  formatCharacterCount(content.value?.content || [])
)
const sequentialPlayMode = computed(() => playbackMode.value === 'chapter')
const narrationReady = computed(() => {
  const sentenceCount = content.value?.content.length || 0
  const result = taskResult.value
  const task = selectedTask.value
  return Boolean(
    sentenceCount
    && result?.audioUrl
    && result.subtitleUrl
    && task?.status === 'completed'
    && task.resultAvailable
    && !task.sourceUpdated
    && result.workspaceId === props.workspace.id
    && result.taskId === task.id
    && subtitleCues.value.length === sentenceCount
  )
})

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
    selectedTask.value?.completedAt,
    content.value
  ],
  () => void loadNarration(),
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

async function loadNarration() {
  const requestId = ++resultRequestId
  subtitleAbortController?.abort()
  subtitleAbortController = null
  resetPlayback()
  taskResult.value = null
  subtitleCues.value = []
  resultError.value = false
  const task = selectedTask.value
  const chapterContent = content.value
  if (
    !task?.resultAvailable
    || task.status !== 'completed'
    || task.sourceUpdated
    || !props.chapter
    || !chapterContent
    || chapterContent.id !== props.chapter.id
    || !chapterContent.content.length
  ) return

  const abortController = new AbortController()
  subtitleAbortController = abortController
  try {
    const result = await useAudioWorkspaceApi().getTaskResult(
      props.workspace.id,
      task.id
    )
    if (
      result.workspaceId !== props.workspace.id
      || result.taskId !== task.id
      || !result.audioUrl
      || !result.subtitleUrl
    ) throw new Error('Narration result is incomplete')

    const response = await fetch(result.subtitleUrl, {
      signal: abortController.signal
    })
    if (!response.ok) throw new Error(`Unable to load subtitles (${response.status})`)
    const cues = parseChapterSrt(await response.text(), chapterContent.content)
    if (requestId === resultRequestId) {
      taskResult.value = result
      subtitleCues.value = cues
    }
  } catch (cause) {
    if (cause instanceof DOMException && cause.name === 'AbortError') return
    if (requestId === resultRequestId) resultError.value = true
  } finally {
    if (subtitleAbortController === abortController) subtitleAbortController = null
  }
}

function disposeAudio() {
  clearSentenceEndTimer()
  if (!activeAudio) return
  activeAudio.ontimeupdate = null
  activeAudio.onended = null
  activeAudio.onerror = null
  activeAudio.pause()
  activeAudio.removeAttribute('src')
  activeAudio.load()
  activeAudio = null
}

function clearSentenceEndTimer() {
  if (sentenceEndTimer == null) return
  clearTimeout(sentenceEndTimer)
  sentenceEndTimer = null
}

function resetPlayback() {
  disposeAudio()
  activeSentenceIndex.value = null
  playbackState.value = 'idle'
  playbackMode.value = null
}

function handlePlaybackError(audio: HTMLAudioElement) {
  if (activeAudio !== audio) return
  resetPlayback()
  resultError.value = true
}

function cueIndexAtTime(time: number): number | null {
  const index = subtitleCues.value.findIndex(cue => (
    time >= cue.startSeconds && time < cue.endSeconds
  ))
  return index === -1 ? null : index
}

function finishPlayback(audio: HTMLAudioElement) {
  if (activeAudio !== audio) return
  clearSentenceEndTimer()
  audio.pause()
  playbackState.value = 'idle'
  playbackMode.value = null
  activeSentenceIndex.value = null
}

function ensureAudio(): HTMLAudioElement | null {
  if (activeAudio) return activeAudio
  const url = taskResult.value?.audioUrl
  if (!url) return null

  const audio = new Audio(url)
  activeAudio = audio
  audio.preload = 'metadata'
  audio.ontimeupdate = () => {
    if (activeAudio !== audio) return
    if (playbackMode.value === 'chapter') {
      activeSentenceIndex.value = cueIndexAtTime(audio.currentTime)
      return
    }
    if (playbackMode.value !== 'sentence' || activeSentenceIndex.value == null) return
    const cue = subtitleCues.value[activeSentenceIndex.value]
    if (cue && audio.currentTime >= cue.endSeconds) finishPlayback(audio)
  }
  audio.onended = () => finishPlayback(audio)
  audio.onerror = () => handlePlaybackError(audio)
  return audio
}

function scheduleSentenceEnd(audio: HTMLAudioElement) {
  clearSentenceEndTimer()
  const index = activeSentenceIndex.value
  const cue = index == null ? null : subtitleCues.value[index]
  if (!cue || playbackMode.value !== 'sentence') return
  const remainingMilliseconds = Math.max(0, (cue.endSeconds - audio.currentTime) * 1000)
  sentenceEndTimer = setTimeout(() => {
    if (activeAudio === audio && playbackMode.value === 'sentence') finishPlayback(audio)
  }, remainingMilliseconds)
}

async function resumeAudio(audio: HTMLAudioElement) {
  if (activeAudio === audio) playbackState.value = 'playing'
  try {
    await audio.play()
    if (activeAudio === audio && playbackState.value === 'playing') {
      scheduleSentenceEnd(audio)
    }
  } catch (cause) {
    if (
      activeAudio === audio
      && playbackState.value === 'paused'
      && cause instanceof DOMException
      && cause.name === 'AbortError'
    ) return
    handlePlaybackError(audio)
  }
}

function playSentence(index: number) {
  const cue = subtitleCues.value[index]
  const audio = ensureAudio()
  if (!cue || !audio) return

  clearSentenceEndTimer()
  const isResuming = playbackMode.value === 'sentence'
    && activeSentenceIndex.value === index
    && playbackState.value === 'paused'
    && audio.currentTime >= cue.startSeconds
    && audio.currentTime < cue.endSeconds
  if (!isResuming) audio.currentTime = cue.startSeconds
  playbackMode.value = 'sentence'
  activeSentenceIndex.value = index
  resultError.value = false
  void resumeAudio(audio)
}

function toggleSentencePlayback(index: number) {
  if (!subtitleCues.value[index]) return
  if (
    playbackMode.value === 'sentence'
    && activeSentenceIndex.value === index
    && playbackState.value === 'playing'
  ) {
    pausePlayback()
    return
  }

  playSentence(index)
}

function pausePlayback() {
  if (playbackState.value !== 'playing' || !activeAudio) return
  clearSentenceEndTimer()
  activeAudio.pause()
  playbackState.value = 'paused'
}

function playAllSentences() {
  if (!narrationReady.value) return
  if (playbackState.value === 'playing' && playbackMode.value === 'chapter') {
    pausePlayback()
    return
  }
  const audio = ensureAudio()
  if (!audio) return
  if (playbackState.value === 'paused' && playbackMode.value === 'chapter') {
    void resumeAudio(audio)
    return
  }
  clearSentenceEndTimer()
  audio.currentTime = 0
  playbackMode.value = 'chapter'
  activeSentenceIndex.value = cueIndexAtTime(0)
  resultError.value = false
  void resumeAudio(audio)
}

function stopAllSentences() {
  resetPlayback()
}

async function exportAudio() {
  if (!narrationReady.value || !props.chapter || exporting.value) return
  exporting.value = true
  try {
    const result = await useAudioWorkspaceApi().exportTask(
      props.workspace.id,
      props.chapter.id
    )
    if (result.exportUrl) {
      const link = document.createElement('a')
      link.href = result.exportUrl
      link.download = `${props.workspace.title}-${props.chapter.title}.wav`
      link.style.display = 'none'
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
      toast.add({
        title: 'Export started',
        description: 'Your audio file download should begin shortly.',
        color: 'success',
        icon: 'lucide:download'
      })
    }
  } catch (cause) {
    toast.add({
      title: 'Export failed',
      description: cause instanceof Error ? cause.message : 'Unable to export audio. Please try again.',
      color: 'error',
      icon: 'lucide:circle-alert'
    })
  } finally {
    exporting.value = false
  }
}

onBeforeUnmount(() => {
  subtitleAbortController?.abort()
  resetPlayback()
})
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
          icon="lucide:download"
          color="neutral"
          variant="ghost"
          aria-label="Export audio"
          :disabled="!narrationReady"
          :loading="exporting"
          @click="exportAudio"
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
                :disabled="!subtitleCues[index]"
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
