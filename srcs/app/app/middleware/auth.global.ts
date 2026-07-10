export default defineNuxtRouteMiddleware((to, from) => {
  const { accessToken, clearAccessToken, isAccessTokenExpired } = useAuth()
  const isAuthPage = to.path === '/signin' || to.path === '/signup'

  if (accessToken.value && isAccessTokenExpired()) {
    clearAccessToken()
  }

  if (to.path === '/') {
    if (accessToken.value) {
      return navigateTo('/dashboard')
    } else {
      return navigateTo('/signin')
    }
  }

  if (accessToken.value && isAuthPage) {
    return navigateTo('/dashboard')
  }

  if (!accessToken.value && !isAuthPage) {
    return navigateTo({
      path: '/signin',
      query: {
        redirect: to.fullPath
      }
    })
  }
})
