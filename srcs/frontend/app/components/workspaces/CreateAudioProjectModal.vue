<script setup lang="ts">
import type { NovelResponse } from '~~/shared/api-services/srv-core.client'
import type { AudioLanguageOption, AudioWorkspace } from '~/types/audio-workspace'
import { resolveLanguage } from '~/constants/supported-languages'

const props = defineProps<{ novels: NovelResponse[] }>()
const emit = defineEmits<{ created: [workspace: AudioWorkspace] }>()
const open = defineModel<boolean>('open', { default: false })
const router = useRouter()
const toast = useToast()
const title = ref('')
const selectedNovelId = ref<string>()
const selectedLanguage = ref<string>()
const languages = ref<AudioLanguageOption[]>([])
const languagesLoading = ref(false)
const languagesError = ref(false)
const submitting = ref(false)
let languageRequest = 0

const novelItems = computed(() => props.novels.map(novel => ({
  label: novel.title,
  value: novel.id,
  description: `${resolveLanguage(String(novel.language || '')).label} · ${Number(novel.chapterCount || 0)} chapters`,
  icon: 'lucide:book-open'
})))
const languageItems = computed(() => languages.value.map(item => ({
  label: item.sourceType === 'original'
    ? `Original · ${item.code === 'original' ? 'Unspecified language' : resolveLanguage(item.code).label}`
    : resolveLanguage(item.code).label,
  value: item.code,
  description: item.sourceType === 'original'
    ? 'Use the novel’s original chapter content'
    : 'Use the newest translation project for this language',
  icon: item.sourceType === 'original' ? 'lucide:book-open' : 'lucide:languages'
})))

watch(selectedNovelId, novelId => void loadLanguages(novelId))
watch(open, (value) => {
  if (value) return
  title.value = ''
  selectedNovelId.value = undefined
  selectedLanguage.value = undefined
  languages.value = []
  languagesLoading.value = false
  languagesError.value = false
})

async function loadLanguages(novelId?: string) {
  const request = ++languageRequest
  languages.value = []
  selectedLanguage.value = undefined
  languagesError.value = false
  if (!novelId) {
    languagesLoading.value = false
    return
  }
  languagesLoading.value = true
  try {
    const result = await useAudioWorkspaceApi().listLanguages(novelId)
    if (request !== languageRequest) return
    languages.value = result
    selectedLanguage.value = result[0]?.code
  } catch {
    if (request === languageRequest) languagesError.value = true
  } finally {
    if (request === languageRequest) languagesLoading.value = false
  }
}

async function submit() {
  const workspaceTitle = title.value.trim()
  if (!workspaceTitle || !selectedNovelId.value || !selectedLanguage.value) return
  submitting.value = true
  try {
    const workspace = await useAudioWorkspaceApi().create({
      title: workspaceTitle,
      novelId: selectedNovelId.value,
      language: selectedLanguage.value
    })
    emit('created', workspace)
    open.value = false
    toast.add({
      title: 'Audio workspace created',
      description: `“${workspace.title}” is ready.`,
      color: 'success'
    })
    await router.push(`/workspaces/audios/${workspace.id}`)
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
    title="New audio project"
    description="Choose a Library novel and the language that will supply its narration text."
    :ui="{ content: 'sm:max-w-2xl' }"
  >
    <template #body>
      <div class="space-y-6">
        <UFormField label="Project title" required>
          <UInput
            v-model="title"
            placeholder="Vietnamese audiobook"
            icon="lucide:folder-pen"
            class="w-full"
            autofocus
          />
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
          label="Content version"
          description="Original text is selected by default; translated languages use their newest project."
          :error="languagesError ? 'Unable to load this novel’s languages.' : undefined"
          required
        >
          <USelectMenu
            v-model="selectedLanguage"
            :items="languageItems"
            value-key="value"
            label-key="label"
            :placeholder="selectedNovelId ? 'Select content language' : 'Select a novel first'"
            icon="lucide:languages"
            class="w-full"
            :loading="languagesLoading"
            :disabled="!selectedNovelId || languagesLoading || languagesError"
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
            :disabled="!title.trim() || !selectedNovelId || !selectedLanguage"
            :loading="submitting"
            @click="submit"
          />
        </div>
      </div>
    </template>
  </UModal>
</template>
