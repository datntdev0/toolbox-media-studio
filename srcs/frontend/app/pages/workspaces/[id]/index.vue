<script setup lang="ts">
import type {
  TranslationChapter,
  TranslationWorkspace
} from '~/types/translation-workspace'
import {
  findTranslationWorkspace,
  translationLanguages,
  translationNovels,
  translationWorkspaces
} from '~/utils/translation-workspace-fixtures'

definePageMeta({
  title: 'Translation workspace',
  middleware: ['auth']
})

const route = useRoute()
const router = useRouter()
const toast = useToast()
const chaptersOpen = ref(false)
const rangeStart = ref('')
const rangeEnd = ref('')
const comparisonRef = ref<{
  confirmDiscard: () => Promise<boolean>
  focusChapters: () => void
} | null>(null)

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
    progress: {
      ...template.progress,
      total: novel.chapterCount
    },
    chapters: template.chapters.slice(0, novel.chapterCount)
  }
})

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

useHead(() => ({
  title: workspace.value
    ? `${workspace.value.novelTitle} · ${workspace.value.targetLanguage.label}`
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
    <UDashboardNavbar :title="workspace?.novelTitle || 'Translation workspace'">
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

    <UDashboardToolbar v-if="workspace" :ui="{ root: 'items-start gap-6 py-5', left: 'min-w-0 flex-1 self-stretch', right: 'min-w-0 flex-1 self-stretch' }">
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
              <dl class="grid grid-cols-2 gap-x-3 gap-y-2 text-sm">
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
                    Status
                  </dt>
                  <dd class="capitalize text-toned">
                    {{ workspace.status.replace('_', ' ') }}
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
              <div class="flex flex-wrap gap-1.5">
                <UBadge
                  label="Translation"
                  icon="lucide:languages"
                  color="neutral"
                  variant="subtle"
                  size="sm"
                />
                <UBadge
                  :label="workspace.targetLanguage.nativeLabel"
                  color="neutral"
                  variant="subtle"
                  size="sm"
                />
              </div>
            </div>
          </div>
          <p class="mt-3 line-clamp-4 text-sm/6 text-muted">
            Compare the original novel chapters with their {{ workspace.targetLanguage.label }} translation.
          </p>
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
      :can-previous="selectedIndex > 0"
      :can-next="selectedIndex < workspace.chapters.length - 1"
      @chapters="chaptersOpen = true"
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
