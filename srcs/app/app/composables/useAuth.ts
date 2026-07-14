export const useAuth = () => {
  const accessToken = useCookie('access-token', { maxAge: 60 * 60 * 24 * 7 })

  const config = useRuntimeConfig()

  interface LoginResponse {
    access_token: string,
  }

  interface JwtPayload {
    exp?: number
  }

  const decodeBase64Url = (value: string) => {
    const base64 = value.replace(/-/g, '+').replace(/_/g, '/')
    const paddedBase64 = base64.padEnd(base64.length + (4 - base64.length % 4) % 4, '=')

    const binaryString = globalThis.atob(paddedBase64)
    const bytes = Uint8Array.from(binaryString, character => character.charCodeAt(0))

    return new TextDecoder().decode(bytes)
  }

  const getAccessTokenPayload = (token = accessToken.value): JwtPayload | null => {
    if (!token) {
      return null
    }

    const [, payload] = token.split('.')

    if (!payload) {
      return null
    }

    try {
      return JSON.parse(decodeBase64Url(payload))
    } catch {
      return null
    }
  }

  const isAccessTokenExpired = (token = accessToken.value) => {
    const payload = getAccessTokenPayload(token)

    if (!payload?.exp) {
      return true
    }

    return payload.exp * 1000 <= Date.now()
  }

  const clearAccessToken = () => {
    accessToken.value = null
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
    clearAccessToken,
    isAccessTokenExpired,
    signIn
  }
}
