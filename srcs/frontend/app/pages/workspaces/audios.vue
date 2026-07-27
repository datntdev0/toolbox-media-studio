<script setup lang="ts">
import type { NavigationMenuItem } from '@nuxt/ui'

definePageMeta({ title: 'Audio workspaces', middleware: ['auth'] })

const links = [
  { label: 'Translations', icon: 'lucide:languages', to: '/workspaces' },
  { label: 'Audios', icon: 'lucide:audio-lines', to: '/workspaces/audios' },
  { label: 'Videos', icon: 'lucide:clapperboard', to: '/workspaces/videos' }
] satisfies NavigationMenuItem[]
</script>

<template>
  <UDashboardPanel id="audio-workspaces">
    <template #header>
      <UDashboardNavbar title="Workspaces">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
      </UDashboardNavbar>
      <UDashboardToolbar>
        <UNavigationMenu :items="links" highlight class="-mx-1 flex-1" />
      </UDashboardToolbar>
    </template>
    <template #body>
      <UEmpty
        icon="lucide:audio-lines"
        title="Audio workspaces are coming soon"
        description="Audio project tools will appear here."
        size="xl"
      />
    </template>
  </UDashboardPanel>
</template>
