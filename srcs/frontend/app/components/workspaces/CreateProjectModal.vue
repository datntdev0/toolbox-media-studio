<script setup lang="ts">
import type { NovelResponse } from '~~/shared/api-services/srv-core.client'
import type { WorkspaceApiRecord } from '~/types/translation-workspace'
import { SUPPORTED_LANGUAGES, resolveLanguage } from '~/constants/supported-languages'

const props = defineProps<{ novels: NovelResponse[] }>()
const emit = defineEmits<{ created: [workspace: WorkspaceApiRecord] }>()
const open = defineModel<boolean>('open', { default: false })
const router = useRouter()
const toast = useToast()
const name = ref('')
const selectedNovelId = ref<string>()
const selectedLanguageCode = ref<string>()
const submitting = ref(false)

const novelItems = computed(() => props.novels.map(novel => ({
  label: novel.title,
  value: novel.id,
  description: `${resolveLanguage(String(novel.language || '')).label} · ${Number(novel.chapterCount || 0)} chapters`,
  icon: 'lucide:book-open'
})))
const selectedNovel = computed(() =>
  props.novels.find(novel => novel.id === selectedNovelId.value) || null
)
const languageItems = SUPPORTED_LANGUAGES.map(language => ({
  label: language.label,
  value: language.code,
  description: language.nativeLabel
}))

watch(open, (value) => {
  if (!value) {
    name.value = ''
    selectedNovelId.value = undefined
    selectedLanguageCode.value = undefined
  }
})

async function submit() {
  const workspaceName = name.value.trim()
  if (!workspaceName || !selectedNovel.value || !selectedLanguageCode.value) return
  submitting.value = true
  try {
    const workspace = await useTranslationWorkspaceApi().create({
      name: workspaceName,
      novelId: selectedNovel.value.id,
      targetLanguage: selectedLanguageCode.value
    })
    emit('created', workspace)
    open.value = false
    toast.add({
      title: 'Workspace created',
      description: `“${workspace.name}” is ready for setup.`,
      color: 'success'
    })
    await router.push(`/workspaces/${workspace.id}`)
  } catch (error) {
    toast.add({
      title: 'Unable to create workspace',
      description: error instanceof Error ? error.message : 'Please try again.',
      color: 'error'
    })
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <UModal
    v-model:open="open"
    title="New translation project"
    description="Name the workspace, then choose its novel and target language."
    :ui="{ content: 'sm:max-w-2xl' }"
  >
    <template #body>
      <div class="space-y-6">
        <UFormField label="Workspace name" required>
          <UInput
            v-model="name"
            placeholder="Vietnamese translation"
            icon="lucide:folder-pen"
            class="w-full"
            autofocus
          />
        </UFormField>

        <UFormField label="Project type" required>
          <button
            type="button"
            class="flex w-full items-center gap-4 rounded-xl border border-primary bg-primary/5 p-4 text-left focus-visible:outline-2 focus-visible:outline-primary"
            aria-pressed="true"
          >
            <span class="flex size-11 shrink-0 items-center justify-center rounded-lg bg-primary/10">
              <UIcon name="lucide:languages" class="size-5 text-primary" />
            </span>
            <span class="min-w-0 flex-1">
              <span class="block font-semibold text-highlighted">Translation</span>
              <span class="mt-0.5 block text-sm text-muted">
                Translate an existing Library novel with an AI language model.
              </span>
            </span>
            <UIcon name="lucide:circle-check" class="size-5 shrink-0 text-primary" />
          </button>
        </UFormField>

        <UFormField
          label="Novel"
          description="Select a novel that already exists in your Library."
          required
        >
          <USelectMenu
            v-model="selectedNovelId"
            :items="novelItems"
            value-key="value"
            label-key="label"
            placeholder="Search Library novels"
            icon="lucide:library-big"
            class="w-full"
          />
        </UFormField>

        <UFormField
          label="Target language"
          description="You can change the target language later."
          required
        >
          <USelectMenu
            v-model="selectedLanguageCode"
            :items="languageItems"
            value-key="value"
            label-key="label"
            placeholder="Select target language"
            icon="lucide:globe-2"
            class="w-full"
          />
        </UFormField>
      </div>
    </template>

    <template #footer>
      <div class="flex w-full items-center justify-between gap-3">
        <UButton
          label="Open Library"
          icon="lucide:library-big"
          to="/library/novels"
          color="neutral"
          variant="ghost"
        />
        <div class="flex gap-2">
          <UButton
            label="Cancel"
            color="neutral"
            variant="subtle"
            @click="open = false"
          />
          <UButton
            label="Create project"
            icon="lucide:plus"
            :disabled="!name.trim() || !selectedNovelId || !selectedLanguageCode"
            :loading="submitting"
            @click="submit"
          />
        </div>
      </div>
    </template>
  </UModal>
</template>
