<template>
  <app-shell>
    <n-space vertical size="large">
      <n-card :bordered="false">
        <n-space justify="space-between" align="center">
          <div>
            <h2>Users</h2>
            <n-text depth="3">Admin-managed local accounts for workspace access.</n-text>
          </div>
          <n-button type="primary" @click="showCreate = true">Create User</n-button>
        </n-space>
      </n-card>

      <n-data-table :columns="columns" :data="users" :loading="loading" :pagination="false" />
    </n-space>

    <n-modal v-model:show="showCreate" preset="card" title="Create user" style="width: 420px">
      <n-form :model="createForm">
        <n-form-item label="Username">
          <n-input v-model:value="createForm.username" />
        </n-form-item>
        <n-form-item label="Password">
          <n-input v-model:value="createForm.password" type="password" show-password-on="click" />
        </n-form-item>
        <n-form-item label="Role">
          <n-select v-model:value="createForm.role" :options="roleOptions" />
        </n-form-item>
        <n-button type="primary" block :loading="saving" @click="handleCreate">Save</n-button>
      </n-form>
    </n-modal>

    <n-modal v-model:show="showResetPassword" preset="card" title="Reset password" style="width: 420px">
      <n-form :model="passwordForm">
        <n-form-item label="New password">
          <n-input v-model:value="passwordForm.password" type="password" show-password-on="click" />
        </n-form-item>
        <n-button type="primary" block @click="handleResetPassword">Reset</n-button>
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
  { label: 'User', value: 'user' },
  { label: 'Admin', value: 'admin' },
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
    message.success('User created')
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
    message.success('Password reset')
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
  { title: 'Username', key: 'username' },
  { title: 'Role', key: 'role' },
  {
    title: 'Active',
    key: 'is_active',
    render: (row) =>
      h(NSwitch, {
        value: row.is_active,
        onUpdateValue: (value: boolean) => void toggleUser(row, value),
      }),
  },
  { title: 'Created', key: 'created_at' },
  {
    title: 'Actions',
    key: 'actions',
    render: (row) =>
      h(
        NButton,
        {
          tertiary: true,
          onClick: () => openResetPassword(row.id),
        },
        { default: () => 'Reset password' },
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
