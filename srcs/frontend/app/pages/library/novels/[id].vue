<script setup lang="ts">
import type { NovelResponse } from '~~/shared/api-services/srv-core.client'

definePageMeta({
  key: route => route.fullPath
})

const route = useRoute()
const novel = ref<NovelResponse | null>(null)
const loading = ref(true)
const error = ref<unknown>()

const novelId = computed(() => String(route.params.id))

function readObjectValue(value: unknown) {
  if (!value) return ''
  if (typeof value === 'string') return value
  if (typeof value !== 'object') return String(value)
  const record = value as Record<string, unknown>
  return String(record.name ?? record.value ?? record.text ?? Object.values(record).find(item => typeof item === 'string') ?? '')
}

function display(value: unknown, fallback: string) {
  return readObjectValue(value) || fallback
}

async function loadNovel() {
  const config = useRuntimeConfig()
  if (!config.public.servUrl || !novelId.value) {
    loading.value = false
    return
  }

  loading.value = true
  error.value = undefined

  try {
    const { novels } = useApiClient()
    novel.value = await Promise.race([
      novels.get_novel(novelId.value),
      new Promise<never>((_, reject) => {
        setTimeout(() => reject(new Error('Novel request timed out')), 8000)
      })
    ])
  } catch (cause) {
    error.value = cause
  } finally {
    loading.value = false
  }
}

onMounted(() => void loadNovel())
watch(novelId, () => void loadNovel())

useHead(() => ({
  title: novel.value?.title ? `Library > Novel > ${novel.value.title}` : 'Novel'
}))
</script>

<template>
  <UDashboardPanel id="novel-detail">
    <template #header>
      <UDashboardNavbar :title="`Library > Novel > ${novel?.title || 'Novel'}`">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>

        <template #right>
          <UButton
            label="Back"
            icon="lucide:arrow-left"
            to="/library/novels"
            variant="outline"
          />
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <div class="flex flex-col gap-6">
        <USkeleton v-if="loading" class="h-64 rounded-xl" />

        <UAlert
          v-else-if="error || !novel"
          color="error"
          variant="subtle"
          icon="lucide:circle-alert"
          title="Unable to load novel"
          description="Please return to the library and try again."
        />

        <UPageCard
          v-else
          :title="novel.title"
          :description="display(novel.description, 'No description available.')"
          orientation="horizontal"
          reverse
          variant="naked"
          class="min-h-64 overflow-hidden"
          :ui="{
            wrapper: 'min-w-0',
            container: 'flex flex-row items-center gap-4 p-4 sm:p-4 lg:flex lg:flex-row lg:items-center lg:gap-4',
            title: 'line-clamp-2 text-2xl',
            description: 'line-clamp-5'
          }"
        >
          <img
            v-if="display(novel.coverImageUrl, '')"
            :src="display(novel.coverImageUrl, '')"
            :alt="`${novel.title} cover`"
            class="h-full min-h-64 w-48 object-cover"
          >
          <div v-else class="flex min-h-64 w-48 shrink-0 items-center justify-center bg-primary/10">
            <UIcon name="lucide:book-open" class="size-8 text-primary/60" />
          </div>

          <template #title>
            <h1 class="text-2xl font-semibold text-highlighted">
              {{ novel.title }}
            </h1>
          </template>

          <template #footer>
            <div class="flex flex-col gap-4 text-sm">
              <div class="grid gap-3 sm:grid-cols-2">
                <div>
                  <p class="text-muted">
                    Author
                  </p>
                  <p class="font-medium text-highlighted">
                    {{ display(novel.author, 'Unknown author') }}
                  </p>
                </div>
                <div>
                  <p class="text-muted">
                    Language
                  </p>
                  <p class="font-medium text-highlighted">
                    {{ display(novel.language, 'Unknown language') }}
                  </p>
                </div>
              </div>

              <div v-if="novel.tags?.length" class="flex flex-wrap gap-2">
                <UBadge
                  v-for="tag in novel.tags"
                  :key="tag"
                  :label="tag"
                  variant="subtle"
                />
              </div>
            </div>
          </template>
        </UPageCard>
      </div>
    </template>
  </UDashboardPanel>
</template>
