<script setup lang="ts">
import type { TranslationWorkspace } from '~/types/translation-workspace'
import {
  translationLanguages,
  translationNovels
} from '~/utils/translation-workspace-fixtures'

const props = defineProps<{ workspaces: TranslationWorkspace[] }>()
const open = defineModel<boolean>('open', { default: false })
const router = useRouter()

const selectedNovelId = ref<string>()
const selectedLanguageCode = ref<string>()

const novelItems = translationNovels.map(novel => ({
  label: novel.title,
  value: novel.id,
  description: `${novel.sourceLanguage.label} · ${novel.chapterCount} chapters`,
  icon: 'lucide:book-open'
}))

const selectedNovel = computed(() =>
  translationNovels.find(novel => novel.id === selectedNovelId.value) || null
)

const languageItems = computed(() => translationLanguages
  .filter(language => language.code !== selectedNovel.value?.sourceLanguage.code)
  .map(language => ({
    label: language.label,
    value: language.code,
    description: language.nativeLabel
  }))
)

const duplicate = computed(() => props.workspaces.find(workspace =>
  workspace.novelId === selectedNovelId.value
  && workspace.targetLanguage.code === selectedLanguageCode.value
))

watch(selectedNovelId, () => {
  if (
    selectedLanguageCode.value
    && selectedLanguageCode.value === selectedNovel.value?.sourceLanguage.code
  ) {
    selectedLanguageCode.value = undefined
  }
})

watch(open, (value) => {
  if (!value) {
    selectedNovelId.value = undefined
    selectedLanguageCode.value = undefined
  }
})

async function submit() {
  if (duplicate.value) {
    open.value = false
    await router.push(`/workspaces/${duplicate.value.id}`)
    return
  }
  if (!selectedNovel.value || !selectedLanguageCode.value) return

  open.value = false
  await router.push({
    path: '/workspaces/prototype-new',
    query: {
      novel: selectedNovel.value.id,
      language: selectedLanguageCode.value
    }
  })
}
</script>

<template>
  <UModal
    v-model:open="open"
    title="New translation project"
    description="Choose a novel and its permanent target language."
    :ui="{ content: 'sm:max-w-2xl' }"
  >
    <template #body>
      <div class="space-y-6">
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
          description="The target language cannot be changed after project creation."
          required
        >
          <USelectMenu
            v-model="selectedLanguageCode"
            :items="languageItems"
            value-key="value"
            label-key="label"
            placeholder="Select target language"
            icon="lucide:globe-2"
            :disabled="!selectedNovelId"
            class="w-full"
          />
        </UFormField>

        <UAlert
          v-if="duplicate"
          color="warning"
          variant="subtle"
          icon="lucide:copy-check"
          title="This translation project already exists"
          :description="`${duplicate.novelTitle} already has a ${duplicate.targetLanguage.label} workspace.`"
        />
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
            :label="duplicate ? 'Open existing project' : 'Create project'"
            :icon="duplicate ? 'lucide:arrow-up-right' : 'lucide:plus'"
            :disabled="!selectedNovelId || !selectedLanguageCode"
            @click="submit"
          />
        </div>
      </div>
    </template>
  </UModal>
</template>
