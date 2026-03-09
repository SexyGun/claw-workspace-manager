<template>
  <app-shell>
    <n-space vertical size="large">
      <n-card :bordered="false">
        <n-space justify="space-between" align="center">
          <div>
            <h2>用户管理</h2>
            <n-text depth="3">由管理员维护本地账号，用于访问工作区。</n-text>
          </div>
          <n-button type="primary" @click="showCreate = true">新建用户</n-button>
        </n-space>
      </n-card>

      <n-data-table :columns="columns" :data="users" :loading="loading" :pagination="false" />
    </n-space>

    <n-modal v-model:show="showCreate" preset="card" title="新建用户" style="width: 420px">
      <n-form :model="createForm">
        <n-form-item label="用户名">
          <n-input v-model:value="createForm.username" />
        </n-form-item>
        <n-form-item label="密码">
          <n-input v-model:value="createForm.password" type="password" show-password-on="click" />
        </n-form-item>
        <n-form-item label="角色">
          <n-select v-model:value="createForm.role" :options="roleOptions" />
        </n-form-item>
        <n-button type="primary" block :loading="saving" @click="handleCreate">保存</n-button>
      </n-form>
    </n-modal>

    <n-modal v-model:show="showResetPassword" preset="card" title="重置密码" style="width: 420px">
      <n-form :model="passwordForm">
        <n-form-item label="新密码">
          <n-input v-model:value="passwordForm.password" type="password" show-password-on="click" />
        </n-form-item>
        <n-button type="primary" block @click="handleResetPassword">确认重置</n-button>
      </n-form>
    </n-modal>
  </app-shell>
</template>

<script setup lang="ts">
import { h, onMounted, reactive, ref } from 'vue'
import {
  NButton,
  NCard,
  NDataTable,
  NForm,
  NFormItem,
  NInput,
  NModal,
  NSelect,
  NSpace,
  NSwitch,
  NText,
  useMessage,
  type DataTableColumns,
} from 'naive-ui'

import AppShell from '../components/AppShell.vue'
import { createUser, getErrorMessage, listUsers, resetPassword, updateUser } from '../api'
import type { User } from '../types'

const message = useMessage()
const loading = ref(false)
const saving = ref(false)
const showCreate = ref(false)
const showResetPassword = ref(false)
const resetUserId = ref<number | null>(null)
const users = ref<User[]>([])
const createForm = reactive({
  username: '',
  password: '',
  role: 'user' as 'admin' | 'user',
  is_active: true,
})
const passwordForm = reactive({
  password: '',
})

const roleOptions = [
  { label: '普通用户', value: 'user' },
  { label: '管理员', value: 'admin' },
]

async function loadUsers() {
  loading.value = true
  try {
    users.value = await listUsers()
  } catch (error) {
    message.error(getErrorMessage(error))
  } finally {
    loading.value = false
  }
}

async function handleCreate() {
  saving.value = true
  try {
    await createUser(createForm)
    message.success('用户创建成功')
    showCreate.value = false
    createForm.username = ''
    createForm.password = ''
    createForm.role = 'user'
    await loadUsers()
  } catch (error) {
    message.error(getErrorMessage(error))
  } finally {
    saving.value = false
  }
}

async function handleResetPassword() {
  if (!resetUserId.value) {
    return
  }
  try {
    await resetPassword(resetUserId.value, passwordForm.password)
    message.success('密码已重置')
    showResetPassword.value = false
    passwordForm.password = ''
  } catch (error) {
    message.error(getErrorMessage(error))
  }
}

async function toggleUser(user: User, nextValue: boolean) {
  try {
    await updateUser(user.id, { is_active: nextValue })
    await loadUsers()
  } catch (error) {
    message.error(getErrorMessage(error))
  }
}

function openResetPassword(userId: number) {
  resetUserId.value = userId
  passwordForm.password = ''
  showResetPassword.value = true
}

const columns: DataTableColumns<User> = [
  { title: '用户名', key: 'username' },
  { title: '角色', key: 'role' },
  {
    title: '启用',
    key: 'is_active',
    render: (row) =>
      h(NSwitch, {
        value: row.is_active,
        onUpdateValue: (value: boolean) => void toggleUser(row, value),
      }),
  },
  { title: '创建时间', key: 'created_at' },
  {
    title: '操作',
    key: 'actions',
    render: (row) =>
      h(
        NButton,
        {
          tertiary: true,
          onClick: () => openResetPassword(row.id),
        },
        { default: () => '重置密码' },
      ),
  },
]

onMounted(() => {
  void loadUsers()
})
</script>

<style scoped>
h2 {
  margin: 0 0 8px;
}
</style>
