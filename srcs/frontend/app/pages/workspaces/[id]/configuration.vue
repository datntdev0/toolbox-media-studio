<script setup lang="ts">
import type { TranslationWorkspace } from '~/types/translation-workspace'

definePageMeta({
  title: 'Translation configuration',
  middleware: ['auth']
})

const route = useRoute()
const router = useRouter()
const toast = useToast()
const previewValid = ref(true)
const loading = ref(true)
const loadError = ref<unknown>()
const workspaceId = computed(() => String(route.params.id || ''))
const previewChapterId = computed(() => {
  const value = route.query.chapter
  return typeof value === 'string' ? value : ''
})
const workspace = ref<TranslationWorkspace | null>(null)

async function loadWorkspace() {
  loading.value = true
  loadError.value = undefined
  try {
    const loadedWorkspace = await useTranslationWorkspaceApi().get(workspaceId.value)
    const novelApi = useNovelWorkspaceApi()
    const novel = await novelApi.getNovel(loadedWorkspace.novelId)
    const requestedChapter = novel.chapters.find(chapter =>
      chapter.id === previewChapterId.value
    )

    loadedWorkspace.chapters = novel.chapters.map((chapter, index) => ({
      id: chapter.id,
      number: chapter.chapterNumber ?? index + 1,
      title: chapter.title,
      status: 'not_started',
      originalParagraphs: [],
      translatedParagraphs: []
    }))

    if (requestedChapter?.contentAvailable) {
      const content = await novelApi.getChapter(loadedWorkspace.novelId, requestedChapter.id)
      const previewChapter = loadedWorkspace.chapters.find(chapter =>
        chapter.id === requestedChapter.id
      )
      if (previewChapter) {
        previewChapter.originalParagraphs = content.content
          .split(/\n\s*\n/g)
          .map(paragraph => paragraph.trim())
          .filter(Boolean)
      }
    }

    workspace.value = loadedWorkspace
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
      <USkeleton v-if="loading" class="h-96 rounded-xl" />

      <WorkspacesConfigurationPreview
        v-else-if="workspace"
        v-model:preview-valid="previewValid"
        :workspace="workspace"
        :preview-chapter-id="previewChapterId"
      />
    </template>
  </UDashboardPanel>
</template>
