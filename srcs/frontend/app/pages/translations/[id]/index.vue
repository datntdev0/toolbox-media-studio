<script setup lang="ts">
import type {
  TranslationChapter,
  TranslationWorkspace
} from '~/types/translation-workspace'
import type {
  NovelChapterContent,
  NovelWorkspace
} from '~/types/novel-workspace'

definePageMeta({
  title: 'Translation workspace',
  middleware: ['auth']
})

const route = useRoute()
const router = useRouter()
const toast = useToast()
const translationApi = useTranslationWorkspaceApi()
const novelApi = useNovelWorkspaceApi()
const loading = ref(true)
const loadError = ref<unknown>()
const workspace = ref<TranslationWorkspace | null>(null)
const novelWorkspace = ref<NovelWorkspace | null>(null)
const originalLoading = ref(false)
const originalLoadError = ref(false)
const translationLoading = ref(false)
const translationLoadError = ref(false)
const starting = ref(false)
const stopping = ref(false)
const chaptersOpen = ref(false)
const rangeStart = ref('')
const rangeEnd = ref('')
const refetch = ref(false)
const force = ref(false)
const comparisonRef = ref<{
  confirmDiscard: () => Promise<boolean>
  focusChapters: () => void
} | null>(null)
let realtimeRefreshTimer: ReturnType<typeof setTimeout> | undefined

const workspaceId = computed(() => String(route.params.id || ''))

function applyWorkspace(
  nextWorkspace: TranslationWorkspace,
  novel: NovelWorkspace
) {
  const mergedWorkspace = mergeTranslationWorkspaceWithNovel(nextWorkspace, novel)
  const currentChapters = new Map(
    (workspace.value?.chapters || []).map(chapter => [chapter.id, chapter])
  )

  novelWorkspace.value = novel

  mergedWorkspace.chapters = mergedWorkspace.chapters.map((chapter) => {
    const current = currentChapters.get(chapter.id)
    const sourceBecameUpdated = chapter.sourceUpdated && !current?.sourceUpdated
    return {
      ...chapter,
      originalParagraphs: sourceBecameUpdated
        ? []
        : current?.originalParagraphs || [],
      translatedParagraphs: chapter.resultAvailable
        ? current?.translatedParagraphs || []
        : [],
      translatedTitle: chapter.resultAvailable
        ? current?.translatedTitle || null
        : null
    }
  })
  workspace.value = mergedWorkspace

  const availableChapters = mergedWorkspace.chapters.filter(
    chapter => chapter.contentAvailable && !chapter.sourceRemoved
  )
  if (!availableChapters.some(chapter => chapter.id === rangeStart.value)) {
    rangeStart.value = availableChapters[0]?.id || ''
  }
  if (!availableChapters.some(chapter => chapter.id === rangeEnd.value)) {
    rangeEnd.value = availableChapters.at(-1)?.id || ''
  }

  const selectedExists = mergedWorkspace.chapters.some(
    chapter => chapter.id === selectedChapterId.value
  )
  if ((!selectedChapterId.value || !selectedExists) && mergedWorkspace.chapters[0]) {
    void router.replace({
      query: { ...route.query, chapter: mergedWorkspace.chapters[0].id }
    })
  }
}

async function hydrateWorkspace(nextWorkspace: TranslationWorkspace) {
  try {
    const novel = await novelApi.getNovel(nextWorkspace.novelId)
    applyWorkspace(nextWorkspace, novel)
  } catch (cause) {
    const currentNovel = novelWorkspace.value
    if (!currentNovel || currentNovel.id !== nextWorkspace.novelId) throw cause
    applyWorkspace(nextWorkspace, currentNovel)
  }
}

async function loadWorkspace() {
  loading.value = true
  loadError.value = undefined
  try {
    const loadedWorkspace = await translationApi.get(workspaceId.value)
    await hydrateWorkspace(loadedWorkspace)
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
  Boolean(selectedChapter.value?.resultAvailable)
)

function applyOriginalContent(chapter: TranslationChapter, content: NovelChapterContent) {
  chapter.originalParagraphs = content.content
    .split(/\n\s*\n/g)
    .map(paragraph => paragraph.trim())
    .filter(Boolean)
}

watch([
  () => selectedChapter.value?.id,
  () => selectedChapter.value?.sourceUpdated,
  () => selectedChapter.value?.sourceRemoved
], async ([chapterId]) => {
  originalLoading.value = false
  originalLoadError.value = false
  if (!chapterId || !workspace.value) return

  const chapter = workspace.value.chapters.find(item => item.id === chapterId)
  if (
    !chapter
    || chapter.originalParagraphs.length
    || !chapter.contentAvailable
    || chapter.sourceRemoved
  ) return

  originalLoading.value = true
  try {
    const content = await novelApi.getChapter(workspace.value.novelId, chapterId)
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

watch([
  () => selectedChapter.value?.id,
  () => selectedChapter.value?.resultAvailable,
  () => selectedChapter.value?.status
], async ([chapterId, resultAvailable]) => {
  translationLoading.value = false
  translationLoadError.value = false
  if (!chapterId || !resultAvailable || !workspace.value) return

  const chapter = workspace.value.chapters.find(item => item.id === chapterId)
  if (!chapter) return

  translationLoading.value = true
  try {
    const result = await translationApi.getResult(workspaceId.value, chapterId)
    if (selectedChapter.value?.id === chapterId) {
      chapter.translatedParagraphs = result.content
      chapter.translatedTitle = result.title
    }
  } catch {
    if (selectedChapter.value?.id === chapterId) {
      translationLoadError.value = true
    }
  } finally {
    if (selectedChapter.value?.id === chapterId) {
      translationLoading.value = false
    }
  }
}, { immediate: true })

useHead(() => ({
  title: workspace.value
    ? `${workspace.value.name} · ${workspace.value.targetLanguage.label}`
    : 'Translation workspace'
}))

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
    path: `/translations/${workspaceId.value}/configuration`,
    query: route.query
  })
}

async function refreshWorkspace() {
  try {
    await hydrateWorkspace(await translationApi.get(workspaceId.value))
  } catch {
    // Keep the current workspace visible when a background refresh races another update.
  }
}

async function saveTranslationContent(content: string, title: string) {
  if (!workspace.value || !selectedChapter.value?.taskExists) {
    throw new Error('Translation chapter is unavailable')
  }
  const chapterId = selectedChapter.value.id
  const result = await translationApi.updateResult(workspaceId.value, chapterId, content, title)
  const chapter = workspace.value.chapters.find(item => item.id === chapterId)
  if (chapter) {
    chapter.translatedParagraphs = result.content
    chapter.translatedTitle = result.title
    chapter.resultAvailable = true
    chapter.status = 'translated'
    chapter.lastError = null
  }
  await refreshWorkspace()
  return result
}

async function startTranslation() {
  if (!workspace.value || starting.value) return
  const from = workspace.value.chapters.find(chapter => chapter.id === rangeStart.value)
  const to = workspace.value.chapters.find(chapter => chapter.id === rangeEnd.value)
  if (!from || !to || from.chapterIndex > to.chapterIndex) return

  starting.value = true
  try {
    await hydrateWorkspace(await translationApi.start(workspaceId.value, {
      chapterIndexFrom: from.chapterIndex,
      chapterIndexTo: to.chapterIndex,
      refetch: refetch.value,
      force: force.value
    }))
    toast.add({
      title: 'Translation tasks queued',
      description: `Chapters ${from.chapterIndex}–${to.chapterIndex} were submitted to the translation queue.`,
      color: 'success',
      icon: 'lucide:play'
    })
  } catch {
    await refreshWorkspace()
    toast.add({
      title: 'Unable to publish translation tasks',
      description: 'Queued state was preserved. Enable Force to retry tasks that were already queued.',
      color: 'error',
      icon: 'lucide:circle-alert'
    })
  } finally {
    starting.value = false
  }
}

async function stopTranslation() {
  if (stopping.value) return
  stopping.value = true
  try {
    await hydrateWorkspace(await translationApi.stop(workspaceId.value))
    toast.add({
      title: 'Queued translations stopped',
      description: 'Queued chapters were reset. A chapter already running will finish normally.',
      color: 'success',
      icon: 'lucide:square'
    })
  } catch {
    await refreshWorkspace()
    toast.add({
      title: 'Unable to stop queued translations',
      description: 'The workspace changed while the stop request was being applied.',
      color: 'error',
      icon: 'lucide:circle-alert'
    })
  } finally {
    stopping.value = false
  }
}

type TranslationUpdatedPayload = {
  translationId: string
  taskId?: string
}

useRealtime().onMessage<TranslationUpdatedPayload>('translation.updated', ({ payload }) => {
  if (payload.translationId !== workspaceId.value) return
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
  <UDashboardPanel id="translation-workspace">
    <UDashboardNavbar :title="workspace?.name || 'Translation workspace'">
      <template #leading>
        <UDashboardSidebarCollapse />
      </template>
      <template #right>
        <UButton
          label="Translations"
          icon="lucide:arrow-left"
          to="/translations"
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
        label: 'Back to Translations',
        icon: 'lucide:arrow-left',
        to: '/translations'
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
                    {{ workspace.novelChapterCount }}
                  </dd>
                </div>
              </dl>
              <div class="space-y-1.5 pt-2">
                <div class="flex justify-between gap-3 text-xs text-muted">
                  <span>Translation progress</span>
                  <span class="tabular-nums">
                    {{ workspace.progress.translated }} / {{ workspace.progress.total }} tasks
                  </span>
                </div>
                <UProgress
                  :model-value="workspace.progress.translated"
                  :max="Math.max(workspace.progress.total, 1)"
                  size="xs"
                />
                <div class="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted">
                  <span class="inline-flex items-center gap-1.5">
                    <UIcon name="lucide:clock-3" class="size-3.5" />
                    <span class="tabular-nums">{{ workspace.progress.queued }}</span>
                    queued
                  </span>
                  <span class="inline-flex items-center gap-1.5">
                    <UIcon
                      name="lucide:loader-circle"
                      class="size-3.5"
                      :class="workspace.progress.running ? 'animate-spin' : undefined"
                    />
                    <span class="tabular-nums">{{ workspace.progress.running }}</span>
                    running
                  </span>
                </div>
              </div>
            </div>
          </div>
        </section>
      </template>

      <template #right>
        <TranslationsRunToolbar
          v-model:range-start="rangeStart"
          v-model:range-end="rangeEnd"
          v-model:refetch="refetch"
          v-model:force="force"
          :workspace="workspace"
          :starting="starting"
          :stopping="stopping"
          @configure="openConfiguration"
          @start="startTranslation"
          @stop="stopTranslation"
        />
      </template>
    </UDashboardToolbar>

    <TranslationsComparisonReader
      v-if="workspace && selectedChapter"
      ref="comparisonRef"
      :workspace="workspace"
      :chapter="selectedChapter"
      :translation-available="translationAvailable"
      :translation-loading="translationLoading"
      :translation-load-error="translationLoadError"
      :save-translation="saveTranslationContent"
      :original-loading="originalLoading"
      :original-load-error="originalLoadError"
      :can-previous="selectedIndex > 0"
      :can-next="selectedIndex < workspace.chapters.length - 1"
      @chapters="chaptersOpen = true"
      @configure="openConfiguration"
      @navigate="navigateChapter"
    />
  </UDashboardPanel>

  <TranslationsChapterSlideover
    v-if="workspace"
    v-model:open="chaptersOpen"
    :workspace="workspace"
    :selected-id="selectedChapter?.id || null"
    @select="selectChapter"
  />
</template>
