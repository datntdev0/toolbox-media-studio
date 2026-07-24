<script setup lang="ts">
import * as z from 'zod'
import type { FormSubmitEvent } from '@nuxt/ui'
import {
  ApiException,
  ScrapingCreateRequest,
  type CrawlerMetadataResponse,
  type CrawlerSummaryResponse,
  type ScrapingCreateResponse
} from '~~/shared/api-services/srv-core.client'

const open = defineModel<boolean>('open', { default: false })

const emit = defineEmits<{
  created: [scraping: ScrapingCreateResponse]
  crawlersLoaded: [crawlers: CrawlerSummaryResponse[]]
}>()

const schema = z.object({
  crawlerId: z.string().min(1, 'Select a crawler.'),
  sourceUrl: z.string().url('Enter a valid source URL.')
})

type Schema = z.output<typeof schema>

const state = reactive<Partial<Schema>>({
  crawlerId: undefined,
  sourceUrl: ''
})

const crawlers = ref<CrawlerSummaryResponse[]>([])
const crawlersLoading = ref(false)
const crawlersError = ref(false)
const preview = ref<CrawlerMetadataResponse | null>(null)
const previewing = ref(false)
const submitting = ref(false)
const sourceError = ref('')
const failedCover = ref(false)
const toast = useToast()

const crawlerItems = computed(() => crawlers.value
  .filter(item => item.metadataSupported)
  .map(item => ({
    label: item.name,
    value: item.id,
    description: item.hosts?.join(', ')
  })))

watch(
  () => [state.crawlerId, state.sourceUrl],
  () => {
    preview.value = null
    sourceError.value = ''
    failedCover.value = false
  }
)

watch(open, (value) => {
  if (value && !crawlers.value.length) void loadCrawlers()
})

async function loadCrawlers() {
  crawlersLoading.value = true
  crawlersError.value = false
  try {
    const { crawlers: client } = useApiClient()
    const response = await client.list_crawlers()
    crawlers.value = response.items || []
    emit('crawlersLoaded', crawlers.value)
  } catch {
    crawlersError.value = true
  } finally {
    crawlersLoading.value = false
  }
}

function errorStatus(error: unknown) {
  return error instanceof ApiException ? error.status : undefined
}

function validationMessage(error: unknown) {
  if (!error || typeof error !== 'object') return ''
  const detail = (error as { detail?: Array<{ msg?: string }> }).detail
  return detail?.find(item => item.msg)?.msg || ''
}

async function loadPreview(data: Schema) {
  previewing.value = true
  sourceError.value = ''
  try {
    const { crawlers: client } = useApiClient()
    preview.value = await client.get_crawler_metadata(data.crawlerId, data.sourceUrl, true)
  } catch (error) {
    const status = errorStatus(error)
    sourceError.value = status === 504
      ? 'The source took too long to respond. Try again shortly.'
      : status === 502
        ? 'The source could not be read. Check the URL and try again.'
        : validationMessage(error) || 'Unable to preview this source. Check the URL and try again.'
  } finally {
    previewing.value = false
  }
}

async function createScraping(data: Schema) {
  submitting.value = true
  sourceError.value = ''
  try {
    const { scrapings } = useApiClient()
    const created = await scrapings.create_scraping(new ScrapingCreateRequest({
      crawlerId: data.crawlerId,
      sourceUrl: data.sourceUrl
    }))

    toast.add(created.reused
      ? {
          title: 'An active scraping already exists.',
          icon: 'lucide:info',
          color: 'neutral'
        }
      : {
          title: 'Scraping queued',
          description: `${created.title} was added to your scrapings.`,
          icon: 'lucide:circle-check',
          color: 'success'
        })

    emit('created', created)
    open.value = false
    state.crawlerId = undefined
    state.sourceUrl = ''
    preview.value = null
  } catch (error) {
    const status = errorStatus(error)
    sourceError.value = status === 502
      ? 'The source could not be read. Check the URL and try again.'
      : status === 504
        ? 'The source took too long to respond. Try again shortly.'
        : validationMessage(error)
          || (status === 422 ? 'The source URL was not accepted.' : 'Unable to create the scraping.')
  } finally {
    submitting.value = false
  }
}

async function onSubmit(event: FormSubmitEvent<Schema>) {
  if (preview.value) {
    await createScraping(event.data)
  } else {
    await loadPreview(event.data)
  }
}
</script>

<template>
  <UModal
    v-model:open="open"
    title="New Scraping"
    description="Preview a novel source, then download all of its chapters."
    :dismissible="!submitting"
  >
    <template #body>
      <UAlert
        v-if="crawlersError"
        class="mb-4"
        color="error"
        variant="subtle"
        icon="lucide:circle-alert"
        title="Unable to load crawlers"
        description="The available sources could not be loaded."
        :actions="[{
          label: 'Retry',
          color: 'error',
          variant: 'soft',
          onClick: loadCrawlers
        }]"
      />

      <UForm
        :schema="schema"
        :state="state"
        class="space-y-5"
        @submit="onSubmit"
      >
        <UFormField label="Crawler" name="crawlerId" required>
          <USelect
            v-model="state.crawlerId"
            :items="crawlerItems"
            value-key="value"
            label-key="label"
            placeholder="Select a crawler"
            icon="lucide:globe"
            :loading="crawlersLoading"
            :disabled="submitting || crawlersError"
            class="w-full"
          />
        </UFormField>

        <UFormField
          label="Source URL"
          name="sourceUrl"
          required
          :error="sourceError || undefined"
        >
          <UInput
            v-model="state.sourceUrl"
            type="url"
            placeholder="https://example.com/novel"
            icon="lucide:link"
            :disabled="submitting"
            class="w-full"
          />
        </UFormField>

        <UPageCard
          v-if="preview"
          orientation="horizontal"
          variant="subtle"
          class="overflow-hidden"
          :ui="{
            container: 'flex flex-row items-center lg:flex lg:flex-row lg:items-center sm:p-2 sm:px-4',
            wrapper: 'min-w-0 p-0',
            title: 'line-clamp-2',
            description: 'line-clamp-3'
          }"
        >
          <div class="flex min-h-36 w-24 shrink-0 items-center justify-center overflow-hidden bg-primary/10 sm:w-28">
            <img
              v-if="preview.coverImageUrl && !failedCover"
              :src="String(preview.coverImageUrl)"
              :alt="`${preview.title} cover`"
              class="size-full object-cover"
              @error="failedCover = true"
            >
            <UIcon v-else name="lucide:book-open" class="size-7 text-primary/70" />
          </div>

          <template #title>
            <h3 class="font-semibold text-highlighted">
              {{ preview.title }}
            </h3>
          </template>

          <template #description>
            <p class="text-sm text-muted">
              {{ String(preview.description || 'No description available.') }}
            </p>
          </template>

          <template #footer>
            <div class="flex flex-wrap gap-x-4 gap-y-1 text-xs text-toned">
              <span>{{ String(preview.author || 'Unknown author') }}</span>
              <span>{{ preview.chapters?.length || 0 }} chapters</span>
            </div>
          </template>
        </UPageCard>

        <div class="flex justify-end gap-2">
          <UButton
            label="Cancel"
            color="neutral"
            variant="ghost"
            :disabled="submitting"
            @click="open = false"
          />
          <UButton
            type="submit"
            :label="preview ? 'Create Scraping' : 'Preview'"
            :icon="preview ? 'lucide:download' : 'lucide:scan-search'"
            :loading="previewing || submitting"
            :disabled="crawlersLoading || crawlersError"
          />
        </div>
      </UForm>
    </template>
  </UModal>
</template>
