<template>
  <aside class="w-64 border-r border-outline-variant bg-background flex flex-col h-full">
    
    <div class="flex flex-col items-center px-6 py-2 border-b border-outline-variant">
      <div class="flex items-center gap-2">
        <img src="/logo.svg" alt="StoryForge Logo" class="h-8 w-8" />
        <span class="font-geist text-headline-sm text-primary">StoryForge</span>
      </div>
      <div class="px-6">
        <span class="font-inter text-label-sm text-on-surface-variant">V1.0.0 - Stable</span>
      </div>
    </div>

    <nav class="flex-1 px-4 py-4 space-y-1 overflow-y-auto">
      <NuxtLink to="/dashboard" class="flex items-center gap-3 px-3 py-2 rounded-md bg-surface-container text-primary font-geist text-body-md font-medium">
        <Icon name="heroicons:squares-2x2" class="h-5 w-5" />
        Dashboard
      </NuxtLink>
      
      <NuxtLink to="/library" class="flex items-center gap-3 px-3 py-2 rounded-md text-on-surface-variant hover:bg-surface-container hover:text-on-background font-inter text-body-md transition-colors">
        <Icon name="heroicons:rectangle-stack" class="h-5 w-5" />
        Library
      </NuxtLink>
      
      <NuxtLink to="/translator" class="flex items-center gap-3 px-3 py-2 rounded-md text-on-surface-variant hover:bg-surface-container hover:text-on-background font-inter text-body-md transition-colors">
        <Icon name="heroicons:language" class="h-5 w-5" />
        Translator
      </NuxtLink>

      <NuxtLink to="/projects" class="flex items-center gap-3 px-3 py-2 rounded-md text-on-surface-variant hover:bg-surface-container hover:text-on-background font-inter text-body-md transition-colors">
        <Icon name="heroicons:folder" class="h-5 w-5" />
        Projects
      </NuxtLink>
      
      <NuxtLink to="/models" class="flex items-center gap-3 px-3 py-2 rounded-md text-on-surface-variant hover:bg-surface-container hover:text-on-background font-inter text-body-md transition-colors">
        <Icon name="heroicons:cpu-chip" class="h-5 w-5" />
        AI Models
      </NuxtLink>
    </nav>

    <div class="p-4 border-t border-outline-variant space-y-4">
      <UButton color="primary" block class="hover:bg-primary-container font-geist py-2">
        <template #leading>
          <Icon name="heroicons:plus" class="h-4 w-4 text-on-primary" />
        </template>
        <span class="text-label-md text-on-primary">Create New</span>
      </UButton>
      
      <div class="flex flex-col gap-2 px-2">
        <NuxtLink to="/help" class="flex items-center gap-2 text-on-surface-variant hover:text-primary font-inter text-label-md">
          <Icon name="heroicons:question-mark-circle" class="h-4 w-4" />
          Help
        </NuxtLink>
      </div>
    </div>

  </aside>
</template>
