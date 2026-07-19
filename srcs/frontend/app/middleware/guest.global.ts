export default defineNuxtRouteMiddleware(async (to) => {
  if (to.path !== '/auth/signin' && to.path !== '/auth/signup') {
    return
  }

  const auth = useAuth()
  await auth.initialize()

  if (auth.isAuthenticated.value) {
    return navigateTo('/')
  }
})
