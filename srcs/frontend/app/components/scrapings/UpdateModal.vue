<script setup lang="ts">
import * as z from 'zod'
import type { FormSubmitEvent } from '@nuxt/ui'
import type { CrawlerMetadataResponse, ScrapingDetailResponse } from '~~/shared/api-services/srv-core.client'

const props = defineProps<{ scrapingId: string | null }>()
const emit = defineEmits<{ updated: [detail: ScrapingDetailResponse] }>()
const open = defineModel<boolean>('open', { default: false })

const schema = z.object({
  title: z.string().min(1, 'A title is required'),
  author: z.string(),
  category: z.string(),
  updatedDate: z.string(),
  protagonists: z.string(),
  description: z.string()
})
type Schema = z.output<typeof schema>

const state = reactive<Schema>({ title: '', author: '', category: '', updatedDate: '', protagonists: '', description: '' })
const detail = ref<ScrapingDetailResponse | null>(null)
const loading = ref(false)
const submitting = ref(false)
const refetching = ref(false)
const coverImage = ref<File | null>(null)
const clearCoverImage = ref(false)
const toast = useToast()

function syncState(item: ScrapingDetailResponse) {
  detail.value = item
  state.title = item.metadata.title
  state.author = item.metadata.author ? String(item.metadata.author) : ''
  state.category = item.metadata.category ? String(item.metadata.category) : ''
  state.updatedDate = item.metadata.updatedDate ? String(item.metadata.updatedDate) : ''
  state.protagonists = (item.metadata.protagonists || []).join(', ')
  state.description = item.metadata.description ? String(item.metadata.description) : ''
  clearCoverImage.value = false
  coverImage.value = null
}

async function loadDetail() {
  if (!props.scrapingId) return
  loading.value = true
  try {
    const { scrapings } = useApiClient()
    syncState(await scrapings.get_scraping(props.scrapingId))
  } catch {
    toast.add({ title: 'Unable to load scraping', color: 'error' })
    open.value = false
  } finally {
    loading.value = false
  }
}

watch(open, (value) => {
  if (value) void loadDetail()
})
watch(() => props.scrapingId, () => {
  if (open.value) void loadDetail()
})
watch(coverImage, (file) => {
  if (file) clearCoverImage.value = false
})
function populateMetadata(metadata: CrawlerMetadataResponse) {
  state.title = metadata.title
  state.author = metadata.author ? String(metadata.author) : ''
  state.category = metadata.category ? String(metadata.category) : ''
  state.updatedDate = metadata.updatedDate ? String(metadata.updatedDate) : ''
  state.protagonists = (metadata.protagonists || []).join(', ')
  state.description = metadata.description ? String(metadata.description) : ''
}

async function refetchMetadata() {
  if (!detail.value) return
  refetching.value = true
  try {
    const { scrapings } = useApiClient()
    populateMetadata(await scrapings.preview_scraping(detail.value.crawlerId, detail.value.sourceUrl, false))
    toast.add({ title: 'Metadata refetched', description: 'Review the refreshed values, then save your changes.', color: 'success' })
  } catch {
    toast.add({ title: 'Unable to refetch metadata', description: 'The source could not be read. Please try again.', color: 'error' })
  } finally {
    refetching.value = false
  }
}

async function onSubmit(event: FormSubmitEvent<Schema>) {
  if (!props.scrapingId) return
  submitting.value = true
  try {
    const body = {
      title: event.data.title.trim(),
      author: event.data.author.trim() || null,
      category: event.data.category.trim() || null,
      updatedDate: event.data.updatedDate.trim() || null,
      protagonists: event.data.protagonists.split(',').map(item => item.trim()).filter(Boolean),
      description: event.data.description.trim() || null,
      clearCoverImage: clearCoverImage.value
    }
    const { updateScraping } = useApiClient()
    let updated = await updateScraping(props.scrapingId, body)
    if (coverImage.value) {
      const { uploadScrapingCover } = useApiClient()
      updated = await uploadScrapingCover(updated.id, coverImage.value)
    }
    emit('updated', updated)
    toast.add({ title: 'Scraping updated', description: `“${updated.metadata.title}” has been updated.`, color: 'success' })
    open.value = false
  } catch (error) {
    toast.add({ title: 'Unable to update scraping', description: error instanceof Error ? error.message : 'Please try again.', color: 'error' })
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <UModal
    v-model:open="open"
    title="Edit scraping"
    description="Update the scraped novel metadata."
    :ui="{ content: 'sm:max-w-3xl' }"
    :dismissible="!submitting"
  >
    <template #body>
      <div v-if="loading" class="space-y-4">
        <USkeleton class="h-24 w-full" /><USkeleton class="h-48 w-full" />
      </div>
      <UForm
        v-else
        :schema="schema"
        :state="state"
        class="space-y-4"
        @submit="onSubmit"
      >
        <div class="flex items-start gap-4">
          <div class="w-41 shrink-0">
            <UFormField label="Cover image" name="coverImage">
              <UFileUpload
                v-model="coverImage"
                variant="area"
                accept="image/jpeg,image/png"
                label="Choose cover image"
                description="JPEG or PNG, max 1 MB"
                :file-image="true"
                :preview="true"
                class="w-41 aspect-[2/3]"
              />
              <UCheckbox v-if="detail?.metadata.coverImageUrl" v-model="clearCoverImage" label="Remove current cover" />
            </UFormField>
          </div>
          <div class="min-w-0 flex-1 space-y-4">
            <UFormField label="Title" name="title" required>
              <UInput v-model="state.title" class="w-full" autofocus />
            </UFormField>
            <div class="grid gap-4 sm:grid-cols-2">
              <UFormField label="Author" name="author">
                <UInput v-model="state.author" class="w-full" />
              </UFormField>
              <UFormField label="Category" name="category">
                <UInput v-model="state.category" class="w-full" />
              </UFormField>
            </div>
            <UFormField label="Updated date" name="updatedDate">
              <UInput v-model="state.updatedDate" class="w-full" />
            </UFormField>
            <UFormField label="Protagonists" name="protagonists" hint="Comma-separated">
              <UInput v-model="state.protagonists" class="w-full" />
            </UFormField>
          </div>
        </div>
        <UFormField label="Description" name="description">
          <UTextarea v-model="state.description" class="w-full" :rows="5" />
        </UFormField>
        <div class="flex justify-between gap-2">
          <UButton
            label="Refetch"
            icon="lucide:refresh-cw"
            color="neutral"
            variant="soft"
            :loading="refetching"
            :disabled="submitting"
            @click="refetchMetadata"
          />
          <div class="flex gap-2">
            <UButton
              label="Cancel"
              color="neutral"
              variant="subtle"
              :disabled="submitting"
              @click="open = false"
            /><UButton label="Save changes" type="submit" :loading="submitting" />
          </div>
        </div>
      </UForm>
    </template>
  </UModal>
</template>
