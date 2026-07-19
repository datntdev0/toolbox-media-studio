<script setup lang="ts">
import * as z from 'zod'
import type { FormSubmitEvent } from '@nuxt/ui'
import { LoginRequest } from '~~/shared/api-services/srv-core.client'

definePageMeta({
  layout: 'auth'
})

useSeoMeta({
  title: 'Sign in',
  description: 'Sign in to your account to continue'
})

const toast = useToast()
const auth = useAuth()
const route = useRoute()
const isSubmitting = ref(false)

const fields = [{
  name: 'email',
  type: 'text' as const,
  label: 'Email',
  placeholder: 'Enter your email',
  required: true
}, {
  name: 'password',
  label: 'Password',
  type: 'password' as const,
  placeholder: 'Enter your password',
  required: true
}, {
  name: 'remember',
  label: 'Remember me',
  type: 'checkbox' as const
}]

const providers = [{
  label: 'Google',
  icon: 'i-simple-icons-google',
  onClick: () => {
    toast.add({ title: 'Google', description: 'Sign in with Google' })
  }
}, {
  label: 'GitHub',
  icon: 'i-simple-icons-github',
  onClick: () => {
    toast.add({ title: 'GitHub', description: 'Sign in with GitHub' })
  }
}]

const schema = z.object({
  email: z.email('Invalid email'),
  password: z.string().min(8, 'Must be at least 8 characters'),
  remember: z.boolean().optional()
})

type Schema = z.output<typeof schema>

async function onSubmit(payload: FormSubmitEvent<Schema>) {
  if (isSubmitting.value) return

  isSubmitting.value = true
  try {
    await auth.login(new LoginRequest({
      email: payload.data.email,
      password: payload.data.password
    }))

    toast.add({
      title: 'Signed in',
      description: 'Welcome back.',
      color: 'success'
    })

    const redirect = typeof route.query.redirect === 'string' && route.query.redirect.startsWith('/')
      ? route.query.redirect
      : '/'
    await navigateTo(redirect)
  } catch (error: unknown) {
    const caught = error as {
      response?: { data?: { detail?: string } }
      message?: string
    }
    const description = caught.response?.data?.detail
      ?? caught.message
      ?? 'The email or password is incorrect.'

    toast.add({
      title: 'Unable to sign in',
      description,
      color: 'error'
    })
  } finally {
    isSubmitting.value = false
  }
}
</script>

<template>
  <UAuthForm
    :fields="fields"
    :schema="schema"
    :providers="providers"
    :loading="isSubmitting"
    title="Welcome back"
    icon="i-lucide-lock"
    @submit="onSubmit"
  >
    <template #description>
      Don't have an account?
      <ULink
        to="/auth/signup"
        class="text-primary font-medium"
      >
        Sign up
      </ULink>.
    </template>

    <template #password-hint>
      <ULink
        to="/"
        class="text-primary font-medium"
        tabindex="-1"
      >
        Forgot password?
      </ULink>
    </template>

    <template #footer>
      By signing in, you agree to our
      <ULink
        to="/"
        class="text-primary font-medium"
      >
        Terms of Service
      </ULink>.
    </template>
  </UAuthForm>
</template>
