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

    <h2 class="text-2xl font-bold text-gray-900 mb-2">Welcome back</h2>
    <p class="text-sm text-gray-600 mb-8">Continue to your workspace pipeline.</p>

    <AuthDivider label="Primary Access" />

    <div class="space-y-3 mb-8">
      <AuthSocialButton variant="google" text="Continue with Google" />
      <AuthSocialButton variant="github" text="Continue with GitHub" />
    </div>

    <AuthDivider label="Or Use Email" />

    <form @submit.prevent="handleSignIn" class="space-y-4">

      <<AuthBaseInput id="email" label="Email Address" type="email" placeholder="name@company.com" v-model="email" />

      <AuthBaseInput id="password" label="Password" type="password" placeholder="••••••••"
        forgot-password-url="/forgot-password" v-model="password" />

      <UButton type="submit" block size="lg" class="mt-4 bg-[#2563EB] hover:bg-blue-700 text-white font-semibold py-3">
        Sign in
      </UButton>
    </form>

  </AuthSplitShell>
</template>