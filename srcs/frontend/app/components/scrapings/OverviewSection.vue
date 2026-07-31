<script setup lang="ts">
import {
  ApiException,
  ScrapingStartRequest,
  ScrapingTaskStatus,
  type ScrapingDetailResponse,
  type ScrapingTaskResponse
} from '~~/shared/api-services/srv-core.client'
import { formatExactTime } from '~/utils/scrapings'

const props = defineProps<{
  scrapingId: string
  detail: ScrapingDetailResponse
  sourceLabel: string
}>()

const emit = defineEmits<{ updated: [detail: ScrapingDetailResponse] }>()

const failedCover = ref(false)
const starting = ref(false)
const stopping = ref(false)
const startError = ref('')
const rangeInitializedFor = ref('')
const startState = reactive({
  chapterIndexFrom: 1,
  chapterIndexTo: 1,
  refetch: false,
  force: false
})

const sortedTasks = computed(() => [...(props.detail.tasks || [])]
  .sort((a, b) => a.manifestIndex - b.manifestIndex))
const hasUnnumberedTasks = computed(
  () => sortedTasks.value.some(task => parsedChapterNumber(task) === null)
)
const startValidationError = computed(() => {
  if (!Number.isInteger(startState.chapterIndexFrom) || startState.chapterIndexFrom < 1) {
    return 'Chapter index from must be a positive whole number.'
  }
  if (!Number.isInteger(startState.chapterIndexTo) || startState.chapterIndexTo < 1) {
    return 'Chapter index to must be a positive whole number.'
  }
  if (startState.chapterIndexFrom > startState.chapterIndexTo) {
    return 'Chapter index from must be less than or equal to chapter index to.'
  }
  return ''
})

watch(() => props.detail.id, initializeChapterRange, { immediate: true })

function parsedChapterNumber(task: ScrapingTaskResponse) {
  const value = task.chapterNumber as unknown
  return typeof value === 'number' && Number.isInteger(value) ? value : null
}

function initializeChapterRange(id: string) {
  if (rangeInitializedFor.value === id) return
  if (props.detail.tasks?.length) {
    startState.chapterIndexFrom = 1
    startState.chapterIndexTo = Math.max(
      ...props.detail.tasks.map(task => task.manifestIndex + 1)
    )
  }
  rangeInitializedFor.value = id
}

function errorStatus(cause: unknown) {
  return cause instanceof ApiException ? cause.status : undefined
}

function validationMessage(cause: unknown) {
  if (!cause || typeof cause !== 'object') return ''
  const detail = (cause as { detail?: string | Array<{ msg?: string }> }).detail
  if (typeof detail === 'string') return detail
  return detail?.find(item => item.msg)?.msg || ''
}

async function startTasks() {
  startError.value = startValidationError.value
  if (startError.value) return
  const expectedQueuedCount = sortedTasks.value.filter((task) => {
    const chapterIndex = task.manifestIndex + 1
    if (chapterIndex < startState.chapterIndexFrom || chapterIndex > startState.chapterIndexTo) return false
    return startState.force
      || ![ScrapingTaskStatus.Queued, ScrapingTaskStatus.Running].includes(task.status)
  }).length
  starting.value = true
  try {
    const { scrapings } = useApiClient()
    const response = await scrapings.start_scraping(
      props.scrapingId,
      new ScrapingStartRequest({
        chapterIndexFrom: startState.chapterIndexFrom,
        chapterIndexTo: startState.chapterIndexTo,
        refetch: startState.refetch,
        force: startState.force
      })
    )
    emit('updated', response)
    startError.value = ''
    useToast().add({
      title: expectedQueuedCount > 0 ? 'Chapter tasks queued' : 'No new tasks queued',
      description: expectedQueuedCount > 0
        ? `Queued chapter indexes ${startState.chapterIndexFrom}–${startState.chapterIndexTo}.`
        : 'The selected tasks are already queued or running.',
      icon: expectedQueuedCount > 0 ? 'lucide:play' : 'lucide:info',
      color: expectedQueuedCount > 0 ? 'success' : 'neutral'
    })
  } catch (cause) {
    startError.value = errorStatus(cause) === 503
      ? 'Some tasks could not be published. Enable force and start the range again.'
      : validationMessage(cause) || 'The selected chapter range could not be started.'
  } finally {
    starting.value = false
  }
}

async function stopQueuedTasks() {
  if (!props.detail.progress.queued) return
  stopping.value = true
  startError.value = ''
  try {
    const { scrapings } = useApiClient()
    emit('updated', await scrapings.stop_scraping(props.scrapingId))
    useToast().add({
      title: 'Queued tasks stopped',
      description: 'Running chapters will continue; queued chapters are ready to start again.',
      icon: 'lucide:square',
      color: 'neutral'
    })
  } catch {
    startError.value = 'Queued tasks could not be stopped. Please try again.'
  } finally {
    stopping.value = false
  }
}
</script>

<template>
  <div class="space-y-7">
    <UPageCard title="Start scraping chapters by index" variant="subtle">
      <div class="grid gap-4 sm:grid-cols-2 lg:grid-cols-[1fr_1fr_auto]">
        <UFormField label="Chapter Index From" name="chapterIndexFrom" required>
          <UInputNumber
            v-model="startState.chapterIndexFrom"
            :min="1"
            :step="1"
            :disabled="starting || stopping || !sortedTasks.length"
            class="w-full"
          />
        </UFormField>
        <UFormField label="Chapter Index To" name="chapterIndexTo" required>
          <UInputNumber
            v-model="startState.chapterIndexTo"
            :min="1"
            :step="1"
            :disabled="starting || stopping || !sortedTasks.length"
            class="w-full"
          />
        </UFormField>
        <div class="flex items-end gap-2">
          <UButton
            label="Start"
            icon="lucide:play"
            :loading="starting"
            :disabled="stopping || !sortedTasks.length || Boolean(startValidationError)"
            @click="startTasks"
          />
          <UButton
            label="Stop queued"
            icon="lucide:square"
            color="neutral"
            variant="soft"
            :loading="stopping"
            :disabled="starting || detail.progress.queued === 0"
            @click="stopQueuedTasks"
          />
        </div>
      </div>
      <div class="mt-4 grid gap-3 sm:grid-cols-2">
        <USwitch
          v-model="startState.refetch"
          label="Refetch chapter content"
          description="Bypass saved results and crawler caches."
          :disabled="starting || stopping"
        />
        <USwitch
          v-model="startState.force"
          label="Force active tasks"
          description="Requeue queued or running tasks; concurrent workers may race."
          :disabled="starting || stopping"
        />
      </div>
      <UAlert
        v-if="startError || startValidationError"
        class="mt-4"
        color="error"
        variant="subtle"
        icon="lucide:circle-alert"
        title="Unable to start this range"
        :description="startError || startValidationError"
      />
      <p v-else-if="hasUnnumberedTasks" class="mt-4 text-xs text-muted">
        Chapter indexes follow the source order, so additional chapters without a parsed chapter number are included in the selected range.
      </p>
      <p v-else-if="!sortedTasks.length" class="mt-4 text-xs text-muted">
        This manifest has no chapters to start.
      </p>
    </UPageCard>

    <UPageCard
      orientation="horizontal"
      reverse
      variant="naked"
      class="overflow-hidden rounded-xl border border-default bg-elevated/30"
      :ui="{
        container: 'flex flex-row items-start gap-4 p-4 sm:p-4 lg:flex lg:flex-row lg:items-start lg:gap-4',
        wrapper: 'min-w-0 p-0 sm:p-0 sm:py-0',
        title: 'line-clamp-2 text-2xl',
        description: 'line-clamp-5',
        footer: 'w-full flex flex-row flex-wrap items-center justify-between pt-2 gap-4 text-sm/6 sm:gap-6'
      }"
    >
      <div class="flex min-h-52 w-full shrink-0 items-center justify-center overflow-hidden bg-primary/10 sm:w-40">
        <img
          v-if="detail.metadata.coverImageUrl && !failedCover"
          :src="String(detail.metadata.coverImageUrl)"
          :alt="`${detail.metadata.title} cover`"
          class="h-64 w-full object-cover sm:h-full"
          @error="failedCover = true"
        >
        <UIcon v-else name="lucide:book-open" class="size-10 text-primary/70" />
      </div>
      <template #title>
        <div class="flex justify-between">
          <h1 class="text-2xl font-semibold text-highlighted">
            {{ detail.metadata.title }}
          </h1>
          <UButton
            :label="sourceLabel"
            icon="lucide:external-link"
            color="neutral"
            variant="link"
            class="h-auto p-0"
            :to="detail.sourceUrl"
            target="_blank"
            rel="noopener noreferrer"
            :aria-label="`${sourceLabel} source (opens in a new tab)`"
          />
        </div>
      </template>
      <template #description>
        <p class="text-sm/6 text-muted">
          {{ String(detail.metadata.description || 'No description available.').trim() }}
        </p>
      </template>
      <template #footer>
        <div>
          <dt class="text-muted">
            Author
          </dt><dd class="font-medium text-highlighted">
            {{ String(detail.metadata.author || 'Unknown author') }}
          </dd>
        </div>
        <div>
          <dt class="text-muted">
            Category
          </dt><dd class="font-medium text-highlighted">
            {{ String(detail.metadata.category || 'Uncategorized') }}
          </dd>
        </div>
        <div v-if="detail.metadata.protagonists?.length">
          <p class="mb-2 text-muted">
            Protagonists
          </p><div class="flex flex-wrap gap-2">
            <UBadge
              v-for="protagonist in detail.metadata.protagonists"
              :key="protagonist"
              :label="protagonist"
              color="neutral"
              variant="subtle"
            />
          </div>
        </div>
        <div>
          <dt class="text-muted">
            Source updated
          </dt><dd class="font-medium text-highlighted">
            {{ String(detail.metadata.updatedDate || 'Unknown date') }}
          </dd>
        </div>
        <div>
          <dt class="text-muted">
            Metadata fetched
          </dt><dd class="font-medium text-highlighted">
            {{ formatExactTime(detail.metadata.fetchedAt) }}
          </dd>
        </div>
      </template>
    </UPageCard>
  </div>
</template>
