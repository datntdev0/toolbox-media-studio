<template>
  <div class="grid min-h-screen grid-cols-1 lg:grid-cols-2 bg-background">
    
    <div class="relative hidden bg-inverse-surface lg:flex lg:flex-col lg:justify-between p-12 text-inverse-on-surface">
      <div>
        </div>
      
      <div class="z-10">
        <h1 class="font-geist text-headline-lg mb-4">
          Architect your masterpiece with precision.
        </h1>
        <p class="font-inter text-body-md text-inverse-on-surface/80">
          The high-performance environment for structured storytelling...
        </p>
      </div>
      
      <div>
        </div>
    </div>

    <div class="flex items-center justify-center p-8 sm:p-12 lg:p-24 bg-background">
      <div class="mx-auto w-full max-w-100">
        <slot /> 
      </div>
    </div>

  </div>
</template>