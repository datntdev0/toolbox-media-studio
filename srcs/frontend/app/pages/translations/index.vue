<script setup lang="ts">
import type { NovelResponse } from '~~/shared/api-services/srv-core.client'
import type {
  TranslationApiRecord,
  TranslationWorkspace
} from '~/types/translation-workspace'
import { normalizeTranslationWorkspace } from '~/composables/useTranslationWorkspaceApi'

definePageMeta({
  title: 'Translations',
  middleware: ['auth']
})

useHead({ title: 'Translations' })

const search = ref('')
const createOpen = ref(false)
const workspaces = ref<TranslationWorkspace[]>([])
const novels = ref<NovelResponse[]>([])
const loading = ref(true)
const error = ref<unknown>()
const editingWorkspace = ref<TranslationWorkspace | null>(null)
const deletingWorkspaceId = ref<string | null>(null)
const toast = useToast()
const confirm = useConfirmDialog()

const editOpen = computed({
  get: () => !!editingWorkspace.value,
  set: (value: boolean) => {
    if (!value) editingWorkspace.value = null
  }
})

const filteredWorkspaces = computed(() => {
  const query = search.value.trim().toLowerCase()
  if (!query) return workspaces.value

  return workspaces.value.filter((workspace) => {
    const configuration = workspace.configuration
    return [
      workspace.name,
      workspace.novelTitle,
      workspace.targetLanguage.label,
      workspace.targetLanguage.nativeLabel,
      configuration?.providerName,
      configuration?.modelName
    ]
      .filter(Boolean)
      .some(value => String(value).toLowerCase().includes(query))
  })
})

async function loadWorkspaces() {
  loading.value = true
  error.value = undefined
  try {
    const { novels: novelClient } = useApiClient()
    const [workspaceItems, novelPage] = await Promise.all([
      useTranslationWorkspaceApi().list(),
      novelClient.list_novels(100, undefined)
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

function upsertWorkspace(record: TranslationApiRecord) {
  const workspace = normalizeTranslationWorkspace(record)
  workspaces.value = [
    workspace,
    ...workspaces.value.filter(item => item.id !== workspace.id)
  ]
}

async function deleteWorkspace(workspace: TranslationWorkspace) {
  const confirmed = await confirm({
    title: 'Delete workspace',
    description: `Delete “${workspace.name}”? This action cannot be undone from the app.`,
    confirmLabel: 'Delete workspace',
    confirmColor: 'error'
  })
  if (!confirmed) return

  deletingWorkspaceId.value = workspace.id
  try {
    await useTranslationWorkspaceApi().delete(workspace.id)
    workspaces.value = workspaces.value.filter(item => item.id !== workspace.id)
    toast.add({
      title: 'Workspace deleted',
      description: `“${workspace.name}” has been removed.`,
      color: 'success'
    })
  } catch (cause) {
    toast.add({
      title: 'Unable to delete workspace',
      description: cause instanceof Error ? cause.message : 'Please try again.',
      color: 'error'
    })
  } finally {
    deletingWorkspaceId.value = null
  }
}
</script>

<template>
  <UDashboardPanel id="translations">
    <template #header>
      <UDashboardNavbar title="Translations">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
        <template #right>
          <UButton
            label="New Project"
            icon="lucide:plus"
            @click="createOpen = true"
          />
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <div class="flex flex-col gap-6">
        <UPageCard
          title="Translation projects"
          description="Compare source chapters, configure an AI model, and follow translation progress for every target language."
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
          title="Unable to load workspaces"
          description="Please check the workspace service and try again."
          :actions="[{ label: 'Retry', icon: 'lucide:refresh-cw', onClick: loadWorkspaces }]"
        />

        <UPageGrid
          v-else-if="loading"
          class="grid-cols-1 gap-4 xl:grid-cols-2"
        >
          <USkeleton v-for="index in 4" :key="index" class="h-48 rounded-xl" />
        </UPageGrid>

        <UPageGrid
          v-else-if="filteredWorkspaces.length"
          class="grid-cols-1 gap-4 sm:grid-cols-1 lg:grid-cols-1 xl:grid-cols-2"
        >
          <TranslationsListItemCard
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
          icon="lucide:languages"
          :title="search ? 'No projects found' : 'No translation projects yet'"
          :description="search
            ? 'Try a workspace name, novel title, provider, model, or target language.'
            : 'Translation projects begin with a novel already stored in your Library.'"
          size="xl"
          :actions="search
            ? undefined
            : [{
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

  <TranslationsCreateModal
    v-model:open="createOpen"
    :novels="novels"
    @created="upsertWorkspace"
  />

  <TranslationsUpdateModal
    v-if="editingWorkspace"
    v-model:open="editOpen"
    :workspace="editingWorkspace"
    :novels="novels"
    @updated="upsertWorkspace"
  />
</template>
