<script setup lang="ts">
import type { TranslationWorkspace } from '~/types/translation-workspace'
import { translationProviders } from '~/utils/translation-workspace-fixtures'

const props = defineProps<{ workspace: TranslationWorkspace }>()
const previewValid = defineModel<boolean>('previewValid', { default: true })
const toast = useToast()

const providerId = ref(props.workspace.configuration?.providerId || translationProviders[0]!.id)
const modelId = ref(
  props.workspace.configuration?.modelId
  || translationProviders[0]!.models[0]!.id
)
const prompt = ref(
  props.workspace.configuration?.globalPrompt
  || 'You are a professional literary translator. Preserve names, dialogue, tone, paragraph breaks, and narrative intent. Return only the translated chapter text.'
)

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
    chapter.id === props.workspace.configuration?.previewChapterId
  )
  || props.workspace.chapters.find(chapter => chapter.originalParagraphs.length)
  || props.workspace.chapters[0]
)
const previewParagraphs = computed(() =>
  props.workspace.configuration?.previewParagraphs.length
    ? props.workspace.configuration.previewParagraphs
    : [
        `[${props.workspace.targetLanguage.label} preview] When the seventh bell sounded, the chapter began beneath a ceiling of quiet brass gears.`,
        'This fixed sample demonstrates the translation preview layout without contacting an AI provider.'
      ]
)

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
  <div class="grid gap-6 lg:grid-cols-12">
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

      <UPageCard
        title="Translation instructions"
        description="Set the permanent target and the instructions applied to every chapter."
        variant="subtle"
      >
        <div class="space-y-5">
          <UFormField
            label="Target language"
            description="Create another workspace to translate this novel into a different language."
          >
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

    <UPageCard
      class="overflow-hidden lg:col-span-7"
      variant="subtle"
      :ui="{ body: 'p-0 sm:p-0', header: 'mb-4 w-full' }"
    >
      <template #header>
        <div class="flex w-full items-start gap-3">
          <div class="min-w-0 flex-1">
            <p class="text-xs font-medium tracking-wide text-primary uppercase">
              First chapter preview
            </p>
            <h2 class="mt-1 text-lg font-semibold text-highlighted">
              Chapter {{ previewChapter?.number }} · {{ previewChapter?.title }}
            </h2>
            <p class="mt-1 text-sm text-muted">
              {{ workspace.sourceLanguage.label }} → {{ workspace.targetLanguage.label }}
            </p>
          </div>
          <UButton
            label="Preview"
            icon="lucide:scan-text"
            color="neutral"
            variant="soft"
            class="ml-auto shrink-0"
            @click="generatePreview"
          />
        </div>
      </template>

      <div class="border-b border-default bg-elevated/30 px-5 py-6 sm:px-8 sm:py-8">
        <p class="mb-2 text-xs font-medium text-muted">
          Original excerpt
        </p>
        <article
          :lang="workspace.sourceLanguage.code"
          class="space-y-5 text-base/8 text-toned sm:text-lg/9"
        >
          <p>
            {{ previewChapter?.originalParagraphs[0] || 'Original chapter content is unavailable.' }}
          </p>
        </article>
      </div>

      <div v-if="previewValid" class="px-5 py-6 sm:px-8 sm:py-8">
        <div class="mb-6 flex items-center gap-2 text-xs text-muted">
          <UIcon name="lucide:circle-check" class="size-4 text-success" />
          <span>Preview generated from Chapter {{ previewChapter?.number }}</span>
        </div>
        <article
          :lang="workspace.targetLanguage.code"
          class="space-y-5 text-base/8 text-toned sm:text-lg/9"
        >
          <p v-for="(paragraph, index) in previewParagraphs" :key="index">
            {{ paragraph }}
          </p>
        </article>
      </div>

      <div v-else class="flex min-h-80 items-center justify-center p-6">
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
    </UPageCard>
  </div>
</template>
