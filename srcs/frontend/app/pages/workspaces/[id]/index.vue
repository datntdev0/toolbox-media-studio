<script setup lang="ts">
import type {
  TranslationChapter,
  TranslationWorkspace
} from '~/types/translation-workspace'
import type { NovelChapterContent } from '~/types/novel-workspace'

definePageMeta({
  title: 'Translation workspace',
  middleware: ['auth']
})

const route = useRoute()
const router = useRouter()
const toast = useToast()
const loading = ref(true)
const loadError = ref<unknown>()
const workspace = ref<TranslationWorkspace | null>(null)
const translationChapterIds = ref(new Set<string>())
const sourceContentChapterIds = ref(new Set<string>())
const originalLoading = ref(false)
const originalLoadError = ref(false)
const chaptersOpen = ref(false)
const rangeStart = ref('')
const rangeEnd = ref('')
const comparisonRef = ref<{
  confirmDiscard: () => Promise<boolean>
  focusChapters: () => void
} | null>(null)

const workspaceId = computed(() => String(route.params.id || ''))

async function loadWorkspace() {
  loading.value = true
  loadError.value = undefined
  try {
    const loadedWorkspace = await useTranslationWorkspaceApi().get(workspaceId.value)
    const novel = await useNovelWorkspaceApi().getNovel(loadedWorkspace.novelId)
    const translationChapters = new Map(
      loadedWorkspace.chapters.map(chapter => [chapter.id, chapter])
    )

    translationChapterIds.value = new Set(translationChapters.keys())
    sourceContentChapterIds.value = new Set(
      novel.chapters
        .filter(chapter => chapter.contentAvailable)
        .map(chapter => chapter.id)
    )
    loadedWorkspace.chapters = novel.chapters.map((sourceChapter, index) => {
      const translationChapter = translationChapters.get(sourceChapter.id)
      return {
        id: sourceChapter.id,
        number: sourceChapter.chapterNumber ?? index + 1,
        title: sourceChapter.title,
        status: translationChapter?.status ?? 'not_started',
        originalParagraphs: [],
        translatedParagraphs: translationChapter?.translatedParagraphs ?? []
      }
    })
    workspace.value = loadedWorkspace
  } catch (cause) {
    loadError.value = cause
    workspace.value = null
  } finally {
    loading.value = false
  }
}

onMounted(() => void loadWorkspace())

const selectedChapterId = computed(() => {
  const value = route.query.chapter
  return typeof value === 'string' ? value : ''
})
const selectedIndex = computed(() =>
  workspace.value?.chapters.findIndex(chapter => chapter.id === selectedChapterId.value) ?? -1
)
const selectedChapter = computed(() =>
  selectedIndex.value >= 0
    ? workspace.value?.chapters[selectedIndex.value] || null
    : workspace.value?.chapters[0] || null
)
const translationAvailable = computed(() =>
  selectedChapter.value
    ? translationChapterIds.value.has(selectedChapter.value.id)
    : false
)

function applyOriginalContent(chapter: TranslationChapter, content: NovelChapterContent) {
  chapter.originalParagraphs = content.content
    .split(/\n\s*\n/g)
    .map(paragraph => paragraph.trim())
    .filter(Boolean)
}

watch(() => selectedChapter.value?.id, async (chapterId) => {
  originalLoading.value = false
  originalLoadError.value = false
  if (!chapterId || !workspace.value) return

  const chapter = workspace.value.chapters.find(item => item.id === chapterId)
  if (
    !chapter
    || chapter.originalParagraphs.length
    || !sourceContentChapterIds.value.has(chapterId)
  ) return

  originalLoading.value = true
  try {
    const content = await useNovelWorkspaceApi().getChapter(workspace.value.novelId, chapterId)
    if (selectedChapter.value?.id === chapterId) {
      applyOriginalContent(chapter, content)
    }
  } catch {
    if (selectedChapter.value?.id === chapterId) {
      originalLoadError.value = true
    }
  } finally {
    if (selectedChapter.value?.id === chapterId) {
      originalLoading.value = false
    }
  }
}, { immediate: true })

useHead(() => ({
  title: workspace.value
    ? `${workspace.value.name} · ${workspace.value.targetLanguage.label}`
    : 'Translation workspace'
}))

watch(workspace, (value) => {
  if (!value?.chapters.length) return
  rangeStart.value = value.chapters[0]!.id
  rangeEnd.value = value.chapters[value.chapters.length - 1]!.id
  if (!selectedChapterId.value) {
    void router.replace({
      query: { ...route.query, chapter: value.chapters[0]!.id }
    })
  }
}, { immediate: true })

watch(chaptersOpen, (value, previous) => {
  if (!value && previous) {
    void nextTick(() => comparisonRef.value?.focusChapters())
  }
})

onBeforeRouteLeave(async () => {
  return comparisonRef.value
    ? await comparisonRef.value.confirmDiscard()
    : true
})

async function selectChapter(chapter: TranslationChapter) {
  if (chapter.id === selectedChapterId.value) {
    chaptersOpen.value = false
    return
  }
  if (comparisonRef.value && !await comparisonRef.value.confirmDiscard()) return
  await router.push({
    query: { ...route.query, chapter: chapter.id }
  })
  chaptersOpen.value = false
}

async function navigateChapter(offset: number) {
  if (!workspace.value || selectedIndex.value < 0) return
  const chapter = workspace.value.chapters[selectedIndex.value + offset]
  if (chapter) await selectChapter(chapter)
}

async function openConfiguration() {
  await router.push({
    path: `/workspaces/${workspaceId.value}/configuration`,
    query: route.query
  })
}

function showPrototypeAction(action: 'start' | 'stop') {
  toast.add(action === 'start'
    ? {
        title: 'Static translation run',
        description: 'The selected range is ready for review; no background job was started.',
        color: 'neutral',
        icon: 'lucide:play'
      }
    : {
        title: 'Static queued state',
        description: 'No queued chapters were changed in this prototype.',
        color: 'neutral',
        icon: 'lucide:square'
      })
}
</script>

<template>
  <UDashboardPanel id="translation-workspace">
    <UDashboardNavbar :title="workspace?.name || 'Translation workspace'">
      <template #leading>
        <UDashboardSidebarCollapse />
      </template>
      <template #right>
        <UButton
          label="Workspaces"
          icon="lucide:arrow-left"
          to="/workspaces"
          color="neutral"
          variant="ghost"
          size="sm"
          class="hidden sm:inline-flex"
        />
      </template>
    </UDashboardNavbar>

    <div v-if="loading" class="p-6">
      <USkeleton class="h-64 rounded-xl" />
    </div>

    <UAlert
      v-else-if="loadError"
      class="m-6"
      color="error"
      variant="subtle"
      icon="lucide:circle-alert"
      title="Unable to load workspace"
      description="The workspace could not be found or the service is unavailable."
      :actions="[{
        label: 'Back to Workspaces',
        icon: 'lucide:arrow-left',
        to: '/workspaces'
      }]"
    />

    <UDashboardToolbar
      v-if="workspace"
      :ui="{
        root: 'items-start gap-6 py-5',
        left: 'min-w-0 flex-1 self-stretch items-start',
        right: 'min-w-0 flex-1 self-stretch items-start'
      }"
    >
      <template #left>
        <section aria-labelledby="novel-info-heading" class="w-full">
          <div class="mb-3 flex items-center justify-between">
            <h2 id="novel-info-heading" class="font-semibold text-highlighted">
              Novel information
            </h2>
            <UButton
              label="View novel"
              icon="lucide:arrow-up-right"
              size="sm"
              color="neutral"
              variant="ghost"
              :to="`/library/novels/${workspace.novelId}`"
            />
          </div>
          <div class="flex gap-4">
            <div class="flex h-32 w-22 shrink-0 items-center justify-center overflow-hidden rounded-lg bg-primary/10">
              <img
                v-if="workspace.coverImageUrl"
                :src="workspace.coverImageUrl"
                :alt="`${workspace.novelTitle} cover`"
                class="size-full object-cover"
              >
              <UIcon v-else name="lucide:book-open" class="size-7 text-primary/70" />
            </div>
            <div class="min-w-0 flex-1 space-y-2">
              <h1 class="text-lg font-semibold text-highlighted">
                {{ workspace.novelTitle }}
              </h1>
              <dl class="grid grid-cols-3 gap-x-3 gap-y-2 text-sm">
                <div>
                  <dt class="text-xs text-muted">
                    Source language
                  </dt>
                  <dd class="truncate text-toned">
                    {{ workspace.sourceLanguage.label }}
                  </dd>
                </div>
                <div>
                  <dt class="text-xs text-muted">
                    Target language
                  </dt>
                  <dd class="truncate text-toned">
                    {{ workspace.targetLanguage.label }}
                  </dd>
                </div>
                <div>
                  <dt class="text-xs text-muted">
                    Chapters
                  </dt>
                  <dd class="text-toned">
                    {{ workspace.progress.total }}
                  </dd>
                </div>
              </dl>
            </div>
          </div>
        </section>
      </template>

      <template #right>
        <WorkspacesRunToolbar
          v-model:range-start="rangeStart"
          v-model:range-end="rangeEnd"
          :workspace="workspace"
          @configure="openConfiguration"
          @start="showPrototypeAction('start')"
          @stop="showPrototypeAction('stop')"
        />
      </template>
    </UDashboardToolbar>

    <WorkspacesComparisonReader
      v-if="workspace && selectedChapter"
      ref="comparisonRef"
      :workspace="workspace"
      :chapter="selectedChapter"
      :translation-available="translationAvailable"
      :original-loading="originalLoading"
      :original-load-error="originalLoadError"
      :can-previous="selectedIndex > 0"
      :can-next="selectedIndex < workspace.chapters.length - 1"
      @chapters="chaptersOpen = true"
      @configure="openConfiguration"
      @navigate="navigateChapter"
    />
  </UDashboardPanel>

  <WorkspacesChapterSlideover
    v-if="workspace"
    v-model:open="chaptersOpen"
    :workspace="workspace"
    :selected-id="selectedChapter?.id || null"
    @select="selectChapter"
  />
</template>
