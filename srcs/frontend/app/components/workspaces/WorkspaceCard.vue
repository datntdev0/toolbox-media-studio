<script setup lang="ts">
import type { TranslationWorkspace } from '~/types/translation-workspace'
import {
  formatWorkspaceDate,
  workspaceStatusMeta
} from '~/utils/translation-workspaces'

const props = defineProps<{ workspace: TranslationWorkspace }>()

const status = computed(() => workspaceStatusMeta[props.workspace.status])
const configuredModel = computed(() => props.workspace.configuration
  ? `${props.workspace.configuration.providerName} · ${props.workspace.configuration.modelName}`
  : 'AI not configured'
)
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
      description: 'line-clamp-2'
    }"
  >
    <div class="flex min-h-48 w-24 shrink-0 items-center justify-center overflow-hidden bg-primary/10 sm:w-32">
      <img
        v-if="workspace.coverImageUrl"
        :src="workspace.coverImageUrl"
        :alt="`${workspace.novelTitle} cover`"
        class="size-full object-cover"
      >
      <UIcon v-else name="lucide:book-open" class="size-9 text-primary/65" />
    </div>

    <template #title>
      <NuxtLink
        :to="`/workspaces/${workspace.id}`"
        class="after:absolute after:inset-0 hover:text-primary focus-visible:outline-2 focus-visible:outline-primary"
      >
        {{ workspace.novelTitle }}
      </NuxtLink>
    </template>

    <template #description>
      <div class="space-y-2.5">
        <div class="flex flex-wrap gap-2">
          <UBadge
            label="Translation"
            icon="lucide:languages"
            color="neutral"
            variant="subtle"
          />
          <UBadge
            :label="workspace.targetLanguage.label"
            icon="lucide:globe-2"
            variant="subtle"
          />
          <UBadge
            :label="status.label"
            :icon="status.icon"
            :color="status.color"
            variant="subtle"
            :ui="workspace.status === 'running' ? { leadingIcon: 'animate-spin' } : undefined"
          />
        </div>

        <div>
          <p class="text-xs text-muted">
            AI model
          </p>
          <p class="mt-0.5 truncate text-sm font-medium text-toned">
            {{ configuredModel }}
          </p>
        </div>

        <div class="space-y-1.5">
          <div class="flex items-center justify-between gap-3 text-xs text-muted">
            <span>Translation progress</span>
            <span class="tabular-nums">
              {{ workspace.progress.translated }} / {{ workspace.progress.total }} chapters
            </span>
          </div>
          <UProgress
            :model-value="workspace.progress.translated"
            :max="Math.max(workspace.progress.total, 1)"
            size="xs"
          />
        </div>
      </div>
    </template>

    <template #footer>
      <div class="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted">
        <span>{{ workspace.sourceLanguage.label }} → {{ workspace.targetLanguage.label }}</span>
        <span>Updated {{ formatWorkspaceDate(workspace.updatedAt) }}</span>
      </div>
    </template>
  </UPageCard>
</template>
