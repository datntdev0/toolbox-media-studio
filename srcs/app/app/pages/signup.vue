<script setup>
definePageMeta({ layout: 'auth' })

useHead({
  title: "Sign up"
})
</script>

<template>
  <AuthSplitShell>

    <AuthTabs />

    <h2 class="font-geist text-headline-lg text-on-background mb-2">
      Create your account
    </h2>

    <p class="font-inter text-body-md text-on-surface-variant mb-8">
      Join the StoryForge pipeline and start building.
    </p>

    <AuthDivider label="Primary Access" />

    <div class="mb-8">
      <div class="grid grid-cols-2 gap-4">

        <UButton color="white" variant="solid"
          class="flex justify-center py-2.5 border border-outline-variant hover:bg-surface-container">
          <Icon name="logos:google-icon" class="h-5 w-5" />
        </UButton>

        <UButton color="white" variant="solid"
          class="flex justify-center py-2.5 border border-outline-variant hover:bg-surface-container">
          <Icon name="mdi:github" class="h-5 w-5 text-on-background" />
        </UButton>

      </div>
    </div>

    <AuthDivider label="Or Use Email" />

    <form @submit.prevent="handleSignUp" class="space-y-4">

      <AuthBaseInput id="fullName" label="Full Name" type="text" placeholder="John Doe" v-model="fullName" />

      <AuthBaseInput id="email" label="Email Address" type="email" placeholder="name@company.com" v-model="email" />

      <AuthBaseInput id="password" label="Password" type="password" placeholder="••••••••" v-model="password" />

      <AuthBaseInput id="confirmPassword" label="Confirm Password" type="password" placeholder="••••••••"
        v-model="confirmPassword" />

      <UButton type="submit" block size="lg"
        class="mt-4 bg-primary hover:bg-primary-container text-on-primary font-geist text-headline-sm py-3">
        Sign up
      </UButton>

    </form>

  </AuthSplitShell>
</template>