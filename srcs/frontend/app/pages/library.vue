<script setup lang="ts">
definePageMeta({
  title: 'Library'
})
</script>

<template>
  <UDashboardPanel id="library">
    <template #header>
      <UDashboardNavbar title="Library">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <div class="flex flex-col gap-4 sm:gap-6 lg:gap-12 w-full lg:max-w-2xl mx-auto">
        <p class="text-default">Library page content coming soon...</p>
      </div>
    </template>
  </UDashboardPanel>
</template>
