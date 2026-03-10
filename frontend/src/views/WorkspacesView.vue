<template>
  <app-shell>
    <n-space vertical size="large">
      <n-card :bordered="false" class="hero-card">
        <n-space justify="space-between" align="center" wrap>
          <div>
            <div class="eyebrow">Workspace Console</div>
            <h2>用最少点击完成工作区查看、启停和排障</h2>
            <n-text depth="3">优先显示能否使用、还缺什么和下一步动作，技术细节收进详情页的专业模式。</n-text>
          </div>
          <n-space>
            <n-button quaternary @click="void loadWorkspaces()">刷新</n-button>
            <n-button type="primary" @click="showCreate = true">新建工作区</n-button>
          </n-space>
        </n-space>
      </n-card>

      <n-card :bordered="false" class="filter-card">
        <n-space justify="space-between" align="center" wrap>
          <n-space>
            <n-button
              v-for="filter in filters"
              :key="filter.key"
              size="small"
              :type="activeFilter === filter.key ? 'primary' : 'default'"
              :secondary="activeFilter !== filter.key"
              @click="activeFilter = filter.key"
            >
              {{ filter.label }}
            </n-button>
          </n-space>
          <n-text depth="3">{{ filteredWorkspaces.length }} 个工作区</n-text>
        </n-space>
      </n-card>

      <n-grid cols="1 l:2" responsive="screen" :x-gap="18" :y-gap="18">
        <n-grid-item v-for="workspace in filteredWorkspaces" :key="workspace.id">
          <n-card :bordered="false" class="workspace-card">
            <n-space vertical size="large">
              <n-space justify="space-between" align="start">
                <div>
                  <n-space align="center">
                    <h3>{{ workspace.name }}</h3>
                    <n-tag size="small" :type="dashboardTagType(workspace.dashboard_state)">
                      {{ dashboardStateLabel(workspace.dashboard_state) }}
                    </n-tag>
                  </n-space>
                  <n-space size="small">
                    <n-tag size="small" type="info">{{ workspaceTypeLabel(workspace.workspace_type) }}</n-tag>
                    <n-tag size="small" :type="activationTagType(workspace.activation_state)">
                      {{ workspace.activation_state === 'active' ? '已启用' : workspace.activation_state === 'error' ? '异常' : '未启用' }}
                    </n-tag>
                  </n-space>
                </div>
                <n-dropdown trigger="click" :options="moreOptions(workspace)" @select="handleMoreAction(workspace, $event)">
                  <n-button quaternary>更多</n-button>
                </n-dropdown>
              </n-space>

              <n-grid cols="2" :x-gap="12" :y-gap="12">
                <n-grid-item>
                  <div class="meta-label">渠道</div>
                  <div class="meta-value">{{ workspace.channel_summary }}</div>
                </n-grid-item>
                <n-grid-item>
                  <div class="meta-label">模型</div>
                  <div class="meta-value">{{ workspace.model_summary }}</div>
                </n-grid-item>
                <n-grid-item>
                  <div class="meta-label">配置完成度</div>
                  <n-progress
                    type="line"
                    :percentage="workspace.completion_percent"
                    :indicator-placement="'inside'"
                    :height="18"
                    processing
                    :show-indicator="false"
                  />
                  <div class="meta-note">{{ workspace.completion_percent }}%</div>
                </n-grid-item>
                <n-grid-item>
                  <div class="meta-label">最近操作</div>
                  <div class="meta-value">{{ formatDateTime(workspace.last_activity_at) }}</div>
                </n-grid-item>
              </n-grid>

              <div class="path-text">{{ workspace.host_path }}</div>

              <n-space justify="space-between" align="center" wrap>
                <n-button tertiary @click="router.push(`/workspaces/${workspace.id}`)">进入管理</n-button>
                <n-space>
                  <n-button
                    :type="workspace.activation_state === 'active' ? 'default' : 'primary'"
                    :loading="pendingWorkspaceId === workspace.id"
                    @click="handleRuntimeToggle(workspace)"
                  >
                    {{ workspace.activation_state === 'active' ? '停止' : '启动' }}
                  </n-button>
                  <n-button
                    quaternary
                    :loading="pendingWorkspaceId === workspace.id"
                    @click="router.push(`/workspaces/${workspace.id}/setup`)"
                  >
                    {{ workspace.completion_percent < 100 ? '继续配置' : '重新配置' }}
                  </n-button>
                </n-space>
              </n-space>
            </n-space>
          </n-card>
        </n-grid-item>
      </n-grid>
    </n-space>

    <n-modal v-model:show="showCreate" preset="card" title="新建工作区" style="width: 480px">
      <n-form :model="form" label-placement="top">
        <n-form-item label="名称">
          <n-input v-model:value="form.name" placeholder="例如：飞书助手工作区" />
        </n-form-item>
        <n-form-item label="工作区类型">
          <n-select
            v-model:value="form.workspace_type"
            :options="workspaceTypeOptions"
            label-field="label"
            value-field="value"
          />
        </n-form-item>
        <n-alert type="info" :show-icon="false" style="margin-bottom: 16px">
          创建完成后会直接进入分步骤向导，先配模型和渠道，再决定是否启动。
        </n-alert>
        <n-text depth="3">{{ selectedWorkspaceTypeDescription }}</n-text>
        <n-button type="primary" block :loading="saving" @click="handleCreate">创建并进入向导</n-button>
      </n-form>
    </n-modal>

    <n-modal v-model:show="showRename" preset="card" title="重命名工作区" style="width: 440px">
      <n-form>
        <n-form-item label="新名称">
          <n-input v-model:value="renameInput" placeholder="请输入新的工作区名称" />
        </n-form-item>
        <n-button type="primary" block :loading="renaming" @click="handleRename">保存名称</n-button>
      </n-form>
    </n-modal>
  </app-shell>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import {
  NAlert,
  NButton,
  NCard,
  NDropdown,
  NForm,
  NFormItem,
  NGrid,
  NGridItem,
  NInput,
  NModal,
  NProgress,
  NSelect,
  NSpace,
  NTag,
  NText,
  useMessage,
} from 'naive-ui'
import { useRouter } from 'vue-router'

import AppShell from '../components/AppShell.vue'
import {
  createWorkspace,
  deleteWorkspace,
  getErrorMessage,
  listWorkspaceTypes,
  listWorkspaces,
  startWorkspaceRuntime,
  stopWorkspaceRuntime,
  updateWorkspaceName,
} from '../api'
import type { WorkspaceListItem, WorkspaceType } from '../types'
import { activationTagType, dashboardStateLabel, dashboardTagType, formatDateTime, workspaceTypeLabel } from '../utils/workspace'

const filters = [
  { key: 'all', label: '全部' },
  { key: 'running', label: '运行中' },
  { key: 'needs_setup', label: '待配置' },
  { key: 'error', label: '异常' },
  { key: 'openclaw', label: 'OpenClaw' },
  { key: 'base', label: 'Nanobot' },
] as const

const message = useMessage()
const router = useRouter()
const showCreate = ref(false)
const showRename = ref(false)
const saving = ref(false)
const renaming = ref(false)
const pendingWorkspaceId = ref<number | null>(null)
const activeFilter = ref<(typeof filters)[number]['key']>('all')
const workspaces = ref<WorkspaceListItem[]>([])
const workspaceTypes = ref<WorkspaceType[]>([])
const renameTarget = ref<WorkspaceListItem | null>(null)
const renameInput = ref('')
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

const filteredWorkspaces = computed(() => {
  switch (activeFilter.value) {
    case 'running':
    case 'needs_setup':
    case 'error':
      return workspaces.value.filter((workspace) => workspace.dashboard_state === activeFilter.value)
    case 'openclaw':
    case 'base':
      return workspaces.value.filter((workspace) => workspace.workspace_type === activeFilter.value)
    default:
      return workspaces.value
  }
})

function moreOptions(workspace: WorkspaceListItem) {
  return [
    { label: '重命名', key: 'rename' },
    { label: '查看诊断', key: 'diagnostics' },
    { label: '高级设置', key: 'advanced' },
    { label: '删除工作区', key: 'delete' },
  ]
}

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
    await loadWorkspaces()
    router.push(`/workspaces/${workspace.id}/setup`)
  } catch (error) {
    message.error(getErrorMessage(error))
  } finally {
    saving.value = false
  }
}

async function handleRuntimeToggle(workspace: WorkspaceListItem) {
  pendingWorkspaceId.value = workspace.id
  try {
    if (workspace.activation_state === 'active') {
      await stopWorkspaceRuntime(workspace.id)
      message.success('已发送停止命令')
    } else {
      await startWorkspaceRuntime(workspace.id)
      message.success('已发送启动命令')
    }
    await loadWorkspaces()
  } catch (error) {
    message.error(getErrorMessage(error))
  } finally {
    pendingWorkspaceId.value = null
  }
}

async function handleMoreAction(workspace: WorkspaceListItem, action: string | number) {
  if (action === 'rename') {
    renameTarget.value = workspace
    renameInput.value = workspace.name
    showRename.value = true
    return
  }
  if (action === 'diagnostics') {
    router.push({ path: `/workspaces/${workspace.id}`, query: { tab: 'diagnostics' } })
    return
  }
  if (action === 'advanced') {
    router.push({ path: `/workspaces/${workspace.id}`, query: { tab: 'advanced', mode: 'professional' } })
    return
  }
  if (action === 'delete') {
    const confirmed = window.confirm(`确认删除工作区“${workspace.name}”吗？此操作不可恢复。`)
    if (!confirmed) {
      return
    }
    try {
      await deleteWorkspace(workspace.id)
      message.success('工作区已删除')
      await loadWorkspaces()
    } catch (error) {
      message.error(getErrorMessage(error))
    }
  }
}

async function handleRename() {
  if (!renameTarget.value) {
    return
  }
  renaming.value = true
  try {
    await updateWorkspaceName(renameTarget.value.id, renameInput.value)
    showRename.value = false
    renameTarget.value = null
    message.success('工作区名称已更新')
    await loadWorkspaces()
  } catch (error) {
    message.error(getErrorMessage(error))
  } finally {
    renaming.value = false
  }
}

onMounted(() => {
  void loadWorkspaceTypes()
  void loadWorkspaces()
})
</script>

<style scoped>
.hero-card {
  background:
    radial-gradient(circle at top left, rgba(251, 146, 60, 0.22), transparent 32%),
    linear-gradient(135deg, rgba(7, 16, 30, 0.84), rgba(23, 37, 84, 0.64));
}

.filter-card {
  background: rgba(10, 18, 32, 0.72);
}

.workspace-card {
  min-height: 280px;
  background: rgba(11, 19, 35, 0.78);
  border: 1px solid rgba(148, 163, 184, 0.12);
}

.eyebrow {
  color: #fb923c;
  text-transform: uppercase;
  letter-spacing: 0.12em;
  font-size: 0.78rem;
}

h2,
h3 {
  margin: 0;
}

.meta-label {
  color: #94a3b8;
  font-size: 0.82rem;
  margin-bottom: 6px;
}

.meta-value {
  color: #f8fafc;
  font-weight: 600;
}

.meta-note {
  color: #94a3b8;
  font-size: 0.82rem;
  margin-top: 6px;
}

.path-text {
  color: #94a3b8;
  word-break: break-all;
}
</style>
