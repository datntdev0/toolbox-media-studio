<script setup lang="ts">
import * as z from 'zod'
import type { FormSubmitEvent } from '@nuxt/ui'
import { NovelCreateRequest, type INovelCreateRequest, type NovelResponse } from '~~/shared/api-services/srv-core.client'

const emit = defineEmits<{ created: [novel: NovelResponse] }>()

const schema = z.object({
  title: z.string().min(1, 'A title is required'),
  author: z.string(),
  language: z.string(),
  description: z.string(),
  tags: z.string(),
  notes: z.string()
})

type Schema = z.output<typeof schema>

const open = ref(false)
const submitting = ref(false)
const toast = useToast()
const state = reactive<Schema>({
  title: '',
  author: '',
  language: '',
  description: '',
  tags: '',
  notes: ''
})
const coverImage = ref<File | null>(null)

function optional(value: string) {
  return value.trim() || null
}

async function onSubmit(event: FormSubmitEvent<Schema>) {
  submitting.value = true
  try {
    const { novels } = useApiClient()
    const request = {
      title: event.data.title.trim(),
      author: optional(event.data.author),
      language: optional(event.data.language),
      description: optional(event.data.description),
      tags: event.data.tags.split(',').map(tag => tag.trim()).filter(Boolean),
      notes: optional(event.data.notes)
    }
    validateCoverImage(coverImage.value)
    const novel = await novels.create_novel(new NovelCreateRequest(request as unknown as INovelCreateRequest), coverImage.value)

    emit('created', novel)
    toast.add({ title: 'Novel created', description: `“${novel.title}” has been added to your library.`, color: 'success' })
    open.value = false
    coverImage.value = null
  } catch {
    toast.add({ title: 'Unable to create novel', description: 'Please check the library service and try again.', color: 'error' })
  } finally {
    submitting.value = false
  }
}

function validateCoverImage(file: File | null) {
  if (!file) return
  if (!['image/jpeg', 'image/png'].includes(file.type) || file.size > 1024 * 1024) {
    throw new Error('Cover image must be a JPEG or PNG no larger than 1 MB.')
  }
}
</script>

<template>
  <UModal
    v-model:open="open"
    title="New novel"
    description="Add a story to your library."
    :ui="{ content: 'sm:max-w-3xl' }"
  >
    <UButton label="New novel" icon="lucide:plus" />

    <template #body>
      <UForm
        :schema="schema"
        :state="state"
        class="space-y-4"
        @submit="onSubmit"
      >
        <div class="flex items-start gap-4">
          <div class="w-48 shrink-0">
            <UFormField label="Cover image" name="coverImage">
              <UFileUpload
                v-model="coverImage"
                variant="area"
                accept="image/jpeg,image/png"
                label="Choose cover image"
                description="JPG or PNG, max 1 MB"
                :preview="true"
                class="w-48 aspect-[2/3]"
              />
            </UFormField>
          </div>
          <div class="min-w-0 flex-1 space-y-4">
            <UFormField label="Title" name="title" required>
              <UInput
                v-model="state.title"
                placeholder="Novel title"
                class="w-full"
                autofocus
              />
            </UFormField>
            <div class="grid gap-4 sm:grid-cols-2">
              <UFormField label="Author" name="author">
                <UInput v-model="state.author" placeholder="Author name" class="w-full" />
              </UFormField>
              <UFormField label="Language" name="language">
                <UInput v-model="state.language" placeholder="e.g. English" class="w-full" />
              </UFormField>
            </div>
            <UFormField label="Tags" name="tags" hint="Comma-separated">
              <UInput v-model="state.tags" placeholder="fantasy, adventure" class="w-full" />
            </UFormField>
            <UFormField label="Notes" name="notes">
              <UTextarea v-model="state.notes" class="w-full" :rows="3" />
            </UFormField>
          </div>
        </div>

        <UFormField label="Description" name="description">
          <UTextarea
            v-model="state.description"
            placeholder="A short summary of the novel"
            class="w-full"
            :rows="5"
          />
        </UFormField>

        <div class="flex justify-end gap-2">
          <UButton
            label="Cancel"
            color="neutral"
            variant="subtle"
            @click="open = false"
          />
          <UButton label="Create novel" type="submit" :loading="submitting" />
        </div>
      </UForm>
    </template>
  </UModal>
</template>
