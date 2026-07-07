export default defineNuxtRouteMiddleware((to, from) => {
  const accessToken = useCookie('access-token')
  if (to.path === '/') {
    console.log(accessToken)
    if (accessToken.value) {
      return navigateTo('/dashboard')
    } else {
      return navigateTo('/signin')
    }
  }

  const isAuthPage = to.path === '/signin' || to.path === '/signup'

  if (accessToken.value && isAuthPage) {
    return navigateTo('/dashboard')
  }

  if (!accessToken.value && !isAuthPage) {
    return navigateTo('/signin')
  }
})