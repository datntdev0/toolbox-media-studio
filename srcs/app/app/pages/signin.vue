<script setup>
import { ref } from 'vue'

definePageMeta({ layout: 'auth' })

const router = useRouter()

const { signIn } = useAuth()

const email = ref('')
const password = ref('')
const isLoading = ref(false)
const errorMessage = ref('')

const handleSignIn = async () => {
  errorMessage.value = ''
  isLoading.value = true

  const result = await signIn(email.value, password.value)

  if (result.success) {
    router.push('/dashboard')
  } else {
    errorMessage.value = result.message
  }

  isLoading.value = false
}
</script>

<template>
  <AuthSplitShell>

    <AuthTabs />

    <h2 class="font-geist text-headline-lg text-on-background mb-2">
      Welcome back
    </h2>

    <p class="font-inter text-body-md text-on-surface-variant mb-8">
      Continue to your workspace pipeline.
    </p>

    <AuthDivider label="Primary Access" />

    <div class="space-y-3 mb-8">
      <AuthSocialButton variant="google" text="Continue with Google" />
      <AuthSocialButton variant="github" text="Continue with GitHub" />
    </div>

    <AuthDivider label="Or Use Email" />

    <form @submit.prevent="handleSignIn" class="space-y-4">

      <AuthBaseInput id="email" label="Email Address" type="email" placeholder="name@company.com" v-model="email" />

      <AuthBaseInput id="password" label="Password" type="password" placeholder="••••••••"
        forgot-password-url="/forgot-password" v-model="password" />

      <UButton type="submit" block size="lg"
        class="mt-4 bg-primary hover:bg-primary-container text-on-primary font-geist text-headline-sm py-3">
        Sign in
      </UButton>

    </form>

  </AuthSplitShell>
</template>