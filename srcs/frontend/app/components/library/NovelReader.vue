<script setup lang="ts">
import type { NovelChapterContent, NovelChapterSummary } from '~/types/novel-workspace'

const props = defineProps<{
  novelId: string
  chapter: NovelChapterSummary | null
  position: number
  total: number
  canPrevious: boolean
  canNext: boolean
  mobile?: boolean
}>()

const emit = defineEmits<{
  close: []
  navigate: [offset: number]
  saved: [chapter: NovelChapterContent]
}>()

const toast = useToast()
const confirm = useConfirmDialog()
const content = ref<NovelChapterContent | null>(null)
const draft = ref('')
const loading = ref(false)
const saving = ref(false)
const exporting = ref(false)
const error = ref(false)
const editing = ref(false)

const dirty = computed(() => editing.value && draft.value !== (content.value?.content || ''))
const paragraphs = computed(() =>
  (content.value?.content || '').split(/\n\s*\n/g).map(item => item.trim()).filter(Boolean)
)
const characterCount = computed(() =>
  formatCharacterCount(editing.value ? draft.value : content.value?.content || '')
)

watch(() => props.chapter?.id, () => {
  editing.value = false
  draft.value = ''
  void load()
}, { immediate: true })

function beforeUnload(event: BeforeUnloadEvent) {
  if (!dirty.value) return
  event.preventDefault()
  event.returnValue = ''
}

onMounted(() => window.addEventListener('beforeunload', beforeUnload))
onBeforeUnmount(() => window.removeEventListener('beforeunload', beforeUnload))

async function load() {
  content.value = null
  error.value = false
  if (!props.chapter?.contentAvailable) return
  loading.value = true
  try {
    content.value = await useNovelWorkspaceApi().getChapter(props.novelId, props.chapter.id)
  } catch {
    error.value = true
  } finally {
    loading.value = false
  }
}

function startEdit() {
  if (!content.value) return
  draft.value = content.value.content
  editing.value = true
}

async function cancelEdit() {
  if (dirty.value) {
    const discard = await confirm({
      title: 'Discard chapter changes?',
      description: 'Your unsaved edits will be lost.',
      confirmLabel: 'Discard changes',
      confirmColor: 'error'
    })
    if (!discard) return
  }
  editing.value = false
  draft.value = content.value?.content || ''
}

async function confirmDiscard() {
  if (!dirty.value) return true
  return await confirm({
    title: 'Discard chapter changes?',
    description: 'Your unsaved edits will be lost when you leave this chapter.',
    confirmLabel: 'Discard changes',
    confirmColor: 'error'
  })
}

async function save() {
  if (!props.chapter || !content.value) return
  saving.value = true
  try {
    const updated = await useNovelWorkspaceApi().editChapter(
      props.novelId,
      props.chapter.id,
      draft.value,
      content.value.etag || props.chapter.etag
    )
    content.value = updated
    draft.value = updated.content
    editing.value = false
    emit('saved', updated)
    toast.add({
      title: 'Chapter saved',
      description: `“${props.chapter.title}” has been updated.`,
      color: 'success',
      icon: 'lucide:circle-check'
    })
  } catch (cause) {
    const conflict = (cause as { status?: number })?.status === 412
    toast.add({
      title: conflict ? 'Chapter changed elsewhere' : 'Unable to save chapter',
      description: conflict ? 'Reload the chapter before applying your edits again.' : 'Please try again.',
      color: 'error',
      icon: 'lucide:circle-alert'
    })
  } finally {
    saving.value = false
  }
}

async function exportNovel() {
  if (!props.chapter || editing.value || exporting.value) return
  exporting.value = true
  try {
    const { blob, filename } = await useNovelWorkspaceApi().exportNovel(props.novelId)
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = filename
    link.style.display = 'none'
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.setTimeout(() => URL.revokeObjectURL(url), 0)
    toast.add({
      title: 'Export started',
      description: 'Your novel ZIP download should begin shortly.',
      color: 'success',
      icon: 'lucide:download'
    })
  } catch (cause) {
    toast.add({
      title: 'Export failed',
      description: cause instanceof Error ? cause.message : 'Unable to export novel. Please try again.',
      color: 'error',
      icon: 'lucide:circle-alert'
    })
  } finally {
    exporting.value = false
  }
}

defineExpose({ confirmDiscard, refresh: load })
</script>

<template>
  <UDashboardPanel id="novel-reader">
    <UDashboardNavbar :title="chapter?.title || 'Chapter reader'" :toggle="false">
      <template v-if="mobile" #leading>
        <UButton
          icon="lucide:x"
          color="neutral"
          variant="ghost"
          aria-label="Close chapter"
          @click="emit('close')"
        />
      </template>
      <template #right>
        <span v-if="chapter" class="hidden text-xs text-muted sm:inline">
          {{ position }} / {{ total }}
        </span>
        <UButton
          icon="lucide:chevron-left"
          color="neutral"
          variant="ghost"
          aria-label="Previous chapter"
          :disabled="!canPrevious || saving || exporting"
          @click="emit('navigate', -1)"
        />
        <UButton
          icon="lucide:chevron-right"
          color="neutral"
          variant="ghost"
          aria-label="Next chapter"
          :disabled="!canNext || saving || exporting"
          @click="emit('navigate', 1)"
        />
        <UButton
          v-if="chapter && content && !editing"
          label="Edit"
          icon="lucide:pencil"
          color="neutral"
          variant="soft"
          size="sm"
          @click="startEdit"
        />
        <UButton
          v-if="chapter && !editing"
          label="Export"
          icon="lucide:download"
          color="primary"
          variant="soft"
          size="sm"
          :loading="exporting"
          :disabled="exporting"
          @click="exportNovel"
        />
      </template>
    </UDashboardNavbar>

    <div class="min-h-0 flex-1 overflow-y-auto">
      <div v-if="loading" class="mx-auto max-w-3xl space-y-4 p-6 sm:p-10" aria-label="Loading chapter">
        <USkeleton class="h-7 w-2/3" />
        <USkeleton
          v-for="index in 10"
          :key="index"
          class="h-4"
          :class="index % 3 === 0 ? 'w-10/12' : 'w-full'"
        />
      </div>

      <div v-else-if="editing" class="flex min-h-full flex-col p-4 sm:p-6">
        <div class="mx-auto flex w-full max-w-4xl flex-1 flex-col gap-4">
          <UAlert
            color="neutral"
            variant="subtle"
            icon="lucide:pencil-line"
            title="Editing novel copy"
            description="These changes do not affect the bound scraping and will be preserved during sync."
          />
          <UTextarea
            v-model="draft"
            aria-label="Chapter content"
            autoresize
            :rows="24"
            class="w-full flex-1 font-mono text-sm/7"
          />
          <p class="text-right text-xs tabular-nums text-muted">
            {{ characterCount }} characters
          </p>
          <div class="sticky bottom-0 flex justify-end gap-2 border-t border-default bg-default py-3">
            <UButton
              label="Cancel"
              color="neutral"
              variant="subtle"
              :disabled="saving"
              @click="cancelEdit"
            />
            <UButton
              label="Save chapter"
              icon="lucide:save"
              :loading="saving"
              @click="save"
            />
          </div>
        </div>
      </div>

      <div v-else-if="error" class="flex min-h-full items-center justify-center p-6">
        <UAlert
          class="max-w-lg"
          color="error"
          variant="subtle"
          icon="lucide:circle-alert"
          title="Unable to load chapter"
          description="The chapter content could not be opened."
          :actions="[{ label: 'Retry', color: 'error', variant: 'soft', onClick: load }]"
        />
      </div>

      <div v-else-if="chapter && !chapter.contentAvailable" class="flex min-h-full items-center justify-center p-6">
        <UEmpty
          icon="lucide:file-clock"
          title="Content not downloaded"
          description="This chapter is in the novel outline, but its source content is not available yet."
          size="xl"
        />
      </div>

      <article v-else-if="chapter && content" class="mx-auto max-w-3xl px-6 py-10 sm:px-10 sm:py-14">
        <header class="mb-10 border-b border-default pb-6 text-center">
          <p class="mb-2 text-xs font-medium tracking-widest text-primary uppercase">
            Chapter {{ chapter.chapterNumber ?? position }}
          </p>
          <h1 class="text-2xl font-semibold text-highlighted sm:text-3xl">
            {{ chapter.title }}
          </h1>
          <p class="mt-2 text-xs tabular-nums text-muted">
            {{ characterCount }} characters
          </p>
        </header>
        <div class="space-y-5 text-base/8 text-toned sm:text-lg/9">
          <p v-for="(paragraph, index) in paragraphs" :key="index">
            {{ paragraph }}
          </p>
          <p v-if="!paragraphs.length" class="text-center italic text-muted">
            This chapter has no text content.
          </p>
        </div>
      </article>

      <div v-else class="flex min-h-full items-center justify-center p-6">
        <UEmpty
          icon="lucide:book-open"
          title="Select a chapter"
          description="Choose a chapter from the novel outline to start reading."
          size="xl"
        />
      </div>
    </div>
  </UDashboardPanel>
</template>
