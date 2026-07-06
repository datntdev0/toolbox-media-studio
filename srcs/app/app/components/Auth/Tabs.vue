<template>
  <div class="flex gap-6 border-b border-gray-200 mb-8">
    <NuxtLink 
      to="/signin" 
      class="pb-2 text-sm font-medium text-gray-500 hover:text-gray-900 transition-colors"
      active-class="!text-gray-900 font-semibold border-b-2 border-blue-600"
    >
      Sign In
    </NuxtLink>
    
    <NuxtLink 
      to="/signup" 
      class="pb-2 text-sm font-medium text-gray-500 hover:text-gray-900 transition-colors"
      active-class="!text-gray-900 font-semibold border-b-2 border-blue-600"
    >
      Sign Up
    </NuxtLink>
  </div>
</template>