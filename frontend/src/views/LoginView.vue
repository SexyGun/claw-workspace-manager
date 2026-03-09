<template>
  <div class="login-shell">
    <n-card class="login-card" :bordered="false">
      <div class="eyebrow">容器化工作区控制台</div>
      <h1>登录</h1>
      <p class="subtitle">在一个面板中统一管理用户、工作区配置和网关容器。</p>
      <n-form :model="form" @submit.prevent="handleSubmit">
        <n-form-item label="用户名">
          <n-input v-model:value="form.username" placeholder="请输入用户名" />
        </n-form-item>
        <n-form-item label="密码">
          <n-input v-model:value="form.password" type="password" show-password-on="click" />
        </n-form-item>
        <n-button type="primary" block :loading="submitting" @click="handleSubmit">登录</n-button>
      </n-form>
    </n-card>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useMessage, NButton, NCard, NForm, NFormItem, NInput } from 'naive-ui'
import { useRoute, useRouter } from 'vue-router'

import { getErrorMessage } from '../api'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()
const message = useMessage()
const submitting = ref(false)
const form = reactive({
  username: '',
  password: '',
})

async function handleSubmit() {
  submitting.value = true
  try {
    await auth.login(form.username, form.password)
    router.push((route.query.redirect as string) || '/workspaces')
    message.success('登录成功')
  } catch (error) {
    message.error(getErrorMessage(error))
  } finally {
    submitting.value = false
  }
}
</script>

<style scoped>
.login-shell {
  min-height: 100vh;
  display: grid;
  place-items: center;
  padding: 24px;
}

.login-card {
  width: min(100%, 420px);
  background: linear-gradient(160deg, rgba(15, 23, 38, 0.94), rgba(30, 41, 59, 0.92));
  box-shadow: 0 24px 80px rgba(15, 23, 38, 0.38);
}

.eyebrow {
  color: #fb923c;
  text-transform: uppercase;
  letter-spacing: 0.12em;
  font-size: 0.75rem;
}

h1 {
  margin: 12px 0 8px;
  font-size: 2.4rem;
}

.subtitle {
  color: #cbd5e1;
  margin-bottom: 24px;
}
</style>
