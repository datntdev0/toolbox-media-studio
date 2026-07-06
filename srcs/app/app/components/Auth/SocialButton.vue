<script setup>
import { computed } from 'vue'

const props = defineProps({
  text: {
    type: String,
    required: true
  },
  variant: {
    type: String,
    required: true,
    validator: (value) => ['google', 'github', 'apple'].includes(value)
  }
})

const buttonConfig = computed(() => {
  switch (props.variant) {
    case 'google':
      return {
        iconName: 'logos:google-icon',
        color: 'blue',
        variant: 'solid',
        class: 'bg-[#0A4BCC] hover:bg-blue-700 text-white flex justify-center'
      }
    case 'github':
      return {
        iconName: 'mdi:github',
        color: 'gray',
        variant: 'solid',
        class: 'bg-[#1A1A1A] hover:bg-black text-white flex justify-center'
      }
    case 'apple':
      return {
        color: 'white',
        variant: 'solid',
        class: 'border border-gray-300 hover:bg-gray-50 text-gray-900 flex justify-center'
      }
  }
})
</script>

<template>
  <UButton 
    block 
    size="lg" 
    v-bind="buttonConfig"
  >
    <template #leading>
      <Icon :name="buttonConfig.iconName" class="h-5 w-5" />
    </template>
    
    {{ text }}
  </UButton>
</template>