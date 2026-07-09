<template>
  <header class="h-16 border-b border-outline-variant bg-background flex items-center justify-between px-6 shrink-0">
    
    <div class="w-96">
      <UInput 
        icon="heroicons:magnifying-glass"
        placeholder="Search pipeline..." 
        variant="outline"
        class="font-inter text-body-md"
       />
    </div>

    <div class="flex items-center gap-4">
      <UButton variant="outline" class="font-geist text-label-md border-outline-variant text-on-background">
        Export
      </UButton>
      
      <UButton variant="ghost" icon="heroicons:bell" class="text-on-surface-variant hover:text-on-background" />
      
      <UAvatar src="" alt="User Avatar" size="sm" class="cursor-pointer" />
    </div>

  </header>
</template>