export default defineNuxtPlugin(async () => {
  await useAuth().initialize()
})
