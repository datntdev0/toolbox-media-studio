<script setup lang="ts">
definePageMeta({
  layout: 'auth'
})

useSeoMeta({
  title: 'Access denied',
  description: 'You do not have permission to access this page.'
})
</script>

<template>
  <div class="text-center">
    <h1 class="text-xl font-semibold">
      Access denied
    </h1>

    <p class="text-muted mt-2">
      You do not have permission to access this page.
    </p>

    <UButton
      to="/"
      label="Return home"
      block
      class="mt-6"
    />
  </div>
</template>
