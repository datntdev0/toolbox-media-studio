<script setup lang="ts">
import type {
  TranslationConfigurationInput,
  TranslationWorkspace
} from '~/types/translation-workspace'
import { translationProviders } from '~/types/translation-workspace'

const props = defineProps<{
  workspace: TranslationWorkspace
  previewChapterId?: string
}>()
const configuration = defineModel<TranslationConfigurationInput>('configuration', {
  required: true
})
const previewValid = ref(false)
const toast = useToast()
const { previewTranslation } = useApiClient()
const previewLoading = ref(false)
const previewError = ref<string | null>(null)
const previewTitle = ref('')
const previewParagraphs = ref<string[]>([])
const originalCharacterCount = computed(() =>
  formatCharacterCount(previewChapter.value?.originalParagraphs || [])
)
const previewCharacterCount = computed(() => formatCharacterCount(previewParagraphs.value))

const providerId = computed({
  get: () => configuration.value.providerId,
  set: (providerId: string) => {
    configuration.value = { ...configuration.value, providerId }
  }
})
const modelId = computed({
  get: () => configuration.value.modelId,
  set: (modelId: string) => {
    configuration.value = { ...configuration.value, modelId }
  }
})
const prompt = computed({
  get: () => configuration.value.globalPrompt,
  set: (globalPrompt: string) => {
    configuration.value = { ...configuration.value, globalPrompt }
  }
})

const providerItems = translationProviders.map(provider => ({
  label: provider.label,
  value: provider.id,
  icon: provider.icon
}))
const selectedProvider = computed(() =>
  translationProviders.find(provider => provider.id === providerId.value)
  || translationProviders[0]!
)
const modelItems = computed(() => selectedProvider.value.models.map(model => ({
  label: model.label,
  value: model.id,
  description: model.description
})))
const previewChapter = computed(() =>
  props.workspace.chapters.find(chapter =>
    chapter.id === props.previewChapterId
  )
  || props.workspace.chapters.find(chapter => chapter.originalParagraphs.length)
  || props.workspace.chapters[0]
)
watch([providerId, modelId, prompt], () => {
  previewValid.value = false
  previewError.value = null
})

watch(providerId, () => {
  const nextModel = selectedProvider.value.models[0]
  if (nextModel) modelId.value = nextModel.id
})

async function generatePreview() {
  const chapter = previewChapter.value
  if (!chapter?.originalParagraphs.length) {
    previewValid.value = false
    previewError.value = 'The selected chapter has no source content to preview.'
    return
  }

  previewLoading.value = true
  previewError.value = null
  try {
    const response = await previewTranslation({
      provider: providerId.value,
      model: modelId.value,
      language: props.workspace.targetLanguage.code,
      instruction: prompt.value,
      chapter: chapter.id
    })
    previewTitle.value = response.title
    previewParagraphs.value = response.content
    previewValid.value = true
    toast.add({
      title: 'Preview generated',
      description: `${selectedProvider.value.label} translated Chapter ${chapter.number}.`,
      color: 'success',
      icon: 'lucide:scan-text'
    })
  } catch (error) {
    previewValid.value = false
    previewError.value = error instanceof Error
      ? error.message
      : 'The translation preview could not be generated.'
  } finally {
    previewLoading.value = false
  }
}
</script>

<template>
  <div class="grid gap-6 lg:grid-cols-12 h-full">
    <div class="space-y-6 lg:col-span-5">
      <UPageCard
        title="LLM model"
        description="Choose the provider and model used for chapter translation."
        variant="subtle"
      >
        <div class="grid gap-5 sm:grid-cols-2">
          <UFormField label="AI provider" required>
            <USelect
              v-model="providerId"
              :items="providerItems"
              value-key="value"
              label-key="label"
              icon="lucide:brain"
              class="w-full"
            />
          </UFormField>
          <UFormField label="AI model" required>
            <USelect
              v-model="modelId"
              :items="modelItems"
              value-key="value"
              label-key="label"
              icon="lucide:sparkles"
              class="w-full"
            />
          </UFormField>
        </div>
      </UPageCard>

      <UPageCard variant="subtle" :ui="{ header: 'w-full' }">
        <template #header>
          <div class="flex w-full items-start justify-between gap-3">
            <div class="min-w-0 flex-1">
              <h2 class="font-semibold text-highlighted">
                Translation instructions
              </h2>
              <p class="mt-1 text-sm text-muted">
                Review the target and the instructions applied to every chapter.
              </p>
            </div>
            <UButton
              label="Preview"
              icon="lucide:scan-text"
              color="primary"
              :loading="previewLoading"
              :disabled="previewLoading"
              class="ml-auto shrink-0"
              @click="generatePreview"
            />
          </div>
        </template>

        <div class="space-y-5">
          <UFormField label="Target language" description="Use the workspace edit action to change this value.">
            <UInput
              :model-value="`${workspace.targetLanguage.label} · ${workspace.targetLanguage.nativeLabel}`"
              icon="lucide:lock"
              disabled
              class="w-full"
            />
          </UFormField>

          <UFormField
            label="Global prompt"
            description="Changing these instructions makes the current preview stale."
            required
          >
            <UTextarea
              v-model="prompt"
              :rows="12"
              autoresize
              class="w-full"
            />
          </UFormField>
          <p class="text-right text-xs tabular-nums text-muted">
            {{ prompt.length }} characters
          </p>
        </div>
      </UPageCard>
    </div>

    <UPageCard class="overflow-hidden lg:col-span-7" variant="naked" :ui="{ header: 'mb-4 w-full', body: 'w-full' }">
      <template #header>
        <div class="flex w-full items-start gap-3">
          <div class="min-w-0 flex-1">
            <p class="text-xs font-medium tracking-wide text-primary uppercase">
              Chapter preview
            </p>
            <h2 class="mt-1 text-lg font-semibold text-highlighted">
              Chapter {{ previewChapter?.number }} · {{ previewChapter?.title }}
            </h2>
            <p class="mt-1 text-sm text-muted">
              {{ workspace.sourceLanguage.label }} → {{ workspace.targetLanguage.label }}
            </p>
          </div>
        </div>
      </template>

      <template #body>
        <section class="min-h-0">
          <h5 class="mb-2 text-muted font-medium">
            Original content · {{ originalCharacterCount }} characters
          </h5>
          <article
            :lang="workspace.sourceLanguage.code"
            class="ps-4 space-y-5 text-base/8 text-toned sm:text-lg/9 h-[400px] overflow-y-auto"
          >
            <p v-for="(paragraph, index) in previewChapter?.originalParagraphs || []" :key="index">
              {{ paragraph }}
            </p>
            <p v-if="!previewChapter?.originalParagraphs.length">
              Original chapter content is unavailable.
            </p>
          </article>
        </section>

        <USeparator :ui="{ root: 'my-4' }" />

        <section class="min-h-0">
          <div v-if="previewValid && !previewError">
            <h5 class="mb-2 flex items-center gap-2 text-muted font-medium">
              <UIcon name="lucide:circle-check" class="size-4 text-success" />
              {{ previewTitle || `Preview generated from Chapter ${previewChapter?.number}` }} · {{ previewCharacterCount }} characters
            </h5>
            <article
              :lang="workspace.targetLanguage.code"
              class="ps-4 space-y-5 text-base/8 text-toned sm:text-lg/9 h-[400px] overflow-y-auto"
            >
              <p v-for="(paragraph, index) in previewParagraphs" :key="index">
                {{ paragraph }}
              </p>
            </article>
          </div>

          <UAlert
            v-else-if="previewError"
            color="error"
            variant="subtle"
            icon="lucide:triangle-alert"
            title="Preview failed"
            :description="previewError"
            class="m-6"
          />

          <div v-else class="flex min-h-full items-center justify-center p-6">
            <UEmpty
              icon="lucide:refresh-cw"
              title="Preview is out of date"
              description="Generate a new fixed preview after changing the provider, model, or prompt."
              :actions="[{
                label: 'Preview',
                icon: 'lucide:scan-text',
                onClick: generatePreview
              }]"
            />
          </div>
        </section>
      </template>
    </UPageCard>
  </div>
</template>
