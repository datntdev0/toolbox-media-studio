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
    <div class="grow border-t border-gray-200"></div>
    <span class="px-4 text-[10px] font-bold tracking-wider text-gray-400 uppercase">
      {{ label }}
    </span>
    <div class="grow border-t border-gray-200"></div>
  </div>
</template>