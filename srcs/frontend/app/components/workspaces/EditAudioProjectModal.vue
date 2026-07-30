<script setup lang="ts">
import type { AudioWorkspace } from '~/types/audio-workspace'

const props = defineProps<{ workspace: AudioWorkspace }>()
const emit = defineEmits<{ updated: [workspace: AudioWorkspace] }>()
const open = defineModel<boolean>('open', { default: false })
const title = ref(props.workspace.title)
const submitting = ref(false)
const toast = useToast()

watch(
  () => props.workspace,
  workspace => title.value = workspace.title,
  { immediate: true }
)

async function submit() {
  const nextTitle = title.value.trim()
  if (!nextTitle || nextTitle === props.workspace.title) {
    open.value = false
    return
  }
  submitting.value = true
  try {
    const workspace = await useAudioWorkspaceApi().update(
      props.workspace.id,
      nextTitle
    )
    emit('updated', workspace)
    open.value = false
    toast.add({
      title: 'Workspace updated',
      description: `The project is now named “${workspace.title}”.`,
      color: 'success'
    })
  } catch (error) {
    toast.add({
      title: 'Unable to update workspace',
      description: error instanceof Error ? error.message : 'Please try again.',
      color: 'error'
    })
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <UModal
    v-model:open="open"
    title="Edit audio project"
    description="Only the project title can be changed after creation."
  >
    <template #body>
      <UFormField label="Project title" required>
        <UInput
          v-model="title"
          icon="lucide:folder-pen"
          class="w-full"
          autofocus
          @keydown.enter="submit"
        />
      </UFormField>
    </template>

    <template #footer>
      <div class="flex w-full justify-end gap-2">
        <UButton
          label="Cancel"
          color="neutral"
          variant="subtle"
          @click="open = false"
        />
        <UButton
          label="Save title"
          icon="lucide:save"
          :disabled="!title.trim()"
          :loading="submitting"
          @click="submit"
        />
      </div>
    </template>
  </UModal>
</template>
