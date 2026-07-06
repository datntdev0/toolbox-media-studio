<script setup>
definePageMeta({ layout: 'auth' })
</script>

<template>
  <AuthSplitShell>

    <AuthTabs />

    <h2 class="text-2xl font-bold text-gray-900 mb-2">Create your account</h2>
    <p class="text-sm text-gray-600 mb-8">Join the StoryForge pipeline and start building.</p>

    <AuthDivider label="Primary Access" />
    <div class="mb-8">
      <div class="grid grid-cols-2 gap-4">

        <UButton color="white" variant="solid"
          class="flex justify-center py-2.5 border border-gray-300 hover:bg-gray-50">
          <Icon name="logos:google-icon" class="h-5 w-5" />
        </UButton>

        <UButton color="white" variant="solid"
          class="flex justify-center py-2.5 border border-gray-300 hover:bg-gray-50">
          <Icon name="mdi:github" class="h-5 w-5 text-gray-900" />
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

      <UButton type="submit" block size="lg" class="mt-4 bg-[#2563EB] hover:bg-blue-700 text-white font-semibold py-3">
        Sign up
      </UButton>

    </form>

  </AuthSplitShell>
</template>