<script setup lang="ts">
import type { TranslationWorkspace } from '~/types/translation-workspace'
import {
  findTranslationWorkspace,
  translationLanguages,
  translationNovels,
  translationWorkspaces
} from '~/utils/translation-workspace-fixtures'

definePageMeta({
  title: 'Translation configuration',
  middleware: ['auth']
})

const route = useRoute()
const router = useRouter()
const toast = useToast()
const previewValid = ref(true)
const workspaceId = computed(() => String(route.params.id || ''))

const workspace = computed<TranslationWorkspace | null>(() => {
  const existing = findTranslationWorkspace(workspaceId.value)
  if (existing) return existing
  if (workspaceId.value !== 'prototype-new') return null

  const novelId = typeof route.query.novel === 'string' ? route.query.novel : ''
  const languageCode = typeof route.query.language === 'string' ? route.query.language : ''
  const novel = translationNovels.find(item => item.id === novelId) || translationNovels[3]!
  const target = translationLanguages.find(language => language.code === languageCode)
    || translationLanguages[3]!
  const template = translationWorkspaces.find(item => item.status === 'needs_setup')!

  return {
    ...template,
    id: 'prototype-new',
    novelId: novel.id,
    novelTitle: novel.title,
    coverImageUrl: novel.coverImageUrl,
    sourceLanguage: novel.sourceLanguage,
    targetLanguage: target,
    progress: { ...template.progress, total: novel.chapterCount },
    chapters: template.chapters.slice(0, novel.chapterCount)
  }
})

useHead(() => ({
  title: workspace.value
    ? `Configure ${workspace.value.novelTitle}`
    : 'Translation configuration'
}))

async function backToWorkspace() {
  await router.push({
    path: `/workspaces/${workspaceId.value}`,
    query: route.query
  })
}

async function save() {
  if (!previewValid.value) return
  toast.add({
    title: 'Configuration reviewed',
    description: 'This prototype does not persist provider or prompt changes.',
    color: 'success',
    icon: 'lucide:circle-check'
  })
  await backToWorkspace()
}
</script>

<template>
  <UDashboardPanel id="translation-configuration">
    <template #header>
      <UDashboardNavbar title="Translation configuration">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
        <template #right>
          <UButton
            label="Back"
            icon="lucide:arrow-left"
            color="neutral"
            variant="ghost"
            @click="backToWorkspace"
          />
          <UButton
            label="Save configuration"
            icon="lucide:save"
            :disabled="!previewValid || !workspace"
            @click="save"
          />
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <div v-if="workspace">
        <WorkspacesConfigurationPreview
          v-model:preview-valid="previewValid"
          :workspace="workspace"
        />
      </div>

      <UAlert
        v-else
        class="mx-auto max-w-lg"
        color="error"
        variant="subtle"
        icon="lucide:circle-alert"
        title="Workspace not found"
        description="This prototype workspace does not exist."
        :actions="[{
          label: 'Back to Workspaces',
          icon: 'lucide:arrow-left',
          to: '/workspaces'
        }]"
      />
    </template>
  </UDashboardPanel>
</template>
