<script setup lang="ts">
import * as z from 'zod'
import type { FormSubmitEvent } from '@nuxt/ui'
import { NovelUpdateRequest, type INovelUpdateRequest, type NovelResponse } from '~~/shared/api-services/srv-core.client'

const props = defineProps<{ novel: NovelResponse }>()
const emit = defineEmits<{ updated: [novel: NovelResponse] }>()
const open = defineModel<boolean>('open', { default: false })

const schema = z.object({
  title: z.string().min(1, 'A title is required'),
  author: z.string(),
  language: z.string(),
  coverImageUrl: z.string(),
  description: z.string(),
  tags: z.string(),
  notes: z.string()
})
type Schema = z.output<typeof schema>

const submitting = ref(false)
const toast = useToast()
const state = reactive<Schema>({
  title: '', author: '', language: '', coverImageUrl: '', description: '', tags: '', notes: ''
})

function valueOf(value: unknown) {
  if (!value) return ''
  if (typeof value === 'string') return value
  if (typeof value !== 'object') return String(value)
  const record = value as Record<string, unknown>
  return String(record.name ?? record.value ?? record.text ?? Object.values(record).find(item => typeof item === 'string') ?? '')
}

function syncState() {
  state.title = props.novel.title
  state.author = valueOf(props.novel.author)
  state.language = valueOf(props.novel.language)
  state.coverImageUrl = valueOf(props.novel.coverImageUrl)
  state.description = valueOf(props.novel.description)
  state.tags = (props.novel.tags ?? []).join(', ')
  state.notes = valueOf(props.novel.notes)
}

watch(() => props.novel, syncState, { immediate: true })

function optional(value: string) {
  return value.trim() || undefined
}

async function onSubmit(event: FormSubmitEvent<Schema>) {
  submitting.value = true
  try {
    const request = {
      title: event.data.title.trim(),
      author: optional(event.data.author),
      language: optional(event.data.language),
      coverImageUrl: optional(event.data.coverImageUrl),
      description: optional(event.data.description),
      tags: event.data.tags.split(',').map(tag => tag.trim()).filter(Boolean),
      notes: optional(event.data.notes),
      etag: props.novel.etag
    }
    const { novels } = useApiClient()
    const novel = await novels.update_novel(props.novel.id, new NovelUpdateRequest(request as unknown as INovelUpdateRequest))
    emit('updated', novel)
    toast.add({ title: 'Novel updated', description: `“${novel.title}” has been updated.`, color: 'success' })
    open.value = false
  } catch {
    toast.add({ title: 'Unable to update novel', description: 'Please check the library service and try again.', color: 'error' })
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <UModal
    v-model:open="open"
    title="Edit novel"
    description="Update this story's details."
    @update:open="syncState"
  >
    <template #body>
      <UForm
        :schema="schema"
        :state="state"
        class="space-y-4"
        @submit="onSubmit"
      >
        <UFormField label="Title" name="title" required>
          <UInput v-model="state.title" class="w-full" autofocus />
        </UFormField>
        <div class="grid gap-4 sm:grid-cols-2">
          <UFormField label="Author" name="author">
            <UInput v-model="state.author" class="w-full" />
          </UFormField>
          <UFormField label="Language" name="language">
            <UInput v-model="state.language" class="w-full" />
          </UFormField>
        </div>
        <UFormField label="Cover image URL" name="coverImageUrl">
          <UInput v-model="state.coverImageUrl" class="w-full" />
        </UFormField>
        <UFormField label="Description" name="description">
          <UTextarea v-model="state.description" class="w-full" :rows="3" />
        </UFormField>
        <UFormField label="Tags" name="tags" hint="Comma-separated">
          <UInput v-model="state.tags" class="w-full" />
        </UFormField>
        <UFormField label="Notes" name="notes">
          <UTextarea v-model="state.notes" class="w-full" :rows="2" />
        </UFormField>

        <div class="flex justify-end gap-2">
          <UButton
            label="Cancel"
            color="neutral"
            variant="subtle"
            @click="open = false"
          />
          <UButton label="Save changes" type="submit" :loading="submitting" />
        </div>
      </UForm>
    </template>
  </UModal>
</template>
