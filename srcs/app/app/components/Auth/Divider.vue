<script setup>
defineProps({
  label: {
    type: String,
    required: true
  }
})
</script>

<template>
  <div class="flex items-center mb-6">
    <div class="grow border-t border-outline-variant"></div>
    <span class="px-4 uppercase font-geist text-label-sm text-on-surface-variant">
      {{ label }}
    </span>
    <div class="grow border-t border-outline-variant"></div>
  </div>
</template>