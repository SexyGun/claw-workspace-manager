<template>
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
                    style="width: 100%"
                    @update:value="updateOpenClawNumber(field.key, $event)"
                  />
                  <n-select
                    v-else-if="field.type === 'select'"
                    :value="openclawTextValue(field.key)"
                    :options="field.options?.map((value) => ({ label: value, value }))"
                    @update:value="updateOpenClawText(field.key, $event)"
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
            <n-button type="primary" :loading="savingOpenClaw" @click="emit('saveOpenClaw')">保存 OpenClaw 配置</n-button>
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
            <n-button type="primary" :loading="savingOpenClawChannel" @click="emit('saveOpenClawChannel')">
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
            <n-space v-if="isAdmin">
              <n-button secondary @click="emit('serviceAction', 'start')">启动</n-button>
              <n-button secondary @click="emit('serviceAction', 'restart')">重启</n-button>
              <n-button tertiary @click="emit('serviceAction', 'stop')">停止</n-button>
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
            :value="openclawRawJson"
            type="textarea"
            :autosize="{ minRows: 20, maxRows: 28 }"
            placeholder="{ model: { primary: 'gpt-4.1' } }"
            @update:value="emit('update:openclawRawJson', $event)"
          />
          <n-button type="primary" :loading="savingOpenClaw" @click="emit('saveOpenClaw')">保存 OpenClaw 配置</n-button>
        </n-space>
      </n-card>
    </n-grid-item>
  </n-grid>
</template>

<script setup lang="ts">
import {
  NButton,
  NCard,
  NDescriptions,
  NDescriptionsItem,
  NForm,
  NFormItem,
  NGrid,
  NGridItem,
  NInput,
  NInputNumber,
  NSelect,
  NSpace,
  NSwitch,
  NText,
} from 'naive-ui'

import type { RuntimeAction } from '../../composables/useWorkspaceDetail'
import type { WorkspaceSummary } from '../../types'
import RuntimeStatusCard from './RuntimeStatusCard.vue'

const props = defineProps<{
  isAdmin: boolean
  openclawChannelValues: Record<string, unknown>
  openclawRawJson: string
  openclawValues: Record<string, unknown>
  savingOpenClaw: boolean
  savingOpenClawChannel: boolean
  summary: WorkspaceSummary
}>()

const emit = defineEmits<{
  (event: 'saveOpenClaw'): void
  (event: 'saveOpenClawChannel'): void
  (event: 'serviceAction', action: RuntimeAction): void
  (event: 'update:openclawRawJson', value: string): void
}>()

function openclawBooleanValue(field: string) {
  return Boolean(props.openclawValues[field])
}

function openclawNumberValue(field: string) {
  const value = props.openclawValues[field]
  return typeof value === 'number' ? value : null
}

function openclawTextValue(field: string) {
  const value = props.openclawValues[field]
  return typeof value === 'string' ? value : null
}

function updateOpenClawBoolean(field: string, value: boolean) {
  props.openclawValues[field] = value
}

function updateOpenClawNumber(field: string, value: number | null) {
  props.openclawValues[field] = value ?? 0
}

function updateOpenClawText(field: string, value: string | null) {
  props.openclawValues[field] = value ?? ''
}

function openclawChannelBooleanValue(field: string) {
  return Boolean(props.openclawChannelValues[field])
}

function openclawChannelTextValue(field: string) {
  const value = props.openclawChannelValues[field]
  return typeof value === 'string' ? value : ''
}

function updateOpenClawChannelBoolean(field: string, value: boolean) {
  props.openclawChannelValues[field] = value
}

function updateOpenClawChannelText(field: string, value: string) {
  props.openclawChannelValues[field] = value
}
</script>

<style scoped>
.card-path {
  max-width: 320px;
  text-align: right;
}
</style>
