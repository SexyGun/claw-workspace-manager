<template>
  <app-shell>
    <n-space vertical size="large" v-if="summary">
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
              <n-tag :type="runtimeTagType">{{ runtimeStatus?.state ?? 'unknown' }}</n-tag>
            </n-space>
            <div class="path-text">
              <n-text depth="3">{{ summary.workspace.host_path }}</n-text>
            </div>
          </div>
          <n-space vertical align="end">
            <n-input v-model:value="workspaceName" placeholder="请输入工作区名称" />
            <n-button type="primary" @click="handleRename">重命名工作区</n-button>
            <n-space>
              <n-button secondary @click="handleRuntimeAction('start')">启动</n-button>
              <n-button secondary @click="handleRuntimeAction('restart')">重启</n-button>
              <n-button tertiary @click="handleRuntimeAction('stop')">停止</n-button>
              <n-button quaternary @click="refreshSummary">刷新</n-button>
            </n-space>
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
              <n-card title="Gateway 配置" class="panel-card">
                <template #header-extra>
                  <div class="card-path">
                    <n-text depth="3">{{ summary.gateway_config?.rendered_path }}</n-text>
                  </div>
                </template>
                <n-form :model="gatewayValues" label-placement="top">
                  <n-grid cols="1 s:2" responsive="screen" :x-gap="12">
                    <n-grid-item v-for="field in summary.gateway_config?.schema.fields || []" :key="field.key">
                      <n-form-item :label="field.label">
                        <n-switch
                          v-if="field.type === 'boolean'"
                          :value="gatewayBooleanValue(field.key)"
                          @update:value="updateGatewayBoolean(field.key, $event)"
                        />
                        <n-input-number
                          v-else-if="field.type === 'number'"
                          :value="gatewayNumberValue(field.key)"
                          @update:value="updateGatewayNumber(field.key, $event)"
                          style="width: 100%"
                        />
                        <n-select
                          v-else-if="field.type === 'select'"
                          :value="gatewayTextValue(field.key)"
                          @update:value="updateGatewayText(field.key, $event)"
                          :options="field.options?.map((value) => ({ label: value, value }))"
                        />
                        <n-input
                          v-else
                          :value="gatewayTextValue(field.key)"
                          @update:value="updateGatewayText(field.key, $event)"
                        />
                      </n-form-item>
                    </n-grid-item>
                  </n-grid>
                  <n-button type="primary" :loading="savingGateway" @click="handleSaveGateway">保存 Gateway 配置</n-button>
                </n-form>
              </n-card>

              <n-card title="Gateway 运行状态" class="panel-card">
                <runtime-status-card :status="summary.gateway_status" />
              </n-card>
            </n-space>
          </n-grid-item>
        </n-grid>
      </template>

      <template v-else>
        <n-grid cols="1 xl:2" responsive="screen" :x-gap="18" :y-gap="18">
          <n-grid-item>
            <n-space vertical size="large">
              <n-card title="OpenClaw 结构化配置" class="panel-card">
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
                </n-form>
              </n-card>

              <n-card title="OpenClaw 运行状态" class="panel-card">
                <runtime-status-card :status="summary.openclaw_status" />
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
                  placeholder="{ gateway: { port: 7331 } }"
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
  restartGateway,
  restartOpenClaw,
  saveGatewayConfig,
  saveNanobotConfig,
  saveOpenClawConfig,
  startGateway,
  startOpenClaw,
  stopGateway,
  stopOpenClaw,
  updateWorkspaceName,
} from '../api'
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
            h(NDescriptionsItem, { label: '容器名称' }, { default: () => props.status?.container_name ?? '-' }),
            h(NDescriptionsItem, { label: '容器 ID' }, { default: () => props.status?.last_container_id ?? '-' }),
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
const workspaceId = computed(() => Number(route.params.id))
const summary = ref<WorkspaceSummary | null>(null)
const workspaceName = ref('')
const savingNanobot = ref(false)
const savingGateway = ref(false)
const savingOpenClaw = ref(false)
const openclawRawJson = ref('')
const nanobotValues = reactive<Record<string, Record<string, string | boolean>>>({})
const gatewayValues = reactive<Record<string, string | number | boolean>>({})
const openclawValues = reactive<Record<string, string | number | boolean>>({})

const isBaseWorkspace = computed(() => summary.value?.workspace.workspace_type === 'base')
const runtimeStatus = computed(() => {
  if (!summary.value) {
    return null
  }
  return isBaseWorkspace.value ? summary.value.gateway_status ?? null : summary.value.openclaw_status ?? null
})

const runtimeTagType = computed(() => {
  switch (runtimeStatus.value?.state) {
    case 'running':
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

function clearRecord(target: Record<string, unknown>) {
  for (const key of Object.keys(target)) {
    delete target[key]
  }
}

function channelBooleanValue(sectionKey: string, fieldKey: string): boolean {
  return Boolean(nanobotValues[sectionKey]?.[fieldKey])
}

function channelTextValue(sectionKey: string, fieldKey: string): string {
  const value = nanobotValues[sectionKey]?.[fieldKey]
  return typeof value === 'string' ? value : ''
}

function updateChannelBoolean(sectionKey: string, fieldKey: string, value: boolean) {
  if (!nanobotValues[sectionKey]) {
    nanobotValues[sectionKey] = {}
  }
  nanobotValues[sectionKey][fieldKey] = value
}

function updateChannelText(sectionKey: string, fieldKey: string, value: string) {
  if (!nanobotValues[sectionKey]) {
    nanobotValues[sectionKey] = {}
  }
  nanobotValues[sectionKey][fieldKey] = value
}

function gatewayBooleanValue(fieldKey: string): boolean {
  return Boolean(gatewayValues[fieldKey])
}

function gatewayNumberValue(fieldKey: string): number | null {
  const value = gatewayValues[fieldKey]
  return typeof value === 'number' ? value : null
}

function gatewayTextValue(fieldKey: string): string | null {
  const value = gatewayValues[fieldKey]
  return typeof value === 'string' ? value : null
}

function updateGatewayBoolean(fieldKey: string, value: boolean) {
  gatewayValues[fieldKey] = value
}

function updateGatewayNumber(fieldKey: string, value: number | null) {
  gatewayValues[fieldKey] = value ?? 0
}

function updateGatewayText(fieldKey: string, value: string | null) {
  gatewayValues[fieldKey] = value ?? ''
}

function openclawBooleanValue(fieldKey: string): boolean {
  return Boolean(openclawValues[fieldKey])
}

function openclawNumberValue(fieldKey: string): number | null {
  const value = openclawValues[fieldKey]
  return typeof value === 'number' ? value : null
}

function openclawTextValue(fieldKey: string): string | null {
  const value = openclawValues[fieldKey]
  return typeof value === 'string' ? value : null
}

function updateOpenClawBoolean(fieldKey: string, value: boolean) {
  openclawValues[fieldKey] = value
}

function updateOpenClawNumber(fieldKey: string, value: number | null) {
  openclawValues[fieldKey] = value ?? 0
}

function updateOpenClawText(fieldKey: string, value: string | null) {
  openclawValues[fieldKey] = value ?? ''
}

function hydrateForms(payload: WorkspaceSummary) {
  workspaceName.value = payload.workspace.name

  for (const key of Object.keys(nanobotValues)) {
    delete nanobotValues[key]
  }
  if (payload.nanobot_config) {
    for (const [section, values] of Object.entries(payload.nanobot_config.values)) {
      nanobotValues[section] = { ...(values as Record<string, string | boolean>) }
    }
  }

  clearRecord(gatewayValues)
  if (payload.gateway_config) {
    Object.assign(gatewayValues, payload.gateway_config.values)
  }

  clearRecord(openclawValues)
  if (payload.openclaw_config) {
    Object.assign(openclawValues, payload.openclaw_config.values)
    openclawRawJson.value = payload.openclaw_config.raw_json5
  } else {
    openclawRawJson.value = ''
  }
}

async function refreshSummary() {
  try {
    const payload = await fetchWorkspaceSummary(workspaceId.value)
    summary.value = payload
    hydrateForms(payload)
  } catch (error) {
    message.error(getErrorMessage(error))
  }
}

async function handleRename() {
  try {
    await updateWorkspaceName(workspaceId.value, workspaceName.value)
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

async function handleSaveGateway() {
  savingGateway.value = true
  try {
    await saveGatewayConfig(workspaceId.value, gatewayValues)
    message.success('Gateway 配置已保存')
    await refreshSummary()
  } catch (error) {
    message.error(getErrorMessage(error))
  } finally {
    savingGateway.value = false
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

async function handleRuntimeAction(action: 'start' | 'stop' | 'restart') {
  try {
    if (isBaseWorkspace.value) {
      if (action === 'start') {
        await startGateway(workspaceId.value)
      } else if (action === 'stop') {
        await stopGateway(workspaceId.value)
      } else {
        await restartGateway(workspaceId.value)
      }
    } else {
      if (action === 'start') {
        await startOpenClaw(workspaceId.value)
      } else if (action === 'stop') {
        await stopOpenClaw(workspaceId.value)
      } else {
        await restartOpenClaw(workspaceId.value)
      }
    }
    message.success(
      action === 'start' ? '已发送启动命令' : action === 'stop' ? '已发送停止命令' : '已发送重启命令',
    )
    await refreshSummary()
  } catch (error) {
    message.error(getErrorMessage(error))
  }
}

onMounted(() => {
  void refreshSummary()
})
</script>

<style scoped>
.workspace-header {
  background: linear-gradient(135deg, rgba(14, 165, 233, 0.16), rgba(15, 23, 38, 0.7));
}

.eyebrow {
  color: #fbbf24;
  text-transform: uppercase;
  letter-spacing: 0.12em;
  font-size: 0.78rem;
}

.path-text,
.card-path {
  max-width: 100%;
  overflow-wrap: anywhere;
  word-break: break-word;
}

.panel-card {
  background: rgba(15, 23, 38, 0.72);
}

.panel-card :deep(.n-card-header) {
  align-items: flex-start;
  flex-wrap: wrap;
  gap: 8px 12px;
}

.panel-card :deep(.n-card-header__main) {
  min-width: 0;
  flex: 0 1 auto;
}

.panel-card :deep(.n-card-header__extra) {
  min-width: 0;
  flex: 1 1 100%;
  max-width: 100%;
}

.section-card {
  background: rgba(30, 41, 59, 0.6);
}
</style>
