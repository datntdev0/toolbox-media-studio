<template>
  <div class="flex gap-6 border-b border-outline-variant mb-8">
    
    <NuxtLink 
      to="/signin" 
      class="pb-2 font-geist text-label-md text-on-surface-variant hover:text-on-background transition-colors"
      active-class="!text-on-background border-b-2 border-primary"
    >
      Sign In
    </NuxtLink>
    
    <NuxtLink 
      to="/signup" 
      class="pb-2 font-geist text-label-md text-on-surface-variant hover:text-on-background transition-colors"
      active-class="!text-on-background border-b-2 border-primary"
    >
      Sign Up
    </NuxtLink>
    
  </div>
</template>