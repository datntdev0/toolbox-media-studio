<script setup lang="ts">
import type {
  TranslationConfigurationInput,
  TranslationWorkspace
} from '~/types/translation-workspace'
import {
  DEFAULT_TRANSLATION_PROMPT,
  translationProviders
} from '~/types/translation-workspace'

definePageMeta({
  title: 'Translation configuration',
  middleware: ['auth']
})

const route = useRoute()
const router = useRouter()
const toast = useToast()
const saving = ref(false)
const loading = ref(true)
const loadError = ref<unknown>()
const workspaceId = computed(() => String(route.params.id || ''))
const previewChapterId = computed(() => {
  const value = route.query.chapter
  return typeof value === 'string' ? value : ''
})
const workspace = ref<TranslationWorkspace | null>(null)
const defaultProvider = translationProviders[0]!
const configuration = ref<TranslationConfigurationInput>({
  providerId: defaultProvider.id,
  modelId: defaultProvider.models[0]!.id,
  globalPrompt: DEFAULT_TRANSLATION_PROMPT
})

async function loadWorkspace() {
  loading.value = true
  loadError.value = undefined
  try {
    const loadedWorkspace = await useTranslationWorkspaceApi().get(workspaceId.value)
    const novelApi = useNovelWorkspaceApi()
    const novel = await novelApi.getNovel(loadedWorkspace.novelId)
    const hydratedWorkspace = mergeTranslationWorkspaceWithNovel(loadedWorkspace, novel)
    const requestedChapter = novel.chapters.find(chapter =>
      chapter.id === previewChapterId.value
    )

    if (requestedChapter?.contentAvailable) {
      const content = await novelApi.getChapter(loadedWorkspace.novelId, requestedChapter.id)
      const previewChapter = hydratedWorkspace.chapters.find(chapter =>
        chapter.id === requestedChapter.id
      )
      if (previewChapter) {
        previewChapter.originalParagraphs = content.content
          .split(/\n\s*\n/g)
          .map(paragraph => paragraph.trim())
          .filter(Boolean)
      }
    }

    workspace.value = hydratedWorkspace
    if (hydratedWorkspace.configuration) {
      configuration.value = {
        providerId: hydratedWorkspace.configuration.providerId,
        modelId: hydratedWorkspace.configuration.modelId,
        globalPrompt: hydratedWorkspace.configuration.globalPrompt
      }
    }
  } catch (cause) {
    loadError.value = cause
    workspace.value = null
  } finally {
    loading.value = false
  }
}

onMounted(() => void loadWorkspace())

useHead(() => ({
  title: workspace.value
    ? `Configure ${workspace.value.name}`
    : 'Translation configuration'
}))

async function backToWorkspace() {
  await router.push({
    path: `/translations/${workspaceId.value}`,
    query: route.query
  })
}

async function save() {
  if (!workspace.value) return
  saving.value = true
  try {
    const updated = await useTranslationWorkspaceApi().update(workspace.value.id, {
      name: workspace.value.name,
      novelId: workspace.value.novelId,
      targetLanguage: workspace.value.targetLanguage.code,
      configuration: configuration.value,
      etag: workspace.value.etag
    })
    workspace.value = normalizeTranslationWorkspace(updated)
    toast.add({
      title: 'Configuration saved',
      description: 'The AI provider, model, and translation prompt are ready to use.',
      color: 'success',
      icon: 'lucide:circle-check'
    })
    await backToWorkspace()
  } catch (cause) {
    toast.add({
      title: 'Unable to save configuration',
      description: cause instanceof Error ? cause.message : 'Please try again.',
      color: 'error',
      icon: 'lucide:circle-alert'
    })
  } finally {
    saving.value = false
  }
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
            :disabled="!workspace"
            :loading="saving"
            @click="save"
          />
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <USkeleton v-if="loading" class="h-96 rounded-xl" />

      <TranslationsConfigurationPreview
        v-else-if="workspace"
        v-model:configuration="configuration"
        :workspace="workspace"
        :preview-chapter-id="previewChapterId"
      />
    </template>
  </UDashboardPanel>
</template>
