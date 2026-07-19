import type {
  LoginRequest,
  UserResponse,
  UserRole
} from '~~/shared/api-services/srv-core.client'

const TOKEN_STORAGE_KEY = 'access_token'
let initializationPromise: Promise<UserResponse | null> | null = null

export function useAuth() {
  const token = useState<string | null>('auth:access-token', () => null)
  const user = useState<UserResponse | null>('auth:user', () => null)
  const initialized = useState('auth:initialized', () => false)
  const pending = useState('auth:pending', () => false)
  const api = useApiClient()

  const isAuthenticated = computed(() => !!user.value && !!token.value)

  function setToken(value: string | null) {
    token.value = value
    if (import.meta.client) {
      if (value) localStorage.setItem(TOKEN_STORAGE_KEY, value)
      else localStorage.removeItem(TOKEN_STORAGE_KEY)
    }
  }

  function clear() {
    setToken(null)
    user.value = null
  }

  async function restore() {
    if (import.meta.client && !token.value) {
      token.value = localStorage.getItem(TOKEN_STORAGE_KEY)
    }
  }

  async function fetchSession() {
    if (!token.value) {
      user.value = null
      return null
    }

    try {
      user.value = await api.auth.me()
      return user.value
    } catch {
      clear()
      return null
    }
  }

  async function initialize() {
    if (initialized.value) return user.value
    if (initializationPromise) return initializationPromise

    pending.value = true
    initializationPromise = (async () => {
      try {
        await restore()
        return await fetchSession()
      } finally {
        initialized.value = true
        pending.value = false
        initializationPromise = null
      }
    })()

    return initializationPromise
  }

  async function login(credentials: LoginRequest) {
    const response = await api.auth.login(credentials)
    setToken(response.access_token)
    await fetchSession()
    return user.value
  }

  function logout() {
    clear()
  }

  function hasRole(role: UserRole | UserRole[]) {
    if (!user.value) return false
    return Array.isArray(role) ? role.includes(user.value.role) : user.value.role === role
  }

  return {
    token,
    user,
    initialized,
    pending,
    isAuthenticated,
    initialize,
    fetchSession,
    login,
    logout,
    setToken,
    hasRole
  }
}
