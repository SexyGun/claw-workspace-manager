<template>
  <app-shell>
    <n-space vertical size="large">
      <n-card :bordered="false" class="hero-card">
        <n-space justify="space-between" align="center">
          <div>
            <div class="eyebrow">Workspace inventory</div>
            <h2>All workspaces you can operate</h2>
            <n-text depth="3">Create isolated base or openclaw workspaces, then manage their config and runtime.</n-text>
          </div>
          <n-button type="primary" @click="showCreate = true">New Workspace</n-button>
        </n-space>
      </n-card>

      <n-grid cols="1 s:2 l:3" responsive="screen" :x-gap="16" :y-gap="16">
        <n-grid-item v-for="workspace in workspaces" :key="workspace.id">
          <router-link :to="`/workspaces/${workspace.id}`">
            <n-card hoverable class="workspace-card">
              <n-space justify="space-between" align="center">
                <n-tag type="warning" size="small">{{ workspace.status }}</n-tag>
                <n-tag :type="workspace.workspace_type === 'openclaw' ? 'info' : 'success'" size="small">
                  {{ workspace.workspace_type }}
                </n-tag>
              </n-space>
              <h3>{{ workspace.name }}</h3>
              <p>{{ workspace.slug }}</p>
              <n-text depth="3">{{ workspace.host_path }}</n-text>
            </n-card>
          </router-link>
        </n-grid-item>
      </n-grid>
    </n-space>

    <n-modal v-model:show="showCreate" preset="card" title="Create workspace" style="width: 460px">
      <n-form :model="form">
        <n-form-item label="Name">
          <n-input v-model:value="form.name" placeholder="Alpha Workspace" />
        </n-form-item>
        <n-form-item label="Workspace Type">
          <n-select
            v-model:value="form.workspace_type"
            :options="workspaceTypeOptions"
            label-field="label"
            value-field="value"
          />
        </n-form-item>
        <n-text depth="3">{{ selectedWorkspaceTypeDescription }}</n-text>
        <n-button type="primary" block :loading="saving" @click="handleCreate">Create</n-button>
      </n-form>
    </n-modal>
  </app-shell>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import {
  NButton,
  NCard,
  NForm,
  NFormItem,
  NGrid,
  NGridItem,
  NInput,
  NModal,
  NSelect,
  NSpace,
  NTag,
  NText,
  useMessage,
} from 'naive-ui'
import { useRouter } from 'vue-router'

import AppShell from '../components/AppShell.vue'
import { createWorkspace, getErrorMessage, listWorkspaceTypes, listWorkspaces } from '../api'
import type { Workspace, WorkspaceType } from '../types'

const message = useMessage()
const router = useRouter()
const showCreate = ref(false)
const saving = ref(false)
const workspaces = ref<Workspace[]>([])
const workspaceTypes = ref<WorkspaceType[]>([])
const form = reactive({
  name: '',
  workspace_type: 'base' as 'base' | 'openclaw',
})

const workspaceTypeOptions = computed(() =>
  workspaceTypes.value.map((type) => ({
    label: type.label,
    value: type.key,
  })),
)

const selectedWorkspaceTypeDescription = computed(() => {
  return workspaceTypes.value.find((type) => type.key === form.workspace_type)?.description ?? ''
})

async function loadWorkspaceTypes() {
  try {
    workspaceTypes.value = await listWorkspaceTypes()
  } catch (error) {
    message.error(getErrorMessage(error))
  }
}

async function loadWorkspaces() {
  try {
    workspaces.value = await listWorkspaces()
  } catch (error) {
    message.error(getErrorMessage(error))
  }
}

async function handleCreate() {
  saving.value = true
  try {
    const workspace = await createWorkspace(form.name, form.workspace_type)
    form.name = ''
    form.workspace_type = 'base'
    showCreate.value = false
    message.success('Workspace created')
    await loadWorkspaces()
    router.push(`/workspaces/${workspace.id}`)
  } catch (error) {
    message.error(getErrorMessage(error))
  } finally {
    saving.value = false
  }
}

onMounted(() => {
  void loadWorkspaceTypes()
  void loadWorkspaces()
})
</script>

<style scoped>
.hero-card {
  background: linear-gradient(140deg, rgba(251, 146, 60, 0.16), rgba(15, 23, 38, 0.72));
}

.eyebrow {
  color: #fb923c;
  text-transform: uppercase;
  letter-spacing: 0.12em;
  font-size: 0.78rem;
}

h2 {
  margin: 8px 0;
}

.workspace-card {
  min-height: 190px;
  background: rgba(15, 23, 38, 0.72);
  transition: transform 0.2s ease, border-color 0.2s ease;
}

.workspace-card:hover {
  transform: translateY(-4px);
}

.workspace-card h3 {
  margin: 14px 0 8px;
}

.workspace-card p {
  margin: 0 0 10px;
  color: #f8fafc;
}
</style>
