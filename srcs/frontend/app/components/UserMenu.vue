<script setup lang="ts">
import type { DropdownMenuItem } from '@nuxt/ui'

defineProps<{
  collapsed?: boolean
}>()

const colorMode = useColorMode()
const auth = useAuth()

const user = computed(() => {
  const current = auth.user.value
  const name = (current?.displayName || current?.email || 'Signed-in user') as string

  return {
    name,
    avatar: {
      alt: name
    }
  }
})

const items = computed<DropdownMenuItem[][]>(() => {
  return [
    [
      {
        type: 'label',
        label: user.value.name,
        avatar: user.value.avatar
      }
    ],
    [
      {
        label: 'Profile',
        icon: 'lucide:user',
        to: '/profile'
      },
      {
        label: 'Appearance',
        icon: 'lucide:sun-moon',
        children: [
          {
            label: 'Light',
            icon: 'lucide:sun',
            type: 'checkbox',
            checked: colorMode.value === 'light',
            onSelect(e: Event) {
              e.preventDefault()

              colorMode.preference = 'light'
            }
          },
          {
            label: 'Dark',
            icon: 'lucide:moon',
            type: 'checkbox',
            checked: colorMode.value === 'dark',
            onSelect(e: Event) {
              e.preventDefault()

              colorMode.preference = 'dark'
            }
          }
        ]
      }
    ],
    [
      {
        label: 'Documentation',
        icon: 'lucide:book-open',
        to: 'https://ui.nuxt.com/docs/getting-started/installation/nuxt',
        target: '_blank'
      },
      {
        label: 'GitHub repository',
        icon: 'simple-icons:github',
        to: 'https://github.com/datntdev0/toolbox-media-studio',
        target: '_blank'
      },
      {
        label: 'Log out',
        icon: 'lucide:log-out',
        onSelect: async () => {
          auth.logout()
          await navigateTo('/auth/signin')
        }
      }
    ]
  ]
})
</script>

<template>
  <UDropdownMenu
    :items="items"
    :content="{ align: 'center', collisionPadding: 12 }"
    :ui="{ content: collapsed ? 'w-48' : 'w-(--reka-dropdown-menu-trigger-width)' }"
  >
    <UButton
      v-bind="{
        ...user,
        label: collapsed ? undefined : user?.name,
        trailingIcon: collapsed ? undefined : 'lucide:chevrons-up-down'
      }"
      color="neutral"
      variant="ghost"
      block
      :square="collapsed"
      class="data-[state=open]:bg-elevated"
      :ui="{
        trailingIcon: 'text-dimmed'
      }"
    />

    <template #chip-leading="{ item }">
      <div class="inline-flex items-center justify-center shrink-0 size-5">
        <span
          class="rounded-full ring ring-bg bg-(--chip-light) dark:bg-(--chip-dark) size-2"
          :style="{
            '--chip-light': `var(--color-${(item as any).chip}-500)`,
            '--chip-dark': `var(--color-${(item as any).chip}-400)`
          }"
        />
      </div>
    </template>
  </UDropdownMenu>
</template>
