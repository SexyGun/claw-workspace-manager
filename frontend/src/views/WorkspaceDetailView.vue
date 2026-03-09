<template>
  <app-shell>
    <n-space vertical size="large" v-if="summary">
      <n-card :bordered="false" class="workspace-header">
        <n-space justify="space-between" align="start" wrap>
          <div>
            <div class="eyebrow">Workspace detail</div>
            <n-h2 style="margin: 8px 0 10px">{{ workspaceName }}</n-h2>
            <n-space>
              <n-tag type="warning">{{ summary.workspace.status }}</n-tag>
              <n-tag :type="gatewayTagType">{{ summary.gateway_status.state }}</n-tag>
            </n-space>
            <n-text depth="3">{{ summary.workspace.host_path }}</n-text>
          </div>
          <n-space vertical align="end">
            <n-input v-model:value="workspaceName" placeholder="Workspace name" />
            <n-button type="primary" @click="handleRename">Rename Workspace</n-button>
            <n-space>
              <n-button secondary @click="handleGatewayAction('start')">Start</n-button>
              <n-button secondary @click="handleGatewayAction('restart')">Restart</n-button>
              <n-button tertiary @click="handleGatewayAction('stop')">Stop</n-button>
              <n-button quaternary @click="refreshSummary">Refresh</n-button>
            </n-space>
          </n-space>
        </n-space>
      </n-card>

      <n-grid cols="1 xl:2" responsive="screen" :x-gap="18" :y-gap="18">
        <n-grid-item>
          <n-card title="Nanobot Channel Config" class="panel-card">
            <template #header-extra>
              <n-text depth="3">{{ summary.nanobot_config.rendered_path }}</n-text>
            </template>
            <n-space vertical size="large">
              <n-card
                v-for="section in summary.nanobot_config.schema.sections"
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
              <n-button type="primary" :loading="savingNanobot" @click="handleSaveNanobot">Save Nanobot Config</n-button>
            </n-space>
          </n-card>
        </n-grid-item>

        <n-grid-item>
          <n-space vertical size="large">
            <n-card title="Gateway Config" class="panel-card">
              <template #header-extra>
                <n-text depth="3">{{ summary.gateway_config.rendered_path }}</n-text>
              </template>
              <n-form :model="gatewayValues" label-placement="top">
                <n-grid cols="1 s:2" responsive="screen" :x-gap="12">
                  <n-grid-item v-for="field in summary.gateway_config.schema.fields" :key="field.key">
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
                <n-button type="primary" :loading="savingGateway" @click="handleSaveGateway">Save Gateway Config</n-button>
              </n-form>
            </n-card>

            <n-card title="Gateway Runtime" class="panel-card">
              <n-descriptions label-placement="left" :column="1" bordered>
                <n-descriptions-item label="State">{{ summary.gateway_status.state }}</n-descriptions-item>
                <n-descriptions-item label="Container">{{ summary.gateway_status.container_name }}</n-descriptions-item>
                <n-descriptions-item label="Container ID">{{ summary.gateway_status.last_container_id || '-' }}</n-descriptions-item>
                <n-descriptions-item label="Started">{{ summary.gateway_status.started_at || '-' }}</n-descriptions-item>
                <n-descriptions-item label="Stopped">{{ summary.gateway_status.stopped_at || '-' }}</n-descriptions-item>
                <n-descriptions-item label="Last Error">{{ summary.gateway_status.last_error || '-' }}</n-descriptions-item>
              </n-descriptions>
            </n-card>
          </n-space>
        </n-grid-item>
      </n-grid>
    </n-space>

    <n-spin v-else size="large" />
  </app-shell>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
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
  saveGatewayConfig,
  saveNanobotConfig,
  startGateway,
  stopGateway,
  updateWorkspaceName,
} from '../api'
import type { WorkspaceSummary } from '../types'

const message = useMessage()
const route = useRoute()
const workspaceId = computed(() => Number(route.params.id))
const summary = ref<WorkspaceSummary | null>(null)
const workspaceName = ref('')
const savingNanobot = ref(false)
const savingGateway = ref(false)
const nanobotValues = reactive<Record<string, Record<string, string | boolean>>>({})
const gatewayValues = reactive<Record<string, string | number | boolean>>({})

const gatewayTagType = computed(() => {
  switch (summary.value?.gateway_status.state) {
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

function hydrateForms(payload: WorkspaceSummary) {
  workspaceName.value = payload.workspace.name
  for (const [section, values] of Object.entries(payload.nanobot_config.values)) {
    nanobotValues[section] = { ...(values as Record<string, string | boolean>) }
  }
  for (const key of Object.keys(gatewayValues)) {
    delete gatewayValues[key]
  }
  Object.assign(gatewayValues, payload.gateway_config.values)
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
    message.success('Workspace renamed')
    await refreshSummary()
  } catch (error) {
    message.error(getErrorMessage(error))
  }
}

async function handleSaveNanobot() {
  savingNanobot.value = true
  try {
    await saveNanobotConfig(workspaceId.value, nanobotValues)
    message.success('Nanobot config saved')
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
    message.success('Gateway config saved')
    await refreshSummary()
  } catch (error) {
    message.error(getErrorMessage(error))
  } finally {
    savingGateway.value = false
  }
}

async function handleGatewayAction(action: 'start' | 'stop' | 'restart') {
  try {
    if (action === 'start') {
      await startGateway(workspaceId.value)
    } else if (action === 'stop') {
      await stopGateway(workspaceId.value)
    } else {
      await restartGateway(workspaceId.value)
    }
    message.success(`Gateway ${action} command sent`)
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

.panel-card {
  background: rgba(15, 23, 38, 0.72);
}

.section-card {
  background: rgba(30, 41, 59, 0.6);
}
</style>
