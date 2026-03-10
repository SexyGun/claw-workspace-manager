<template>
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
                      :type="field.type === 'password' ? 'password' : 'text'"
                      show-password-on="click"
                      @update:value="updateChannelText(section.key, field.key, $event)"
                    />
                  </n-form-item>
                </n-grid-item>
              </n-grid>
            </n-form>
          </n-card>
          <n-button type="primary" :loading="savingNanobot" @click="emit('saveNanobot')">保存 Nanobot 配置</n-button>
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
                    :options="field.options?.map((value) => ({ label: value, value }))"
                    @update:value="updateAgentText(field.key, $event)"
                  />
                  <n-input
                    v-else
                    :value="agentTextValue(field.key)"
                    @update:value="updateAgentText(field.key, $event)"
                  />
                </n-form-item>
              </n-grid-item>
            </n-grid>
            <n-button type="primary" :loading="savingAgent" @click="emit('saveAgent')">保存 Agent Defaults</n-button>
          </n-form>
        </n-card>

        <n-card title="Providers 配置" class="panel-card">
          <template #header-extra>
            <div class="card-path">
              <n-text depth="3">{{ summary.nanobot_provider_config?.rendered_path }}</n-text>
            </div>
          </template>
          <n-space vertical size="large">
            <n-form-item label="Provider">
              <n-select
                :value="selectedProviderKey"
                :options="providerOptions"
                @update:value="emit('update:selectedProviderKey', $event)"
              />
            </n-form-item>
            <n-card v-if="selectedProviderSection" :key="selectedProviderSection.key" embedded class="section-card">
              <template #header>{{ selectedProviderSection.title }}</template>
              <n-form :model="providerValues[selectedProviderSection.key]" label-placement="top">
                <n-grid cols="1" responsive="screen" :x-gap="12">
                  <n-grid-item v-for="field in selectedProviderSection.fields" :key="field.key">
                    <n-form-item :label="field.label">
                      <n-input
                        :value="providerTextValue(selectedProviderSection.key, field.key)"
                        :type="field.type === 'password' ? 'password' : field.type === 'textarea' ? 'textarea' : 'text'"
                        :autosize="field.type === 'textarea' ? { minRows: 3, maxRows: 6 } : undefined"
                        :placeholder="field.placeholder"
                        show-password-on="click"
                        @update:value="updateProviderText(selectedProviderSection.key, field.key, $event)"
                      />
                    </n-form-item>
                  </n-grid-item>
                </n-grid>
              </n-form>
            </n-card>
            <n-button type="primary" :loading="savingProviders" @click="emit('saveProviders')">保存 Providers 配置</n-button>
          </n-space>
        </n-card>

        <n-card title="实例运行状态" class="panel-card">
          <runtime-status-card :status="summary.runtime_status" />
        </n-card>
      </n-space>
    </n-grid-item>
  </n-grid>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import {
  NAlert,
  NButton,
  NCard,
  NForm,
  NFormItem,
  NGrid,
  NGridItem,
  NInput,
  NSelect,
  NSpace,
  NSwitch,
  NText,
} from 'naive-ui'

import type { WorkspaceSummary } from '../../types'
import RuntimeStatusCard from './RuntimeStatusCard.vue'

const props = defineProps<{
  agentValues: Record<string, unknown>
  nanobotValues: Record<string, Record<string, unknown>>
  providerValues: Record<string, Record<string, unknown>>
  savingAgent: boolean
  savingNanobot: boolean
  savingProviders: boolean
  selectedProviderKey: string | null
  summary: WorkspaceSummary
}>()

const emit = defineEmits<{
  (event: 'saveAgent'): void
  (event: 'saveNanobot'): void
  (event: 'saveProviders'): void
  (event: 'update:selectedProviderKey', value: string | null): void
}>()

const providerOptions = computed(() =>
  (props.summary.nanobot_provider_config?.schema.sections || []).map((section) => ({
    label: section.title,
    value: section.key,
  })),
)

const selectedProviderSection = computed(
  () =>
    (props.summary.nanobot_provider_config?.schema.sections || []).find((section) => section.key === props.selectedProviderKey) ?? null,
)

function ensureSection(section: string) {
  if (!props.nanobotValues[section]) {
    props.nanobotValues[section] = {}
  }
}

function ensureProviderSection(section: string) {
  if (!props.providerValues[section]) {
    props.providerValues[section] = {}
  }
}

function channelBooleanValue(section: string, field: string) {
  return Boolean(props.nanobotValues[section]?.[field])
}

function channelTextValue(section: string, field: string) {
  const value = props.nanobotValues[section]?.[field]
  return typeof value === 'string' ? value : ''
}

function updateChannelBoolean(section: string, field: string, value: boolean) {
  ensureSection(section)
  props.nanobotValues[section][field] = value
}

function updateChannelText(section: string, field: string, value: string) {
  ensureSection(section)
  props.nanobotValues[section][field] = value
}

function agentTextValue(field: string) {
  const value = props.agentValues[field]
  return typeof value === 'string' ? value : ''
}

function agentSelectValue(field: string) {
  const value = props.agentValues[field]
  return typeof value === 'string' && value.length > 0 ? value : null
}

function updateAgentText(field: string, value: string | null) {
  props.agentValues[field] = value ?? ''
  if (field === 'provider' && value && value !== 'auto') {
    emit('update:selectedProviderKey', value)
  }
}

function providerTextValue(section: string, field: string) {
  const value = props.providerValues[section]?.[field]
  return typeof value === 'string' ? value : ''
}

function updateProviderText(section: string, field: string, value: string) {
  ensureProviderSection(section)
  props.providerValues[section][field] = value
}
</script>

<style scoped>
.card-path {
  max-width: 320px;
  text-align: right;
}
</style>
