<template>
  <div class="flex h-screen w-full bg-surface-container overflow-hidden text-on-background">
    
    <AppSidebar />

    <div class="flex flex-col flex-1 min-w-0 overflow-hidden">
      
      <AppHeader />

      <main class="flex-1 overflow-y-auto p-6 md:p-8 bg-surface-container-low">
        
        <slot />
        
      </main>
      
    </div>
    
  </div>
</template>