<script setup lang="ts">
import { breakpointsTailwind } from '@vueuse/core'
import type { AudioWorkspace, AudioWorkspaceChapter } from '~/types/audio-workspace'

definePageMeta({ title: 'Audio workspace', middleware: ['auth'] })

const route = useRoute()
const router = useRouter()
const toast = useToast()
const audioApi = useAudioWorkspaceApi()
const breakpoints = useBreakpoints(breakpointsTailwind)
const isMobile = breakpoints.smaller('lg')
const workspace = ref<AudioWorkspace | null>(null)
const loading = ref(true)
const error = ref(false)
const editOpen = ref(false)
const starting = ref(false)
const stopping = ref(false)
const provider = ref('Built-in Microsoft Foundry')
const voice = ref('vi-VN-HoaiMyNeural')
const chapterIndexFrom = ref(1)
const chapterIndexTo = ref(1)
const refetch = ref(false)
const force = ref(false)
let realtimeRefreshTimer: ReturnType<typeof setTimeout> | undefined
const workspaceId = computed(() => String(route.params.id || ''))
const selectedId = computed(() => {
  const value = route.query.chapter
  return typeof value === 'string' && value ? value : null
})
const selectedIndex = computed(() =>
  workspace.value?.chapters.findIndex(item => item.id === selectedId.value) ?? -1
)
const selectedChapter = computed(() =>
  selectedIndex.value >= 0
    ? workspace.value?.chapters[selectedIndex.value] || null
    : null
)
const mobileReaderOpen = computed({
  get: () => Boolean(isMobile.value && selectedChapter.value),
  set: (value: boolean) => {
    if (!value) void replaceChapter()
  }
})

useHead(() => ({
  title: workspace.value?.title
    ? `Audio workspace · ${workspace.value.title}`
    : 'Audio workspace'
}))

onMounted(() => void loadWorkspace())
watch(workspaceId, () => void loadWorkspace())
watch(isMobile, (mobile) => {
  if (!mobile && workspace.value && !selectedChapter.value) void selectDefaultChapter()
})

async function loadWorkspace() {
  loading.value = true
  error.value = false
  try {
    applyWorkspace(await audioApi.get(workspaceId.value))
    if (!isMobile.value || selectedId.value) await selectDefaultChapter()
  } catch {
    workspace.value = null
    error.value = true
  } finally {
    loading.value = false
  }
}

function applyWorkspace(nextWorkspace: AudioWorkspace) {
  workspace.value = nextWorkspace
  const available = nextWorkspace.chapters.filter(
    chapter => chapter.contentAvailable && !chapter.sourceRemoved
  )
  const indexes = new Set(available.map(chapter => chapter.manifestIndex + 1))
  if (!indexes.has(chapterIndexFrom.value)) {
    chapterIndexFrom.value = (available[0]?.manifestIndex ?? 0) + 1
  }
  if (!indexes.has(chapterIndexTo.value)) {
    chapterIndexTo.value = (available.at(-1)?.manifestIndex ?? 0) + 1
  }
}

async function refreshWorkspace() {
  try {
    applyWorkspace(await audioApi.get(workspaceId.value))
  } catch {
    // Preserve the current reader while a background refresh races another update.
  }
}

async function selectDefaultChapter() {
  if (!workspace.value?.chapters.length || selectedChapter.value) return
  const first = workspace.value.chapters.find(chapter => chapter.contentAvailable)
    || workspace.value.chapters[0]
  if (first) await replaceChapter(first.id)
}

async function replaceChapter(id?: string) {
  const query = { ...route.query }
  if (id) query.chapter = id
  else delete query.chapter
  await router.replace({ query })
}

async function selectChapter(chapter: AudioWorkspaceChapter) {
  if (chapter.id === selectedId.value) return
  await replaceChapter(chapter.id)
}

async function navigateChapter(offset: number) {
  if (!workspace.value || selectedIndex.value < 0) return
  const chapter = workspace.value.chapters[selectedIndex.value + offset]
  if (chapter) await selectChapter(chapter)
}

function onUpdated(updated: AudioWorkspace) {
  if (!workspace.value) return
  workspace.value = {
    ...workspace.value,
    title: updated.title,
    updatedAt: updated.updatedAt
  }
}

async function startWorkspace() {
  if (!workspace.value || starting.value) return
  if (chapterIndexFrom.value > chapterIndexTo.value) return
  starting.value = true
  try {
    applyWorkspace(await audioApi.start(workspaceId.value, {
      provider: provider.value,
      voice: voice.value,
      chapterIndexFrom: chapterIndexFrom.value,
      chapterIndexTo: chapterIndexTo.value,
      refetch: refetch.value,
      force: force.value
    }))
    toast.add({
      title: 'Audio tasks queued',
      description: `Chapters ${chapterIndexFrom.value}–${chapterIndexTo.value} were submitted to the audio queue.`,
      color: 'success',
      icon: 'lucide:play'
    })
  } catch {
    await refreshWorkspace()
    toast.add({
      title: 'Unable to publish audio tasks',
      description: 'Queued state was preserved. Enable Force to retry tasks already queued.',
      color: 'error',
      icon: 'lucide:circle-alert'
    })
  } finally {
    starting.value = false
  }
}

async function stopWorkspace() {
  if (stopping.value) return
  stopping.value = true
  try {
    applyWorkspace(await audioApi.stop(workspaceId.value))
    toast.add({
      title: 'Queued audio tasks stopped',
      description: 'Queued chapters were reset. A chapter already running will finish normally.',
      color: 'success',
      icon: 'lucide:square'
    })
  } catch {
    await refreshWorkspace()
    toast.add({
      title: 'Unable to stop queued audio tasks',
      description: 'The workspace changed while the stop request was applied.',
      color: 'error',
      icon: 'lucide:circle-alert'
    })
  } finally {
    stopping.value = false
  }
}

type WorkspaceUpdatedPayload = {
  workspaceId: string
  taskId?: string
}

useRealtime().onMessage<WorkspaceUpdatedPayload>('workspace.updated', ({ payload }) => {
  if (payload.workspaceId !== workspaceId.value) return
  if (realtimeRefreshTimer) clearTimeout(realtimeRefreshTimer)
  realtimeRefreshTimer = setTimeout(() => {
    realtimeRefreshTimer = undefined
    void refreshWorkspace()
  }, 200)
})

onBeforeUnmount(() => {
  if (realtimeRefreshTimer) clearTimeout(realtimeRefreshTimer)
})
</script>

<template>
  <UDashboardPanel
    id="audio-workspace-outline"
    :default-size="40"
    :min-size="30"
    :max-size="55"
    resizable
  >
    <UDashboardNavbar :title="workspace?.title || 'Audio workspace'">
      <template #leading>
        <UDashboardSidebarCollapse />
      </template>
      <template #right>
        <UButton
          label="Audio projects"
          icon="lucide:arrow-left"
          to="/workspaces/audios"
          color="neutral"
          variant="ghost"
          size="sm"
        />
      </template>
    </UDashboardNavbar>

    <div v-if="loading" class="min-h-0 flex-1 space-y-5 overflow-hidden p-5" aria-label="Loading audio workspace">
      <USkeleton class="h-28 rounded-xl" />
      <USkeleton class="h-36 rounded-xl" />
      <USkeleton v-for="index in 5" :key="index" class="h-12 rounded-lg" />
    </div>

    <div v-else-if="error || !workspace" class="flex min-h-0 flex-1 items-center justify-center p-5">
      <UAlert
        class="max-w-md"
        color="error"
        variant="subtle"
        icon="lucide:circle-alert"
        title="Unable to load audio workspace"
        description="Return to audio projects or try again."
        :actions="[{ label: 'Retry', color: 'error', variant: 'soft', onClick: loadWorkspace }]"
      />
    </div>

    <template v-else>
      <UAlert
        v-if="!workspace.sourceAvailable"
        class="m-4 mb-0"
        color="warning"
        variant="subtle"
        icon="lucide:circle-alert"
        title="Selected language unavailable"
        description="The workspace remains available, but its selected novel language can no longer be resolved."
      />
      <WorkspacesAudioProjectOutline
        :workspace="workspace"
        :selected-id="selectedId"
        @select="selectChapter"
        @edit="editOpen = true"
      />
    </template>
  </UDashboardPanel>

  <WorkspacesAudioChapterReader
    v-if="workspace && !isMobile"
    v-model:provider="provider"
    v-model:voice="voice"
    v-model:chapter-index-from="chapterIndexFrom"
    v-model:chapter-index-to="chapterIndexTo"
    v-model:refetch="refetch"
    v-model:force="force"
    :workspace="workspace"
    :chapter="selectedChapter"
    :position="selectedIndex + 1"
    :total="workspace.chapters.length"
    :can-previous="selectedIndex > 0"
    :can-next="selectedIndex >= 0 && selectedIndex < workspace.chapters.length - 1"
    :starting="starting"
    :stopping="stopping"
    @navigate="navigateChapter"
    @start="startWorkspace"
    @stop="stopWorkspace"
  />

  <div v-else-if="!isMobile" class="hidden flex-1 items-center justify-center p-8 lg:flex">
    <UEmpty
      icon="lucide:audio-lines"
      title="Audio chapter"
      description="The selected chapter content will appear here."
      size="xl"
    />
  </div>

  <ClientOnly>
    <USlideover
      v-if="isMobile"
      v-model:open="mobileReaderOpen"
      :close="false"
      :ui="{ content: 'w-full max-w-none' }"
    >
      <template #content>
        <WorkspacesAudioChapterReader
          v-if="workspace && selectedChapter"
          v-model:provider="provider"
          v-model:voice="voice"
          v-model:chapter-index-from="chapterIndexFrom"
          v-model:chapter-index-to="chapterIndexTo"
          v-model:refetch="refetch"
          v-model:force="force"
          mobile
          :workspace="workspace"
          :chapter="selectedChapter"
          :position="selectedIndex + 1"
          :total="workspace.chapters.length"
          :can-previous="selectedIndex > 0"
          :can-next="selectedIndex < workspace.chapters.length - 1"
          :starting="starting"
          :stopping="stopping"
          @close="replaceChapter()"
          @navigate="navigateChapter"
          @start="startWorkspace"
          @stop="stopWorkspace"
        />
      </template>
    </USlideover>
  </ClientOnly>

  <WorkspacesUpdateAudioProjectModal
    v-if="workspace"
    v-model:open="editOpen"
    :workspace="workspace"
    @updated="onUpdated"
  />
</template>
