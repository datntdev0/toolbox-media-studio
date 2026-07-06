<template>
  <div class="grid min-h-screen grid-cols-1 lg:grid-cols-2">
    
    <div class="relative hidden bg-slate-900 lg:flex lg:flex-col lg:justify-between p-12 text-white">
      <div>
        </div>
      <div class="z-10">
        <h1 class="text-3xl font-bold mb-4">Architect your masterpiece with precision.</h1>
        <p class="text-gray-300">The high-performance environment for structured storytelling...</p>
      </div>
      <div>
        </div>
    </div>

    <div class="flex items-center justify-center p-8 sm:p-12 lg:p-24 bg-white">
      <div class="mx-auto w-full max-w-100">
        <slot /> 
      </div>
    </div>

  </div>
</template>