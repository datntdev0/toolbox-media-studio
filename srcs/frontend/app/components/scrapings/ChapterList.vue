<script setup lang="ts">
import type { AccordionItem } from '@nuxt/ui'
import {
  ApiException,
  ScrapingTaskStatus,
  type ScrapingProgressResponse,
  type ScrapingResultResponse,
  type ScrapingTaskResponse
} from '~~/shared/api-services/srv-core.client'
import { formatCharacterCount } from '~/utils/character-count'
import { scrapingTaskStatusMeta } from '~/utils/scrapings'

type ChapterItem = AccordionItem & {
  task: ScrapingTaskResponse
}

const props = defineProps<{
  scrapingId: string
  tasks?: ScrapingTaskResponse[]
  progress: ScrapingProgressResponse
}>()

const emit = defineEmits<{
  refresh: []
}>()

const openTaskId = ref<string>()
const resultLoading = reactive<Record<string, boolean>>({})
const resultErrors = reactive<Record<string, string>>({})
const resultCache = useState<Record<string, ScrapingResultResponse>>(
  'scrapings:result-cache',
  () => ({})
)

const sortedTasks = computed(() => [...(props.tasks || [])]
  .sort((a, b) => a.manifestIndex - b.manifestIndex))
const chapterItems = computed<ChapterItem[]>(() => sortedTasks.value.map(task => ({
  value: task.id,
  label: chapterLabel(task),
  disabled: !task.resultAvailable,
  task,
  ui: {
    trigger: 'h-[52px] border-b border-default py-0',
    body: 'h-[468px] overflow-y-auto pb-5 pt-2'
  }
})))

watch(openTaskId, (taskId) => {
  if (taskId) void loadResult(taskId)
})

watch(() => props.tasks, (tasks) => {
  if (
    openTaskId.value
    && !tasks?.find(task => task.id === openTaskId.value && task.resultAvailable)
  ) {
    openTaskId.value = undefined
  }
}, { deep: true })

watch(() => props.scrapingId, () => {
  openTaskId.value = undefined
})

function cacheKey(taskId: string) {
  return `${props.scrapingId}:${taskId}`
}

function chapterLabel(task: ScrapingTaskResponse) {
  const title = task.title || 'Untitled chapter'
  const chapterNumber = parsedChapterNumber(task)
  if (chapterNumber === null) return title
  const number = String(chapterNumber)
  return new RegExp(`\\b${number.replace(/[.*+?^${}()|[\\]\\]/g, '\\$&')}\\b`).test(title)
    ? title
    : `Chapter ${number}: ${title}`
}

function parsedChapterNumber(task: ScrapingTaskResponse) {
  const value = task.chapterNumber as unknown
  if (typeof value === 'number' && Number.isInteger(value)) return value
  return null
}

function taskMeta(task: ScrapingTaskResponse) {
  if (task.status === ScrapingTaskStatus.Completed && !task.resultAvailable) {
    return {
      label: 'Unavailable',
      color: 'neutral' as const,
      icon: 'lucide:circle-dashed'
    }
  }
  return scrapingTaskStatusMeta[task.status]
}

function isSpinning(task: ScrapingTaskResponse) {
  return task.status === ScrapingTaskStatus.Running
}

async function loadResult(taskId: string) {
  const key = cacheKey(taskId)
  if (resultCache.value[key] || resultLoading[key]) return
  resultLoading[key] = true
  resultErrors[key] = ''

  try {
    const { scrapings } = useApiClient()
    resultCache.value[key] = await scrapings.get_scraping_result(props.scrapingId, taskId)
  } catch (cause) {
    if (cause instanceof ApiException && cause.status === 409) {
      openTaskId.value = undefined
      emit('refresh')
    } else {
      resultErrors[key] = 'This chapter could not be loaded.'
    }
  } finally {
    resultLoading[key] = false
  }
}

function resultFor(taskId: string) {
  return resultCache.value[cacheKey(taskId)]
}

function resultCharacterCount(taskId: string) {
  return formatCharacterCount(resultFor(taskId)?.content || [])
}
</script>

<template>
  <section class="flex min-h-0 flex-1 flex-col pt-1" aria-labelledby="chapters-heading" role="tabpanel">
    <div class="mb-3 flex flex-wrap items-end justify-between gap-2">
      <div>
        <h2 id="chapters-heading" class="text-lg font-semibold text-highlighted">
          Chapters
        </h2>
      </div>
    </div>
    <div v-if="chapterItems.length" class="min-h-0 flex-1 overflow-y-auto rounded-lg border border-default">
      <UAccordion
        v-model="openTaskId"
        :items="chapterItems"
        type="single"
        collapsible
        :unmount-on-hide="false"
        class="px-4"
      >
        <template #default="{ item }">
          <div class="min-w-0 flex-1 text-left">
            <p class="truncate">
              {{ item.label }}
            </p>
            <p class="truncate text-xs text-muted">
              Chapter index {{ item.task.manifestIndex + 1 }}
              <template v-if="parsedChapterNumber(item.task) === null">
                · Additional chapter
              </template>
            </p>
            <p v-if="item.task.lastError" class="truncate text-xs text-error">
              {{ String(item.task.lastError) }}
            </p>
          </div>
        </template>

        <template #leading="{ item }">
          <UIcon
            :name="taskMeta(item.task).icon"
            class="size-4 shrink-0"
            :class="[
              isSpinning(item.task) && 'motion-safe:animate-spin',
              taskMeta(item.task).color === 'success' && 'text-success',
              taskMeta(item.task).color === 'error' && 'text-error',
              taskMeta(item.task).color === 'primary' && 'text-primary',
              taskMeta(item.task).color === 'neutral' && 'text-muted'
            ]"
          />
        </template>

        <template #trailing="{ item, open }">
          <div class="ms-auto flex shrink-0 items-center gap-2">
            <UBadge
              :label="taskMeta(item.task).label"
              :color="taskMeta(item.task).color"
              variant="subtle"
              size="sm"
            />
            <UIcon
              v-if="item.task.resultAvailable"
              name="lucide:chevron-down"
              class="ms-1 size-4 shrink-0 text-muted transition-transform"
              :class="open && 'rotate-180'"
            />
          </div>
        </template>

        <template #body="{ item }">
          <div :aria-label="`${item.label} content`">
            <UAlert
              v-if="item.task.lastError"
              class="mb-4"
              color="error"
              variant="subtle"
              icon="lucide:circle-alert"
              title="Latest fetch failed"
              :description="String(item.task.lastError)"
            />
            <div
              v-if="resultLoading[cacheKey(item.task.id)]"
              class="space-y-3 py-2"
              aria-label="Loading chapter content"
            >
              <USkeleton
                v-for="index in 5"
                :key="index"
                class="h-4"
                :class="index % 2 === 0 ? 'w-11/12' : 'w-full'"
              />
            </div>

            <UAlert
              v-else-if="resultErrors[cacheKey(item.task.id)]"
              color="error"
              variant="subtle"
              icon="lucide:circle-alert"
              title="Unable to load chapter"
              :description="resultErrors[cacheKey(item.task.id)]"
              :actions="[{
                label: 'Retry',
                color: 'error',
                variant: 'soft',
                onClick: () => loadResult(item.task.id)
              }]"
            />

            <article
              v-else-if="resultFor(item.task.id)"
              class="mx-auto max-w-3xl space-y-3 py-1 text-sm/6 text-toned"
            >
              <p class="text-right text-xs tabular-nums text-muted">
                {{ resultCharacterCount(item.task.id) }} characters
              </p>
              <p
                v-for="(paragraph, index) in resultFor(item.task.id)?.content || []"
                :key="index"
              >
                {{ paragraph }}
              </p>
              <p v-if="!resultFor(item.task.id)?.content?.length" class="italic text-muted">
                This chapter has no text content.
              </p>
            </article>
          </div>
        </template>
      </UAccordion>
    </div>

    <UEmpty
      v-else
      icon="lucide:book-open"
      title="No chapters"
      description="This scraping does not contain a chapter manifest."
      variant="subtle"
      size="sm"
    />
  </section>
</template>
