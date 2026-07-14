<script setup>
useHead({
  title: 'StoryForge',
  
  titleTemplate: (titleChunk) => {
    return titleChunk ? `${titleChunk} - StoryForge` : 'StoryForge';
  }
})
</script>

<template>
  <NuxtRouteAnnouncer />
  <NuxtLayout>
    <NuxtPage />
  </NuxtLayout>
</template>
