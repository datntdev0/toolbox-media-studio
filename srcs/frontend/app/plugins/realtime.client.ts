export default defineNuxtPlugin(async () => {
  const auth = useAuth()
  const realtime = useRealtime()
  const config = useRuntimeConfig()

  await auth.initialize()

  watch(auth.token, (token) => {
    if (token) realtime.start(token, String(config.public.servUrl || ''))
    else realtime.stop()
  }, { immediate: true })

  window.addEventListener('beforeunload', realtime.stop, { once: true })
})
