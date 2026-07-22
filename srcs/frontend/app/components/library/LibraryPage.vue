<script setup lang="ts">
import type { NavigationMenuItem } from '@nuxt/ui'
import type { NovelResponse } from '~~/shared/api-services/srv-core.client'

type LibraryKind = 'novels' | 'videos'

const props = defineProps<{ kind: LibraryKind }>()
const toast = useToast()
const confirm = useConfirmDialog()
const search = ref('')

const links = [{
  label: 'Novels',
  icon: 'lucide:book-open',
  to: '/library/novels'
}, {
  label: 'Videos',
  icon: 'lucide:clapperboard',
  to: '/library/videos'
}] satisfies NavigationMenuItem[]

const novels = ref<NovelResponse[]>([])
const loading = ref(false)
const error = ref<unknown>()
const mounted = ref(false)
const editingNovel = ref<NovelResponse | null>(null)
const deletingNovelId = ref<string | null>(null)

const isEditModalOpen = computed({
  get: () => !!editingNovel.value,
  set: (value: boolean) => {
    if (!value) editingNovel.value = null
  }
})
async function loadNovels() {
  if (props.kind !== 'novels') return

  const config = useRuntimeConfig()
  if (!config.public.servUrl) {
    loading.value = false
    return
  }

  loading.value = true
  error.value = undefined
  const { novels: novelsClient } = useApiClient()
  try {
    const response = await Promise.race([
      novelsClient.list_novels(50, undefined),
      new Promise<never>((_, reject) => {
        setTimeout(() => reject(new Error('Novel request timed out')), 8000)
      })
    ])
    novels.value = response?.items ?? []
  } catch (cause) {
    error.value = cause
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  mounted.value = true
  void loadNovels()
})

watch(() => props.kind, () => {
  if (mounted.value) void loadNovels()
})

const filteredNovels = computed(() => {
  const query = search.value.trim().toLowerCase()
  if (!query) return novels.value

  return novels.value.filter((novel) => {
    const author = readObjectValue(novel.author)
    return [novel.title, novel.description, author, ...(novel.tags ?? [])]
      .filter(Boolean)
      .some(value => String(value).toLowerCase().includes(query))
  })
})

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

function formatDate(value?: Date) {
  if (!value) return ''
  return new Intl.DateTimeFormat(undefined, { month: 'short', year: 'numeric' }).format(new Date(value))
}

function onNovelCreated(novel: NovelResponse) {
  novels.value = [novel, ...novels.value.filter(item => item.id !== novel.id)]
}

function onNovelUpdated(novel: NovelResponse) {
  novels.value = novels.value.map(item => item.id === novel.id ? novel : item)
}

function onNovelDeleted(id: string) {
  novels.value = novels.value.filter(novel => novel.id !== id)
}

async function deleteNovel(novel: NovelResponse) {
  const confirmed = await confirm({
    title: 'Delete novel',
    description: `Remove “${novel.title}” from your library? This cannot be undone.`,
    confirmLabel: 'Delete novel',
    confirmColor: 'error'
  })
  if (!confirmed) return

  deletingNovelId.value = novel.id
  try {
    const { novels: novelsClient } = useApiClient()
    await novelsClient.delete_novel(novel.id)
    onNovelDeleted(novel.id)
    toast.add({ title: 'Novel deleted', description: `“${novel.title}” has been removed.`, color: 'success' })
  } catch {
    toast.add({ title: 'Unable to delete novel', description: 'Please check the library service and try again.', color: 'error' })
  } finally {
    deletingNovelId.value = null
  }
}
</script>

<template>
  <UDashboardPanel id="library">
    <template #header>
      <UDashboardNavbar title="Library">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>

        <template #right>
          <LibraryCreateNovelModal v-if="kind === 'novels'" @created="onNovelCreated" />
          <UButton
            v-else
            label="New video"
            icon="lucide:plus"
            disabled
          />
        </template>
      </UDashboardNavbar>

      <UDashboardToolbar>
        <UNavigationMenu :items="links" highlight class="-mx-1 flex-1" />
      </UDashboardToolbar>
    </template>

    <template #body>
      <div class="flex flex-col gap-6">
        <UPageCard
          :title="kind === 'novels' ? 'Novels' : 'Videos'"
          :description="kind === 'novels' ? 'Browse and manage the stories in your library.' : 'Keep your video library close at hand.'"
          variant="naked"
          class="mb-0"
        />

        <div class="flex flex-col gap-3 border-b border-default pb-4 sm:flex-row sm:items-center sm:justify-between">
          <UInput
            v-model="search"
            icon="lucide:search"
            :placeholder="`Search ${kind}...`"
            class="w-full sm:max-w-sm"
          />
          <p class="text-sm text-muted">
            {{ kind === 'novels' ? `${filteredNovels.length} ${filteredNovels.length === 1 ? 'novel' : 'novels'}` : 'Your video collection' }}
          </p>
        </div>

        <UAlert
          v-if="error"
          color="error"
          variant="subtle"
          icon="lucide:circle-alert"
          title="Unable to load novels"
          description="Please try again when the library service is available."
        />

        <div v-else-if="kind === 'videos'" class="flex min-h-64 flex-col items-center justify-center rounded-xl border border-dashed border-default bg-elevated/20 px-6 text-center">
          <UIcon name="lucide:clapperboard" class="mb-3 size-10 text-dimmed" />
          <h2 class="font-semibold text-highlighted">
            No videos yet
          </h2>
          <p class="mt-1 max-w-sm text-sm text-muted">
            Create a video to start building your media library.
          </p>
        </div>

        <div v-else-if="loading" class="grid grid-cols-1 sm:grid-cols-1 lg:grid-cols-1 xl:grid-cols-2 gap-4 gap-4">
          <USkeleton v-for="index in 4" :key="index" class="h-48 rounded-xl" />
        </div>

        <UPageGrid v-else-if="filteredNovels.length" class="grid-cols-1 sm:grid-cols-1 lg:grid-cols-1 xl:grid-cols-2 gap-4">
          <UPageCard
            v-for="novel in filteredNovels"
            :key="novel.id"
            :title="novel.title"
            :description="display(novel.description, 'No description available.')"
            orientation="horizontal"
            reverse
            variant="subtle"
            class="min-h-64 overflow-hidden"
            :ui="{
              wrapper: 'min-w-0',
              container: 'flex flex-row items-center gap-4 p-4 sm:p-4 lg:flex lg:flex-row lg:items-center lg:gap-4',
              title: 'line-clamp-2',
              description: 'line-clamp-5'
            }"
          >
            <img
              v-if="display(novel.coverImageUrl, '')"
              :src="display(novel.coverImageUrl, '')"
              :alt="`${novel.title} cover`"
              class="h-full min-h-64 w-48 object-cover"
            >
            <div v-else class="flex min-h-64 w-48 items-center justify-center bg-primary/10">
              <UIcon name="lucide:book-open" class="size-8 text-primary/60" />
            </div>
            <div class="absolute top-3 right-3 z-10 flex items-center gap-1 rounded-md bg-default/80 p-0.5 shadow-sm backdrop-blur">
              <UButton
                icon="lucide:pencil"
                color="neutral"
                variant="ghost"
                size="sm"
                square
                aria-label="Edit novel"
                @click="editingNovel = novel"
              />
              <UButton
                icon="lucide:trash-2"
                color="error"
                variant="ghost"
                size="sm"
                square
                aria-label="Delete novel"
                :loading="deletingNovelId === novel.id"
                @click="deleteNovel(novel)"
              />
            </div>
            <template #footer>
              <div class="flex flex-wrap items-center gap-2 text-xs text-muted">
                <UBadge
                  v-if="novel.status"
                  :label="novel.status"
                  variant="subtle"
                  class="capitalize"
                />
                <span v-if="display(novel.author, '')">{{ display(novel.author, '') }}</span>
                <span v-if="display(novel.language, '')">{{ display(novel.language, '') }}</span>
                <span v-if="novel.updatedAt">Updated {{ formatDate(novel.updatedAt) }}</span>
              </div>
            </template>
          </UPageCard>
        </UPageGrid>

        <div v-else class="flex min-h-64 flex-col items-center justify-center rounded-xl border border-dashed border-default bg-elevated/20 px-6 text-center">
          <UIcon name="lucide:book-open" class="mb-3 size-10 text-dimmed" />
          <h2 class="font-semibold text-highlighted">
            {{ search ? 'No novels found' : 'No novels yet' }}
          </h2>
          <p class="mt-1 max-w-sm text-sm text-muted">
            {{ search ? 'Try a different search term.' : 'Create a novel to start building your library.' }}
          </p>
        </div>

        <LibraryEditNovelModal
          v-if="editingNovel"
          v-model:open="isEditModalOpen"
          :novel="editingNovel"
          @updated="onNovelUpdated"
        />
      </div>
    </template>
  </UDashboardPanel>
</template>
