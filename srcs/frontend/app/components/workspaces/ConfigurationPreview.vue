<script setup lang="ts">
import type {
  TranslationConfigurationInput,
  TranslationWorkspace
} from '~/types/translation-workspace'
import { translationProviders } from '~/utils/translation-workspace-fixtures'

const props = defineProps<{
  workspace: TranslationWorkspace
  previewChapterId?: string
}>()
const configuration = defineModel<TranslationConfigurationInput>('configuration', {
  required: true
})
const previewValid = defineModel<boolean>('previewValid', { default: true })
const toast = useToast()

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
const previewParagraphs = computed(() => [
  `[${props.workspace.targetLanguage.label} preview] When the seventh bell sounded, the chapter began beneath a ceiling of quiet brass gears.`,
  'This fixed sample demonstrates the translation preview layout without contacting an AI provider.'
])

watch([providerId, modelId, prompt], () => {
  previewValid.value = false
})

watch(providerId, () => {
  const nextModel = selectedProvider.value.models[0]
  if (nextModel) modelId.value = nextModel.id
})

function generatePreview() {
  previewValid.value = true
  toast.add({
    title: 'Fixed preview restored',
    description: 'No AI provider was contacted in this prototype.',
    color: 'neutral',
    icon: 'lucide:scan-text'
  })
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

    <UPageCard class="overflow-hidden lg:col-span-7" variant="naked" :ui="{ header: 'mb-4 w-full' }">
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
            Original content
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
          <div v-if="previewValid">
            <h5 class="mb-2 flex items-center gap-2 text-muted font-medium">
              <UIcon name="lucide:circle-check" class="size-4 text-success" />
              Preview generated from Chapter {{ previewChapter?.number }}
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
