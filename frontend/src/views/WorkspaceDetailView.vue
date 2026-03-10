<template>
  <app-shell>
    <n-space v-if="summary" vertical size="large">
      <n-card :bordered="false" class="workspace-header">
        <n-space justify="space-between" align="start" wrap>
          <div>
            <div class="eyebrow">工作区详情</div>
            <n-h2 style="margin: 8px 0 10px">{{ workspaceName }}</n-h2>
            <n-space>
              <n-tag type="warning">{{ summary.workspace.status }}</n-tag>
              <n-tag :type="summary.workspace.workspace_type === 'openclaw' ? 'info' : 'success'">
                {{ summary.workspace.workspace_type }}
              </n-tag>
              <n-tag v-if="isBaseWorkspace" :type="activationTagType">
                {{ summary.workspace.activation_state ?? 'inactive' }}
              </n-tag>
              <n-tag v-else :type="runtimeTagType">{{ runtimeStatus?.state ?? 'unknown' }}</n-tag>
            </n-space>
            <div class="path-text">
              <n-text depth="3">{{ summary.workspace.host_path }}</n-text>
            </div>
          </div>
          <n-space vertical align="end">
            <n-input v-model:value="workspaceNameInput" placeholder="请输入工作区名称" />
            <n-button type="primary" @click="handleRename">重命名工作区</n-button>
            <n-space v-if="isBaseWorkspace">
              <n-button secondary @click="handleWorkspaceRuntimeAction('start')">激活</n-button>
              <n-button secondary @click="handleWorkspaceRuntimeAction('restart')">重启</n-button>
              <n-button tertiary @click="handleWorkspaceRuntimeAction('stop')">停用</n-button>
              <n-button quaternary @click="refreshSummary">刷新</n-button>
            </n-space>
            <n-button v-else quaternary @click="refreshSummary">刷新</n-button>
          </n-space>
        </n-space>
      </n-card>

      <template v-if="isBaseWorkspace">
        <n-grid cols="1 xl:2" responsive="screen" :x-gap="18" :y-gap="18">
          <n-grid-item>
            <n-card title="Nanobot 渠道配置" class="panel-card">
              <template #header-extra>
                <div class="card-path">
                  <n-text depth="3">{{ summary.nanobot_config?.rendered_path }}</n-text>
                </div>
              </template>
              <n-space vertical size="large">
                <n-alert
                  v-for="warning in summary.nanobot_config?.warnings || []"
                  :key="warning"
                  type="warning"
                  :show-icon="false"
                >
                  {{ warning }}
                </n-alert>
                <n-card
                  v-for="section in summary.nanobot_config?.schema.sections || []"
                  :key="section.key"
                  embedded
                  class="section-card"
                >
                  <template #header>{{ section.title }}</template>
                  <n-form :model="nanobotValues[section.key]" label-placement="top">
                    <n-grid cols="1 s:2" responsive="screen" :x-gap="12">
                      <n-grid-item v-for="field in section.fields" :key="field.key">
                        <n-form-item :label="field.label">
                          <n-switch
                            v-if="field.type === 'boolean'"
                            :value="channelBooleanValue(section.key, field.key)"
                            @update:value="updateChannelBoolean(section.key, field.key, $event)"
                          />
                          <n-input
                            v-else
                            :value="channelTextValue(section.key, field.key)"
                            @update:value="updateChannelText(section.key, field.key, $event)"
                            :type="field.type === 'password' ? 'password' : 'text'"
                            show-password-on="click"
                          />
                        </n-form-item>
                      </n-grid-item>
                    </n-grid>
                  </n-form>
                </n-card>
                <n-button type="primary" :loading="savingNanobot" @click="handleSaveNanobot">保存 Nanobot 配置</n-button>
              </n-space>
            </n-card>
          </n-grid-item>

          <n-grid-item>
            <n-space vertical size="large">
              <n-card title="Agent Defaults" class="panel-card">
                <template #header-extra>
                  <div class="card-path">
                    <n-text depth="3">{{ summary.nanobot_agent_config?.rendered_path }}</n-text>
                  </div>
                </template>
                <n-form :model="agentValues" label-placement="top">
                  <n-grid cols="1 s:2" responsive="screen" :x-gap="12">
                    <n-grid-item v-for="field in summary.nanobot_agent_config?.schema.fields || []" :key="field.key">
                      <n-form-item :label="field.label">
                        <n-select
                          v-if="field.type === 'select'"
                          :value="agentSelectValue(field.key)"
                          @update:value="updateAgentText(field.key, $event)"
                          :options="field.options?.map((value) => ({ label: value, value }))"
                        />
                        <n-input
                          v-else
                          :value="agentTextValue(field.key)"
                          @update:value="updateAgentText(field.key, $event)"
                        />
                      </n-form-item>
                    </n-grid-item>
                  </n-grid>
                  <n-button type="primary" :loading="savingAgent" @click="handleSaveAgent">保存 Agent Defaults</n-button>
                </n-form>
              </n-card>

              <n-card title="Providers 配置" class="panel-card">
                <template #header-extra>
                  <div class="card-path">
                    <n-text depth="3">{{ summary.nanobot_provider_config?.rendered_path }}</n-text>
                  </div>
                </template>
                <n-space vertical size="large">
                  <n-card
                    v-for="section in summary.nanobot_provider_config?.schema.sections || []"
                    :key="section.key"
                    embedded
                    class="section-card"
                  >
                    <template #header>{{ section.title }}</template>
                    <n-form :model="providerValues[section.key]" label-placement="top">
                      <n-grid cols="1" responsive="screen" :x-gap="12">
                        <n-grid-item v-for="field in section.fields" :key="field.key">
                          <n-form-item :label="field.label">
                            <n-input
                              :value="providerTextValue(section.key, field.key)"
                              @update:value="updateProviderText(section.key, field.key, $event)"
                              :type="field.type === 'password' ? 'password' : field.type === 'textarea' ? 'textarea' : 'text'"
                              :autosize="field.type === 'textarea' ? { minRows: 3, maxRows: 6 } : undefined"
                              :placeholder="field.placeholder"
                              show-password-on="click"
                            />
                          </n-form-item>
                        </n-grid-item>
                      </n-grid>
                    </n-form>
                  </n-card>
                  <n-button type="primary" :loading="savingProviders" @click="handleSaveProviders">保存 Providers 配置</n-button>
                </n-space>
              </n-card>

              <n-card title="实例运行状态" class="panel-card">
                <runtime-status-card :status="summary.runtime_status" />
              </n-card>
            </n-space>
          </n-grid-item>
        </n-grid>
      </template>

      <template v-else>
        <n-grid cols="1 xl:2" responsive="screen" :x-gap="18" :y-gap="18">
          <n-grid-item>
            <n-space vertical size="large">
              <n-card title="OpenClaw Agent 配置" class="panel-card">
                <template #header-extra>
                  <div class="card-path">
                    <n-text depth="3">{{ summary.openclaw_config?.rendered_path }}</n-text>
                  </div>
                </template>
                <n-form :model="openclawValues" label-placement="top">
                  <n-grid cols="1 s:2" responsive="screen" :x-gap="12">
                    <n-grid-item v-for="field in summary.openclaw_config?.schema.fields || []" :key="field.key">
                      <n-form-item :label="field.label">
                        <n-switch
                          v-if="field.type === 'boolean'"
                          :value="openclawBooleanValue(field.key)"
                          @update:value="updateOpenClawBoolean(field.key, $event)"
                        />
                        <n-input-number
                          v-else-if="field.type === 'number'"
                          :value="openclawNumberValue(field.key)"
                          @update:value="updateOpenClawNumber(field.key, $event)"
                          style="width: 100%"
                        />
                        <n-select
                          v-else-if="field.type === 'select'"
                          :value="openclawTextValue(field.key)"
                          @update:value="updateOpenClawText(field.key, $event)"
                          :options="field.options?.map((value) => ({ label: value, value }))"
                        />
                        <n-input
                          v-else
                          :value="openclawTextValue(field.key)"
                          :type="field.type === 'password' ? 'password' : field.type === 'textarea' ? 'textarea' : 'text'"
                          :autosize="field.type === 'textarea' ? { minRows: 3, maxRows: 6 } : undefined"
                          :placeholder="field.placeholder"
                          show-password-on="click"
                          @update:value="updateOpenClawText(field.key, $event)"
                        />
                      </n-form-item>
                    </n-grid-item>
                  </n-grid>
                  <n-button type="primary" :loading="savingOpenClaw" @click="handleSaveOpenClaw">保存 OpenClaw 配置</n-button>
                </n-form>
              </n-card>

              <n-card title="飞书账号路由" class="panel-card">
                <template #header-extra>
                  <div class="card-path">
                    <n-text depth="3">{{ summary.openclaw_channel_config?.rendered_path }}</n-text>
                  </div>
                </template>
                <n-form :model="openclawChannelValues" label-placement="top">
                  <n-grid cols="1 s:2" responsive="screen" :x-gap="12">
                    <n-grid-item v-for="field in summary.openclaw_channel_config?.schema.fields || []" :key="field.key">
                      <n-form-item :label="field.label">
                        <n-switch
                          v-if="field.type === 'boolean'"
                          :value="openclawChannelBooleanValue(field.key)"
                          @update:value="updateOpenClawChannelBoolean(field.key, $event)"
                        />
                        <n-input
                          v-else
                          :value="openclawChannelTextValue(field.key)"
                          :type="field.type === 'password' ? 'password' : 'text'"
                          show-password-on="click"
                          @update:value="updateOpenClawChannelText(field.key, $event)"
                        />
                      </n-form-item>
                    </n-grid-item>
                  </n-grid>
                  <n-button type="primary" :loading="savingOpenClawChannel" @click="handleSaveOpenClawChannel">
                    保存飞书账号配置
                  </n-button>
                </n-form>
              </n-card>

              <n-card title="Workspace 路由状态" class="panel-card">
                <n-descriptions label-placement="left" :column="1" bordered>
                  <n-descriptions-item label="Agent ID">{{ summary.openclaw_route?.agent_id ?? '-' }}</n-descriptions-item>
                  <n-descriptions-item label="Channel">{{ summary.openclaw_route?.channel ?? '-' }}</n-descriptions-item>
                  <n-descriptions-item label="Account ID">{{ summary.openclaw_route?.account_id ?? '-' }}</n-descriptions-item>
                  <n-descriptions-item label="Enabled">{{ summary.openclaw_route?.enabled ? 'true' : 'false' }}</n-descriptions-item>
                </n-descriptions>
              </n-card>

              <n-card title="共享 OpenClaw 服务" class="panel-card">
                <template #header-extra>
                  <n-space v-if="authStore.isAdmin.value">
                    <n-button secondary @click="handleOpenClawServiceAction('start')">启动</n-button>
                    <n-button secondary @click="handleOpenClawServiceAction('restart')">重启</n-button>
                    <n-button tertiary @click="handleOpenClawServiceAction('stop')">停止</n-button>
                  </n-space>
                </template>
                <runtime-status-card :status="summary.shared_runtime_status" />
              </n-card>
            </n-space>
          </n-grid-item>

          <n-grid-item>
            <n-card title="OpenClaw 原始 JSON5" class="panel-card">
              <n-space vertical>
                <n-input
                  v-model:value="openclawRawJson"
                  type="textarea"
                  :autosize="{ minRows: 20, maxRows: 28 }"
                  placeholder="{ model: { primary: 'gpt-4.1' } }"
                />
                <n-button type="primary" :loading="savingOpenClaw" @click="handleSaveOpenClaw">保存 OpenClaw 配置</n-button>
              </n-space>
            </n-card>
          </n-grid-item>
        </n-grid>
      </template>
    </n-space>

    <n-spin v-else size="large" />
  </app-shell>
</template>

<script setup lang="ts">
import { computed, defineComponent, h, onMounted, reactive, ref } from 'vue'
import {
  NAlert,
  NButton,
  NCard,
  NDescriptions,
  NDescriptionsItem,
  NForm,
  NFormItem,
  NGrid,
  NGridItem,
  NH2,
  NInput,
  NInputNumber,
  NSelect,
  NSpace,
  NSpin,
  NSwitch,
  NTag,
  NText,
  useMessage,
} from 'naive-ui'
import { useRoute } from 'vue-router'

import AppShell from '../components/AppShell.vue'
import {
  fetchWorkspaceSummary,
  getErrorMessage,
  restartOpenClawService,
  restartWorkspaceRuntime,
  saveAgentConfig,
  saveNanobotConfig,
  saveProviderConfig,
  saveOpenClawChannelConfig,
  saveOpenClawConfig,
  startOpenClawService,
  startWorkspaceRuntime,
  stopOpenClawService,
  stopWorkspaceRuntime,
  updateWorkspaceName,
} from '../api'
import { useAuthStore } from '../stores/auth'
import type { RuntimeStatus, WorkspaceSummary } from '../types'

const RuntimeStatusCard = defineComponent({
  name: 'RuntimeStatusCard',
  props: {
    status: {
      type: Object as () => RuntimeStatus | null | undefined,
      required: false,
      default: null,
    },
  },
  setup(props) {
    return () =>
      h(
        NDescriptions,
        { labelPlacement: 'left', column: 1, bordered: true },
        {
          default: () => [
            h(NDescriptionsItem, { label: '状态' }, { default: () => props.status?.state ?? '-' }),
            h(NDescriptionsItem, { label: '范围' }, { default: () => props.status?.scope ?? '-' }),
            h(NDescriptionsItem, { label: '控制器' }, { default: () => props.status?.controller_kind ?? '-' }),
            h(NDescriptionsItem, { label: 'Unit' }, { default: () => props.status?.unit_name ?? '-' }),
            h(NDescriptionsItem, { label: 'PID' }, { default: () => props.status?.process_id ?? '-' }),
            h(NDescriptionsItem, { label: '监听端口' }, { default: () => props.status?.listen_port ?? '-' }),
            h(NDescriptionsItem, { label: '配置文件' }, { default: () => props.status?.config_path ?? '-' }),
            h(NDescriptionsItem, { label: '工作区目录' }, { default: () => props.status?.workspace_path ?? '-' }),
            h(NDescriptionsItem, { label: '需要重启' }, { default: () => (props.status?.needs_restart ? 'true' : 'false') }),
            h(NDescriptionsItem, { label: '启动时间' }, { default: () => props.status?.started_at ?? '-' }),
            h(NDescriptionsItem, { label: '停止时间' }, { default: () => props.status?.stopped_at ?? '-' }),
            h(NDescriptionsItem, { label: '最近错误' }, { default: () => props.status?.last_error ?? '-' }),
          ],
        },
      )
  },
})

const message = useMessage()
const route = useRoute()
const authStore = useAuthStore()

const workspaceId = computed(() => Number(route.params.id))
const summary = ref<WorkspaceSummary | null>(null)
const workspaceNameInput = ref('')
const savingNanobot = ref(false)
const savingAgent = ref(false)
const savingProviders = ref(false)
const savingOpenClaw = ref(false)
const savingOpenClawChannel = ref(false)
const openclawRawJson = ref('')

const nanobotValues = reactive<Record<string, Record<string, unknown>>>({})
const agentValues = reactive<Record<string, unknown>>({})
const providerValues = reactive<Record<string, Record<string, unknown>>>({})
const openclawValues = reactive<Record<string, unknown>>({})
const openclawChannelValues = reactive<Record<string, unknown>>({})

const isBaseWorkspace = computed(() => summary.value?.workspace.workspace_type === 'base')
const workspaceName = computed(() => summary.value?.workspace.name ?? '')
const runtimeStatus = computed(() => summary.value?.runtime_status ?? null)
const activationTagType = computed(() => {
  switch (summary.value?.workspace.activation_state) {
    case 'active':
      return 'success'
    case 'error':
      return 'error'
    default:
      return 'default'
  }
})
const runtimeTagType = computed(() => {
  switch (runtimeStatus.value?.state) {
    case 'running':
    case 'configured':
      return 'success'
    case 'error':
      return 'error'
    case 'starting':
    case 'stopping':
      return 'warning'
    default:
      return 'default'
  }
})

function resetObject(target: Record<string, unknown>) {
  for (const key of Object.keys(target)) {
    delete target[key]
  }
}

function channelBooleanValue(section: string, field: string) {
  return Boolean(nanobotValues[section]?.[field])
}

function channelTextValue(section: string, field: string) {
  const value = nanobotValues[section]?.[field]
  return typeof value === 'string' ? value : ''
}

function updateChannelBoolean(section: string, field: string, value: boolean) {
  if (!nanobotValues[section]) {
    nanobotValues[section] = {}
  }
  nanobotValues[section][field] = value
}

function updateChannelText(section: string, field: string, value: string) {
  if (!nanobotValues[section]) {
    nanobotValues[section] = {}
  }
  nanobotValues[section][field] = value
}

function agentTextValue(field: string) {
  const value = agentValues[field]
  return typeof value === 'string' ? value : ''
}

function agentSelectValue(field: string) {
  const value = agentValues[field]
  return typeof value === 'string' && value.length > 0 ? value : null
}

function updateAgentText(field: string, value: string | null) {
  agentValues[field] = value ?? ''
}

function providerTextValue(section: string, field: string) {
  const value = providerValues[section]?.[field]
  return typeof value === 'string' ? value : ''
}

function updateProviderText(section: string, field: string, value: string) {
  if (!providerValues[section]) {
    providerValues[section] = {}
  }
  providerValues[section][field] = value
}

function openclawBooleanValue(field: string) {
  return Boolean(openclawValues[field])
}

function openclawNumberValue(field: string) {
  const value = openclawValues[field]
  return typeof value === 'number' ? value : null
}

function openclawTextValue(field: string) {
  const value = openclawValues[field]
  return typeof value === 'string' ? value : null
}

function updateOpenClawBoolean(field: string, value: boolean) {
  openclawValues[field] = value
}

function updateOpenClawNumber(field: string, value: number | null) {
  openclawValues[field] = value ?? 0
}

function updateOpenClawText(field: string, value: string | null) {
  openclawValues[field] = value ?? ''
}

function openclawChannelBooleanValue(field: string) {
  return Boolean(openclawChannelValues[field])
}

function openclawChannelTextValue(field: string) {
  const value = openclawChannelValues[field]
  return typeof value === 'string' ? value : ''
}

function updateOpenClawChannelBoolean(field: string, value: boolean) {
  openclawChannelValues[field] = value
}

function updateOpenClawChannelText(field: string, value: string) {
  openclawChannelValues[field] = value
}

function populateForms(nextSummary: WorkspaceSummary) {
  workspaceNameInput.value = nextSummary.workspace.name

  for (const key of Object.keys(nanobotValues)) {
    delete nanobotValues[key]
  }
  if (nextSummary.nanobot_config) {
    for (const [section, values] of Object.entries(nextSummary.nanobot_config.values)) {
      nanobotValues[section] = { ...(values as Record<string, unknown>) }
    }
  }

  resetObject(agentValues)
  if (nextSummary.nanobot_agent_config) {
    Object.assign(agentValues, nextSummary.nanobot_agent_config.values)
  }

  for (const key of Object.keys(providerValues)) {
    delete providerValues[key]
  }
  if (nextSummary.nanobot_provider_config) {
    for (const [section, values] of Object.entries(nextSummary.nanobot_provider_config.values)) {
      providerValues[section] = { ...(values as Record<string, unknown>) }
    }
  }

  resetObject(openclawValues)
  if (nextSummary.openclaw_config) {
    Object.assign(openclawValues, nextSummary.openclaw_config.values)
    openclawRawJson.value = nextSummary.openclaw_config.raw_json5
  } else {
    openclawRawJson.value = ''
  }

  resetObject(openclawChannelValues)
  if (nextSummary.openclaw_channel_config) {
    Object.assign(openclawChannelValues, nextSummary.openclaw_channel_config.values)
  }
}

async function refreshSummary() {
  try {
    const data = await fetchWorkspaceSummary(workspaceId.value)
    summary.value = data
    populateForms(data)
  } catch (error) {
    message.error(getErrorMessage(error))
  }
}

async function handleRename() {
  try {
    await updateWorkspaceName(workspaceId.value, workspaceNameInput.value)
    message.success('工作区已重命名')
    await refreshSummary()
  } catch (error) {
    message.error(getErrorMessage(error))
  }
}

async function handleSaveNanobot() {
  savingNanobot.value = true
  try {
    await saveNanobotConfig(workspaceId.value, nanobotValues)
    message.success('Nanobot 配置已保存')
    await refreshSummary()
  } catch (error) {
    message.error(getErrorMessage(error))
  } finally {
    savingNanobot.value = false
  }
}

async function handleSaveAgent() {
  savingAgent.value = true
  try {
    await saveAgentConfig(workspaceId.value, agentValues)
    message.success('Agent Defaults 已保存')
    await refreshSummary()
  } catch (error) {
    message.error(getErrorMessage(error))
  } finally {
    savingAgent.value = false
  }
}

async function handleSaveProviders() {
  savingProviders.value = true
  try {
    await saveProviderConfig(workspaceId.value, providerValues)
    message.success('Providers 配置已保存')
    await refreshSummary()
  } catch (error) {
    message.error(getErrorMessage(error))
  } finally {
    savingProviders.value = false
  }
}

async function handleSaveOpenClaw() {
  savingOpenClaw.value = true
  try {
    await saveOpenClawConfig(workspaceId.value, openclawValues, openclawRawJson.value)
    message.success('OpenClaw 配置已保存')
    await refreshSummary()
  } catch (error) {
    message.error(getErrorMessage(error))
  } finally {
    savingOpenClaw.value = false
  }
}

async function handleSaveOpenClawChannel() {
  savingOpenClawChannel.value = true
  try {
    await saveOpenClawChannelConfig(workspaceId.value, openclawChannelValues)
    message.success('飞书账号配置已保存')
    await refreshSummary()
  } catch (error) {
    message.error(getErrorMessage(error))
  } finally {
    savingOpenClawChannel.value = false
  }
}

async function handleWorkspaceRuntimeAction(action: 'start' | 'restart' | 'stop') {
  try {
    if (action === 'start') {
      await startWorkspaceRuntime(workspaceId.value)
    } else if (action === 'restart') {
      await restartWorkspaceRuntime(workspaceId.value)
    } else {
      await stopWorkspaceRuntime(workspaceId.value)
    }
    message.success(action === 'start' ? '已发送激活命令' : action === 'restart' ? '已发送重启命令' : '已发送停用命令')
    await refreshSummary()
  } catch (error) {
    message.error(getErrorMessage(error))
  }
}

async function handleOpenClawServiceAction(action: 'start' | 'restart' | 'stop') {
  try {
    if (action === 'start') {
      await startOpenClawService()
    } else if (action === 'restart') {
      await restartOpenClawService()
    } else {
      await stopOpenClawService()
    }
    message.success(action === 'start' ? '已启动共享 OpenClaw 服务' : action === 'restart' ? '已重启共享 OpenClaw 服务' : '已停止共享 OpenClaw 服务')
    await refreshSummary()
  } catch (error) {
    message.error(getErrorMessage(error))
  }
}

onMounted(async () => {
  await authStore.ensureLoaded()
  await refreshSummary()
})
</script>

<style scoped>
.path-text {
  margin-top: 12px;
}

.card-path {
  max-width: 320px;
  text-align: right;
}
</style>
