<script setup lang="ts">
import type { NavigationMenuItem } from '@nuxt/ui'
import { translationWorkspaces } from '~/utils/translation-workspace-fixtures'

definePageMeta({
  title: 'Workspaces',
  middleware: ['auth']
})

useHead({ title: 'Workspaces' })

const search = ref('')
const createOpen = ref(false)

const links = [{
  label: 'Translations',
  icon: 'lucide:languages',
  to: '/workspaces'
}, {
  label: 'Audios',
  icon: 'lucide:audio-lines',
  to: '/workspaces/audios'
}, {
  label: 'Videos',
  icon: 'lucide:clapperboard',
  to: '/workspaces/videos'
}] satisfies NavigationMenuItem[]

const filteredWorkspaces = computed(() => {
  const query = search.value.trim().toLowerCase()
  if (!query) return translationWorkspaces

  return translationWorkspaces.filter((workspace) => {
    const configuration = workspace.configuration
    return [
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
</script>

<template>
  <UDashboardPanel id="workspaces">
    <template #header>
      <UDashboardNavbar title="Workspaces">
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

      <UDashboardToolbar>
        <UNavigationMenu :items="links" highlight class="-mx-1 flex-1" />
      </UDashboardToolbar>
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

        <UPageGrid
          v-if="filteredWorkspaces.length"
          class="grid-cols-1 gap-4 sm:grid-cols-1 lg:grid-cols-1 xl:grid-cols-2"
        >
          <WorkspacesWorkspaceCard
            v-for="workspace in filteredWorkspaces"
            :key="workspace.id"
            :workspace="workspace"
          />
        </UPageGrid>

        <UEmpty
          v-else
          icon="lucide:languages"
          :title="search ? 'No projects found' : 'No translation projects yet'"
          :description="search
            ? 'Try a novel title, provider, model, or target language.'
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

  <WorkspacesCreateProjectModal
    v-model:open="createOpen"
    :workspaces="translationWorkspaces"
  />
</template>
