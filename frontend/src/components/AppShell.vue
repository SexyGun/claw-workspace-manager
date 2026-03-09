<template>
  <n-layout position="absolute" class="app-shell">
    <n-layout-header bordered class="shell-header">
      <div class="brand">
        <span class="brand-mark">Claw</span>
        <span class="brand-text">工作区管理器</span>
      </div>
      <n-space align="center">
        <n-button quaternary :type="route.path.startsWith('/workspaces') ? 'primary' : 'default'" @click="router.push('/workspaces')">
          工作区
        </n-button>
        <n-button
          v-if="auth.isAdmin.value"
          quaternary
          :type="route.path.startsWith('/users') ? 'primary' : 'default'"
          @click="router.push('/users')"
        >
          用户
        </n-button>
        <n-text depth="3">{{ auth.currentUser.value?.username }}</n-text>
        <n-button secondary @click="handleLogout">退出登录</n-button>
      </n-space>
    </n-layout-header>
    <n-layout-content content-style="padding: 24px; max-width: 1180px; margin: 0 auto;">
      <slot />
    </n-layout-content>
  </n-layout>
</template>

<script setup lang="ts">
import { useMessage, NButton, NLayout, NLayoutContent, NLayoutHeader, NSpace, NText } from 'naive-ui'
import { useRoute, useRouter } from 'vue-router'

import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()
const message = useMessage()

async function handleLogout() {
  await auth.logout()
  message.success('已退出登录')
  router.push('/login')
}
</script>

<style scoped>
.app-shell {
  background: transparent;
}

.shell-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 24px;
  backdrop-filter: blur(16px);
  background: rgba(15, 23, 38, 0.72);
}

.brand {
  display: flex;
  align-items: baseline;
  gap: 10px;
}

.brand-mark {
  font-family: "Space Grotesk", sans-serif;
  font-weight: 700;
  font-size: 1.4rem;
  color: #f97316;
}

.brand-text {
  color: #cbd5e1;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  font-size: 0.82rem;
}
</style>
