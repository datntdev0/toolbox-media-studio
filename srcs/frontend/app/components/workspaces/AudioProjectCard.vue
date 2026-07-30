<script setup lang="ts">
import type { AudioWorkspace } from '~/types/audio-workspace'
import { formatWorkspaceDate } from '~/utils/translation-workspaces'
import { resolveLanguage } from '~/constants/supported-languages'

const props = defineProps<{ workspace: AudioWorkspace }>()
const emit = defineEmits<{
  edit: [workspace: AudioWorkspace]
  delete: [workspace: AudioWorkspace]
}>()

const language = computed(() => resolveLanguage(props.workspace.language))
</script>

<template>
  <UPageCard
    orientation="horizontal"
    reverse
    variant="subtle"
    class="relative min-h-48 overflow-hidden"
    :ui="{
      wrapper: 'min-w-0',
      container: 'flex flex-row items-stretch gap-3 p-3 sm:p-3 lg:flex lg:flex-row lg:items-stretch lg:gap-3',
      title: 'line-clamp-2',
      description: 'line-clamp-2',
      body: 'w-full',
      footer: 'w-full'
    }"
  >
    <div class="flex min-h-48 w-24 shrink-0 items-center justify-center overflow-hidden bg-primary/10 sm:w-32">
      <img
        v-if="workspace.novel?.coverImageUrl"
        :src="workspace.novel.coverImageUrl"
        :alt="`${workspace.novel.title} cover`"
        class="size-full object-cover"
      >
      <UIcon v-else name="lucide:audio-lines" class="size-9 text-primary/65" />
    </div>

    <template #title>
      <NuxtLink
        :to="`/workspaces/audios/${workspace.id}`"
        class="after:absolute after:inset-0 hover:text-primary focus-visible:outline-2 focus-visible:outline-primary"
      >
        {{ workspace.title }}
      </NuxtLink>
    </template>

    <template #description>
      <div class="space-y-3">
        <p class="truncate text-sm font-medium text-toned">
          {{ workspace.novel?.title || 'Novel unavailable' }}
        </p>
        <div class="flex flex-wrap gap-2">
          <UBadge
            label="Audio"
            icon="lucide:audio-lines"
            color="neutral"
            variant="subtle"
          />
          <UBadge
            :label="workspace.sourceType === 'original' ? 'Original' : 'Translated'"
            :icon="workspace.sourceType === 'original' ? 'lucide:book-open' : 'lucide:languages'"
            variant="subtle"
          />
          <UBadge
            v-if="!workspace.sourceAvailable"
            label="Source unavailable"
            icon="lucide:circle-alert"
            color="warning"
            variant="subtle"
          />
        </div>
        <dl class="grid grid-cols-2 gap-3 text-sm">
          <div>
            <dt class="text-xs text-muted">
              Language
            </dt>
            <dd class="mt-0.5 truncate font-medium text-toned">
              {{ workspace.language === 'original' ? 'Original' : language.label }}
            </dd>
          </div>
          <div>
            <dt class="text-xs text-muted">
              Chapters
            </dt>
            <dd class="mt-0.5 font-medium text-toned">
              {{ workspace.chapterCount }}
            </dd>
          </div>
        </dl>
      </div>
    </template>

    <template #footer>
      <div class="text-xs text-muted">
        Updated {{ formatWorkspaceDate(workspace.updatedAt) }}
      </div>
    </template>

    <div class="absolute top-3 right-3 z-10 flex items-center gap-1 rounded-md bg-default/80 p-0.5 shadow-sm backdrop-blur">
      <UTooltip text="Edit workspace title">
        <UButton
          icon="lucide:pencil"
          color="neutral"
          variant="ghost"
          size="sm"
          square
          aria-label="Edit workspace title"
          @click="emit('edit', workspace)"
        />
      </UTooltip>
      <UTooltip text="Delete workspace">
        <UButton
          icon="lucide:trash-2"
          color="error"
          variant="ghost"
          size="sm"
          square
          aria-label="Delete workspace"
          @click="emit('delete', workspace)"
        />
      </UTooltip>
    </div>
  </UPageCard>
</template>
