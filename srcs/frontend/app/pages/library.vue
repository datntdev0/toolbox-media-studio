<script setup lang="ts">
import { UserRole } from '~~/shared/api-services/srv-core.client'

definePageMeta({
  middleware: 'auth',
  auth: { roles: [UserRole.Admin] }
})
</script>

<template>
  <NuxtPage />
</template>
