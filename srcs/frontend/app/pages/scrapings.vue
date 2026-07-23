<script setup lang="ts">
definePageMeta({
  title: 'Scrapings'
})
</script>

<template>
  <UDashboardPanel id="scrapings">
    <template #header>
      <UDashboardNavbar title="Scrapings">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <div class="flex flex-col gap-4 sm:gap-6 lg:gap-12 w-full lg:max-w-2xl mx-auto">
        <p class="text-default">
          Scrapings page content coming soon...
        </p>
      </div>
    </template>
  </UDashboardPanel>
</template>
