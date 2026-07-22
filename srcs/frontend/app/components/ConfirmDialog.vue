<script setup lang="ts">
withDefaults(defineProps<{
  title: string
  description?: string
  confirmLabel?: string
  confirmColor?: 'error' | 'primary'
}>(), {
  description: undefined,
  confirmLabel: 'Confirm',
  confirmColor: 'primary'
})

const emit = defineEmits<{ close: [confirmed: boolean] }>()
</script>

<template>
  <UModal
    :title="title"
    :description="description"
    :dismissible="false"
    :ui="{ footer: 'justify-end' }"
  >
    <template #footer>
      <UButton
        label="Cancel"
        color="neutral"
        variant="outline"
        @click="emit('close', false)"
      />
      <UButton
        :label="confirmLabel"
        :color="confirmColor"
        @click="emit('close', true)"
      />
    </template>
  </UModal>
</template>
