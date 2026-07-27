<script setup lang="ts">
import type {
  TranslationChapter,
  TranslationWorkspace
} from '~/types/translation-workspace'
import { chapterStatusMeta } from '~/utils/translation-workspaces'

const props = defineProps<{
  workspace: TranslationWorkspace
  chapter: TranslationChapter
  canPrevious: boolean
  canNext: boolean
}>()

const emit = defineEmits<{
  navigate: [offset: number]
  chapters: []
}>()
const confirm = useConfirmDialog()
const toast = useToast()
const viewMode = ref<'original' | 'translation'>('original')
const editing = ref(false)
const savedLocally = ref(false)
const draft = ref('')
const localTranslation = ref<string[]>([])
const chaptersButtonRef = ref<{ $el?: HTMLElement } | null>(null)

const tabItems = [
  { label: 'Original', value: 'original', icon: 'lucide:book-open' },
  { label: 'Translation', value: 'translation', icon: 'lucide:languages' }
]

const dirty = computed(() =>
  editing.value && draft.value !== localTranslation.value.join('\n\n')
)
const chapterStatus = computed(() =>
  savedLocally.value
    ? chapterStatusMeta.manually_edited
    : chapterStatusMeta[props.chapter.status]
)
const canEdit = computed(() =>
  props.chapter.status !== 'unavailable'
  && props.chapter.status !== 'translating'
  && props.chapter.originalParagraphs.length > 0
)

watch(() => props.chapter.id, () => {
  editing.value = false
  savedLocally.value = false
  localTranslation.value = [...props.chapter.translatedParagraphs]
  draft.value = localTranslation.value.join('\n\n')
  viewMode.value = 'original'
}, { immediate: true })

function startEdit() {
  draft.value = localTranslation.value.join('\n\n')
  editing.value = true
  viewMode.value = 'translation'
}

async function cancelEdit() {
  if (dirty.value) {
    const discard = await confirm({
      title: 'Discard translation changes?',
      description: 'Your unsaved prototype edits will be lost.',
      confirmLabel: 'Discard changes',
      confirmColor: 'error'
    })
    if (!discard) return
  }
  draft.value = localTranslation.value.join('\n\n')
  editing.value = false
}

async function confirmDiscard() {
  if (!dirty.value) return true
  return await confirm({
    title: 'Discard translation changes?',
    description: 'Your unsaved prototype edits will be lost when you leave this chapter.',
    confirmLabel: 'Discard changes',
    confirmColor: 'error'
  })
}

function saveEdit() {
  localTranslation.value = draft.value
    .split(/\n\s*\n/g)
    .map(paragraph => paragraph.trim())
    .filter(Boolean)
  savedLocally.value = true
  editing.value = false
  toast.add({
    title: 'Prototype edit applied',
    description: 'This local preview is not persisted.',
    color: 'success',
    icon: 'lucide:circle-check'
  })
}

function focusChapters() {
  chaptersButtonRef.value?.$el?.focus()
}

defineExpose({ confirmDiscard, focusChapters })
</script>

<template>
  <div class="flex min-h-0 flex-1 flex-col">
    <div class="border-b border-default px-4 py-3 lg:hidden">
      <UTabs
        v-model="viewMode"
        :items="tabItems"
        :content="false"
        class="w-full"
      />
    </div>

    <div class="grid min-h-0 flex-1 lg:grid-cols-2">
      <section
        class="min-h-0 flex-col border-default lg:flex lg:border-r"
        :class="viewMode === 'original' ? 'flex' : 'hidden'"
        aria-labelledby="original-content-heading"
      >
        <header class="sticky top-0 z-10 flex min-h-16 items-center gap-3 border-b border-default bg-default/95 px-4 py-3 backdrop-blur sm:px-6">
          <div class="min-w-0 flex-1">
            <div class="flex flex-wrap items-center gap-2">
              <h2 id="original-content-heading" class="font-semibold text-highlighted">
                Original
              </h2>
              <UBadge
                :label="workspace.sourceLanguage.label"
                icon="lucide:lock"
                color="neutral"
                variant="subtle"
              />
            </div>
            <p class="mt-0.5 truncate text-xs text-muted">
              Chapter {{ chapter.number }} · {{ chapter.title }}
            </p>
          </div>
          <div class="flex gap-1">
            <UButton
              ref="chaptersButtonRef"
              icon="lucide:list"
              color="neutral"
              variant="soft"
              size="sm"
              aria-label="Open chapter list"
              @click="emit('chapters')"
            />
            <UButton
              icon="lucide:chevron-left"
              color="neutral"
              variant="ghost"
              size="sm"
              aria-label="Previous chapter"
              :disabled="!canPrevious"
              @click="emit('navigate', -1)"
            />
            <UButton
              icon="lucide:chevron-right"
              color="neutral"
              variant="ghost"
              size="sm"
              aria-label="Next chapter"
              :disabled="!canNext"
              @click="emit('navigate', 1)"
            />
          </div>
        </header>

        <article
          v-if="chapter.originalParagraphs.length"
          :lang="workspace.sourceLanguage.code"
          class="mx-auto w-full max-w-3xl space-y-5 px-6 py-9 text-base/8 text-toned sm:px-10 sm:py-12 sm:text-lg/9"
        >
          <p v-for="(paragraph, index) in chapter.originalParagraphs" :key="index">
            {{ paragraph }}
          </p>
        </article>

        <div v-else class="flex min-h-96 flex-1 items-center justify-center p-6">
          <UEmpty
            icon="lucide:file-clock"
            title="Original content unavailable"
            description="This chapter is listed in the novel, but its source text has not been downloaded."
            size="lg"
          />
        </div>
      </section>

      <section
        class="min-h-0 flex-col bg-elevated/20 lg:flex"
        :class="viewMode === 'translation' ? 'flex' : 'hidden'"
        aria-labelledby="translated-content-heading"
      >
        <header class="sticky top-0 z-10 flex min-h-16 items-center gap-3 border-b border-default bg-default/95 px-4 py-3 backdrop-blur sm:px-6">
          <div class="min-w-0 flex-1">
            <div class="flex flex-wrap items-center gap-2">
              <h2 id="translated-content-heading" class="font-semibold text-highlighted">
                Translation
              </h2>
              <UBadge
                :label="workspace.targetLanguage.label"
                icon="lucide:globe-2"
                variant="subtle"
              />
              <UBadge
                :label="chapterStatus.shortLabel"
                :icon="chapterStatus.icon"
                :color="chapterStatus.color"
                variant="subtle"
                :ui="chapter.status === 'translating' ? { leadingIcon: 'animate-spin' } : undefined"
              />
            </div>
            <p class="mt-0.5 truncate text-xs text-muted">
              Chapter {{ chapter.number }} · {{ chapter.title }}
            </p>
          </div>
          <UButton
            v-if="!editing"
            :label="localTranslation.length ? 'Edit translation' : 'Add translation'"
            icon="lucide:pencil"
            color="neutral"
            variant="soft"
            size="sm"
            :disabled="!canEdit"
            @click="startEdit"
          />
        </header>

        <div v-if="editing" class="flex min-h-96 flex-1 flex-col p-4 sm:p-6">
          <UAlert
            class="mb-4"
            color="neutral"
            variant="subtle"
            icon="lucide:pencil-line"
            title="Editing translated copy"
            description="Changes are kept only while this prototype screen remains open."
          />
          <UTextarea
            v-model="draft"
            aria-label="Translated chapter content"
            :rows="22"
            autoresize
            class="w-full flex-1 font-mono text-sm/7"
            :placeholder="`Enter the ${workspace.targetLanguage.label} translation…`"
          />
          <div class="sticky bottom-0 mt-4 flex justify-end gap-2 border-t border-default bg-default/95 py-3 backdrop-blur">
            <UButton
              label="Cancel"
              color="neutral"
              variant="subtle"
              @click="cancelEdit"
            />
            <UButton
              label="Save translation"
              icon="lucide:save"
              @click="saveEdit"
            />
          </div>
        </div>

        <article
          v-else-if="localTranslation.length"
          :lang="workspace.targetLanguage.code"
          class="mx-auto w-full max-w-3xl space-y-5 px-6 py-9 text-base/8 text-toned sm:px-10 sm:py-12 sm:text-lg/9"
        >
          <p v-for="(paragraph, index) in localTranslation" :key="index">
            {{ paragraph }}
          </p>
        </article>

        <div
          v-else-if="chapter.status === 'translating'"
          class="mx-auto w-full max-w-3xl space-y-4 p-8 sm:p-12"
          aria-label="Translating chapter"
        >
          <UAlert
            color="primary"
            variant="subtle"
            icon="lucide:loader-circle"
            title="Translation in progress"
            description="This chapter will refresh when the background translation finishes."
          />
          <USkeleton v-for="index in 8" :key="index" class="h-4" />
        </div>

        <div v-else-if="chapter.status === 'failed'" class="flex min-h-96 flex-1 items-center justify-center p-6">
          <UAlert
            class="max-w-lg"
            color="error"
            variant="subtle"
            icon="lucide:circle-x"
            title="Translation failed"
            description="The provider could not translate this chapter. It can be included in a later retry range or entered manually."
          />
        </div>

        <div v-else class="flex min-h-96 flex-1 items-center justify-center p-6">
          <UEmpty
            :icon="chapter.status === 'queued' ? 'lucide:clock-3' : 'lucide:languages'"
            :title="chapter.status === 'queued' ? 'Queued for translation' : 'No translation yet'"
            :description="chapter.status === 'queued'
              ? 'This chapter is waiting for the current translation run.'
              : 'Translate this chapter range or add the translated content manually.'"
            size="lg"
          />
        </div>
      </section>
    </div>
  </div>
</template>
