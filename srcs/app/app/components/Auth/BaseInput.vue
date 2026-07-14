<script setup>
import { ref, computed } from 'vue'

const props = defineProps({
  id: { type: String, required: true },
  label: { type: String, required: true },
  type: { type: String, default: 'text' },
  placeholder: { type: String, default: '' },
  // If a URL is passed, the "Forgot password?" link will appear
  forgotPasswordUrl: { type: String, default: null }
})

// defineModel automatically handles the two-way data binding for v-model
const model = defineModel()

// State for the password visibility toggle
const showPassword = ref(false)

// Dynamically change the input type based on the toggle state
const computedType = computed(() => {
  if (props.type === 'password') {
    return showPassword.value ? 'text' : 'password'
  }
  return props.type
})
</script>

<template>
  <div class="space-y-1">
    <div class="flex items-center justify-between">

      <label :for="id" class="block font-geist text-label-md text-on-background">
        {{ label }}
      </label>

      <NuxtLink v-if="forgotPasswordUrl" :to="forgotPasswordUrl"
        class="font-geist text-label-md text-primary hover:underline">
        Forgot password?
      </NuxtLink>
    </div>

    <UInput :id="id" :type="computedType" :placeholder="placeholder" v-model="model" size="lg" color="gray"
      variant="outline" class="w-full font-inter text-body-md">
      <template #trailing v-if="props.type === 'password'">

        <UButton color="gray" variant="link" :padded="false"
          :icon="showPassword ? 'heroicons:eye-slash' : 'heroicons:eye'" @click="showPassword = !showPassword"
          class="text-on-surface-variant hover:text-on-background transition-colors" tabindex="-1" />

      </template>
    </UInput>
  </div>
</template>