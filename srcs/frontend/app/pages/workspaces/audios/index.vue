<script setup lang="ts">
import type { NavigationMenuItem } from '@nuxt/ui'
import type { NovelResponse } from '~~/shared/api-services/srv-core.client'
import type { AudioWorkspace } from '~/types/audio-workspace'
import { resolveLanguage } from '~/constants/supported-languages'

definePageMeta({ title: 'Audio workspaces', middleware: ['auth'] })

const links = [
  { label: 'Audios', icon: 'lucide:audio-lines', to: '/workspaces/audios' },
  { label: 'Videos', icon: 'lucide:clapperboard', to: '/workspaces/videos' }
] satisfies NavigationMenuItem[]

const search = ref('')
const createOpen = ref(false)
const workspaces = ref<AudioWorkspace[]>([])
const novels = ref<NovelResponse[]>([])
const loading = ref(true)
const error = ref<unknown>()
const editingWorkspace = ref<AudioWorkspace | null>(null)
const deletingWorkspaceId = ref<string | null>(null)
const toast = useToast()
const confirm = useConfirmDialog()

const editOpen = computed({
  get: () => Boolean(editingWorkspace.value),
  set: (value: boolean) => {
    if (!value) editingWorkspace.value = null
  }
})
const filteredWorkspaces = computed(() => {
  const query = search.value.trim().toLowerCase()
  if (!query) return workspaces.value
  return workspaces.value.filter(workspace => [
    workspace.title,
    workspace.novel?.title,
    workspace.language,
    resolveLanguage(workspace.language).label,
    workspace.sourceType
  ].filter(Boolean).some(value => String(value).toLowerCase().includes(query)))
})

async function loadWorkspaces() {
  loading.value = true
  error.value = undefined
  try {
    const { novels: novelsClient } = useApiClient()
    const [workspaceItems, novelPage] = await Promise.all([
      useAudioWorkspaceApi().list(),
      novelsClient.list_novels(100, undefined)
    ])
    workspaces.value = workspaceItems
    novels.value = novelPage.items || []
  } catch (cause) {
    error.value = cause
  } finally {
    loading.value = false
  }
}

onMounted(() => void loadWorkspaces())

function upsertWorkspace(workspace: AudioWorkspace) {
  workspaces.value = [
    workspace,
    ...workspaces.value.filter(item => item.id !== workspace.id)
  ]
}

async function deleteWorkspace(workspace: AudioWorkspace) {
  const confirmed = await confirm({
    title: 'Delete audio project',
    description: `Delete “${workspace.title}”? This action cannot be undone from the app.`,
    confirmLabel: 'Delete project',
    confirmColor: 'error'
  })
  if (!confirmed) return

  deletingWorkspaceId.value = workspace.id
  try {
    await useAudioWorkspaceApi().delete(workspace.id)
    workspaces.value = workspaces.value.filter(item => item.id !== workspace.id)
    toast.add({
      title: 'Audio project deleted',
      description: `“${workspace.title}” has been removed.`,
      color: 'success'
    })
  } catch (cause) {
    toast.add({
      title: 'Unable to delete project',
      description: cause instanceof Error ? cause.message : 'Please try again.',
      color: 'error'
    })
  } finally {
    deletingWorkspaceId.value = null
  }
}
</script>

<template>
  <UDashboardPanel id="audio-workspaces">
    <template #header>
      <UDashboardNavbar title="Workspaces">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
        <template #right>
          <UButton label="New Project" icon="lucide:plus" @click="createOpen = true" />
        </template>
      </UDashboardNavbar>
      <UDashboardToolbar>
        <UNavigationMenu :items="links" highlight class="-mx-1 flex-1" />
      </UDashboardToolbar>
    </template>

    <template #body>
      <div class="flex flex-col gap-6">
        <UPageCard
          title="Audio projects"
          description="Prepare original or translated novel chapters for text-to-speech production."
          variant="naked"
          class="mb-0"
        />

        <div class="flex flex-col gap-3 border-b border-default pb-4 sm:flex-row sm:items-center sm:justify-between">
          <UInput
            v-model="search"
            icon="lucide:search"
            placeholder="Search projects..."
            class="w-full sm:max-w-sm"
          />
          <p class="text-sm text-muted" aria-live="polite">
            {{ filteredWorkspaces.length }}
            {{ filteredWorkspaces.length === 1 ? 'project' : 'projects' }}
          </p>
        </div>

        <UAlert
          v-if="error"
          color="error"
          variant="subtle"
          icon="lucide:circle-alert"
          title="Unable to load audio projects"
          description="Please check the workspace service and try again."
          :actions="[{ label: 'Retry', icon: 'lucide:refresh-cw', onClick: loadWorkspaces }]"
        />

        <UPageGrid v-else-if="loading" class="grid-cols-1 gap-4 xl:grid-cols-2">
          <USkeleton v-for="index in 4" :key="index" class="h-48 rounded-xl" />
        </UPageGrid>

        <UPageGrid
          v-else-if="filteredWorkspaces.length"
          class="grid-cols-1 gap-4 xl:grid-cols-2"
        >
          <WorkspacesAudioProjectCard
            v-for="workspace in filteredWorkspaces"
            :key="workspace.id"
            :workspace="workspace"
            :class="{ 'pointer-events-none opacity-60': deletingWorkspaceId === workspace.id }"
            @edit="editingWorkspace = $event"
            @delete="deleteWorkspace"
          />
        </UPageGrid>

        <UEmpty
          v-else
          icon="lucide:audio-lines"
          :title="search ? 'No projects found' : 'No audio projects yet'"
          :description="search
            ? 'Try a project title, novel, language, or source type.'
            : 'Audio projects begin with a novel already stored in your Library.'"
          size="xl"
          :actions="search ? undefined : [{
            label: 'New Project',
            icon: 'lucide:plus',
            onClick: () => createOpen = true
          }, {
            label: 'Open Library',
            icon: 'lucide:library-big',
            color: 'neutral',
            variant: 'soft',
            to: '/library/novels'
          }]"
        />
      </div>
    </template>
  </UDashboardPanel>

  <WorkspacesCreateAudioProjectModal
    v-model:open="createOpen"
    :novels="novels"
    @created="upsertWorkspace"
  />

  <WorkspacesUpdateAudioProjectModal
    v-if="editingWorkspace"
    v-model:open="editOpen"
    :workspace="editingWorkspace"
    @updated="upsertWorkspace"
  />
</template>
