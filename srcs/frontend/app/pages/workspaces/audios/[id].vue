<script setup lang="ts">
import { breakpointsTailwind } from '@vueuse/core'
import type { AudioWorkspace, AudioWorkspaceChapter } from '~/types/audio-workspace'

definePageMeta({ title: 'Audio workspace', middleware: ['auth'] })

const route = useRoute()
const router = useRouter()
const breakpoints = useBreakpoints(breakpointsTailwind)
const isMobile = breakpoints.smaller('lg')
const workspace = ref<AudioWorkspace | null>(null)
const loading = ref(true)
const error = ref(false)
const editOpen = ref(false)
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
    workspace.value = await useAudioWorkspaceApi().get(workspaceId.value)
    if (!isMobile.value || selectedId.value) await selectDefaultChapter()
  } catch {
    workspace.value = null
    error.value = true
  } finally {
    loading.value = false
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
    :workspace="workspace"
    :chapter="selectedChapter"
    :position="selectedIndex + 1"
    :total="workspace.chapters.length"
    :can-previous="selectedIndex > 0"
    :can-next="selectedIndex >= 0 && selectedIndex < workspace.chapters.length - 1"
    @navigate="navigateChapter"
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
          mobile
          :workspace="workspace"
          :chapter="selectedChapter"
          :position="selectedIndex + 1"
          :total="workspace.chapters.length"
          :can-previous="selectedIndex > 0"
          :can-next="selectedIndex < workspace.chapters.length - 1"
          @close="replaceChapter()"
          @navigate="navigateChapter"
        />
      </template>
    </USlideover>
  </ClientOnly>

  <WorkspacesEditAudioProjectModal
    v-if="workspace"
    v-model:open="editOpen"
    :workspace="workspace"
    @updated="onUpdated"
  />
</template>
