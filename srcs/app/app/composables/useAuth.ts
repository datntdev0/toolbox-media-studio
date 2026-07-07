export const useAuth = () => {
  const accessToken = useCookie('access-token', { maxAge: 60 * 60 * 24 * 7 })

  const config = useRuntimeConfig()

  interface LoginResponse {
    access_token: string,
  }

  const signIn = async (email: string, password: string) => {
    try {
      const response = await $fetch<LoginResponse>('/auth/login', {
        baseURL: config.public.apiBase,
        method: 'POST',
        body: { email, password }
      })

      // Store the returned data
      accessToken.value = response.access_token

      return { success: true }
    } catch (error: any) {
      const message = error.data?.message || error.data?.detail || 'Invalid email or password.'
      
      return { 
        success: false, 
        message: message 
      }
    }
  }

  return {
    accessToken,
    signIn
  }
}
