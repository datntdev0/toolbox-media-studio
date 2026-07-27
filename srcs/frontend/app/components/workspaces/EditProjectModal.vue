<script setup lang="ts">
import type { NovelResponse } from '~~/shared/api-services/srv-core.client'
import type {
  TranslationWorkspace,
  WorkspaceApiRecord
} from '~/types/translation-workspace'
import { SUPPORTED_LANGUAGES, resolveLanguage } from '~/constants/supported-languages'

const props = defineProps<{
  workspace: TranslationWorkspace
  novels: NovelResponse[]
}>()
const emit = defineEmits<{ updated: [workspace: WorkspaceApiRecord] }>()
const open = defineModel<boolean>('open', { default: false })
const toast = useToast()
const submitting = ref(false)
const name = ref('')
const selectedNovelId = ref<string>()
const selectedLanguageCode = ref<string>()

const novelItems = computed(() => props.novels.map(novel => ({
  label: novel.title,
  value: novel.id,
  description: `${resolveLanguage(String(novel.language || '')).label} · ${Number(novel.chapterCount || 0)} chapters`,
  icon: 'lucide:book-open'
})))
const languageItems = SUPPORTED_LANGUAGES.map(language => ({
  label: language.label,
  value: language.code,
  description: language.nativeLabel
}))

function syncState() {
  name.value = props.workspace.name
  selectedNovelId.value = props.workspace.novelId
  selectedLanguageCode.value = props.workspace.targetLanguage.code
}

watch(() => props.workspace, syncState, { immediate: true })

async function submit() {
  const workspaceName = name.value.trim()
  if (!workspaceName || !selectedNovelId.value || !selectedLanguageCode.value) return
  submitting.value = true
  try {
    const workspace = await useTranslationWorkspaceApi().update(props.workspace.id, {
      name: workspaceName,
      novelId: selectedNovelId.value,
      targetLanguage: selectedLanguageCode.value,
      etag: props.workspace.etag
    })
    emit('updated', workspace)
    toast.add({
      title: 'Workspace updated',
      description: `“${workspace.name}” has been updated.`,
      color: 'success'
    })
    open.value = false
  } catch (error) {
    toast.add({
      title: 'Unable to update workspace',
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
    title="Edit workspace"
    description="Update the workspace name, bound novel, or target language."
    :ui="{ content: 'sm:max-w-2xl' }"
    @update:open="syncState"
  >
    <template #body>
      <div class="space-y-5">
        <UFormField label="Workspace name" required>
          <UInput
            v-model="name"
            icon="lucide:folder-pen"
            class="w-full"
            autofocus
          />
        </UFormField>
        <UFormField label="Novel" required>
          <USelectMenu
            v-model="selectedNovelId"
            :items="novelItems"
            value-key="value"
            label-key="label"
            icon="lucide:library-big"
            class="w-full"
          />
        </UFormField>
        <UFormField label="Target language" required>
          <USelectMenu
            v-model="selectedLanguageCode"
            :items="languageItems"
            value-key="value"
            label-key="label"
            icon="lucide:globe-2"
            class="w-full"
          />
        </UFormField>
      </div>
    </template>

    <template #footer>
      <div class="flex w-full justify-end gap-2">
        <UButton
          label="Cancel"
          color="neutral"
          variant="subtle"
          @click="open = false"
        />
        <UButton
          label="Save changes"
          icon="lucide:save"
          :disabled="!name.trim() || !selectedNovelId || !selectedLanguageCode"
          :loading="submitting"
          @click="submit"
        />
      </div>
    </template>
  </UModal>
</template>
