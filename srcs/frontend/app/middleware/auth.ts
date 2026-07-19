export default defineNuxtRouteMiddleware(async (to) => {
  const auth = useAuth()
  await auth.initialize()

  if (!auth.isAuthenticated.value) {
    return navigateTo({
      path: '/auth/signin',
      query: { redirect: to.fullPath }
    })
  }

  const requiredRoles = to.meta.auth?.roles
  if (requiredRoles?.length && (!auth.user.value || !requiredRoles.includes(auth.user.value.role))) {
    return navigateTo('/errors/forbidden')
  }
})
