<template>
  <app-shell>
    <n-space v-if="summary" vertical size="large">
      <n-card :bordered="false" class="wizard-hero">
        <n-space justify="space-between" align="center" wrap>
          <div>
            <div class="eyebrow">Setup Wizard</div>
            <n-h2 style="margin: 0">先配模型和渠道，再决定是否启动</n-h2>
            <n-text depth="3">
              当前工作区：{{ summary.workspace.name }} · {{ workspaceTypeLabel(summary.workspace.workspace_type) }}
            </n-text>
          </div>
          <n-space>
            <n-button quaternary @click="router.push(`/workspaces/${summary.workspace.id}`)">返回管理台</n-button>
            <n-button secondary @click="handleSaveWithoutStart">保存并稍后处理</n-button>
          </n-space>
        </n-space>
      </n-card>

      <n-card :bordered="false" class="steps-card">
        <n-steps :current="currentStep">
          <n-step title="工作区类型" description="确认类型与用途" />
          <n-step title="模型配置" description="填写默认模型和 Provider" />
          <n-step title="渠道配置" description="绑定要使用的账号" />
          <n-step title="运行方式" description="决定访问和会话策略" />
          <n-step title="确认并启动" description="检查后立即生效" />
        </n-steps>
      </n-card>

      <n-card class="wizard-card" :bordered="false">
        <template v-if="currentStep === 1">
          <n-space vertical size="large">
            <n-alert type="info" :show-icon="false">
              这个向导只处理高频配置。原始 JSON、Hooks、PID、Unit 等信息会保留在详情页的专业模式中。
            </n-alert>
            <n-grid cols="1 s:2" :x-gap="16" :y-gap="16">
              <n-grid-item>
                <n-card embedded class="choice-card">
                  <div class="meta-label">当前类型</div>
                  <div class="meta-value">{{ workspaceTypeLabel(summary.workspace.workspace_type) }}</div>
                </n-card>
              </n-grid-item>
              <n-grid-item>
                <n-card embedded class="choice-card">
                  <div class="meta-label">当前状态</div>
                  <div class="meta-value">{{ dashboardStateLabel(summary.overview?.dashboard_state ?? 'stopped') }}</div>
                </n-card>
              </n-grid-item>
            </n-grid>
          </n-space>
        </template>

        <template v-else-if="currentStep === 2">
          <n-grid cols="1 l:2" responsive="screen" :x-gap="18" :y-gap="18">
            <n-grid-item>
              <n-card embedded title="默认模型">
                <n-form label-placement="top">
                  <n-form-item label="默认模型">
                    <n-input
                      v-if="isBaseWorkspace"
                      v-model:value="baseDraft.agent.model"
                      placeholder="例如：anthropic/claude-sonnet-4-5"
                    />
                    <n-input
                      v-else
                      v-model:value="openClawDraft.values.primary_model"
                      placeholder="例如：moonshot/kimi-k2.5"
                    />
                  </n-form-item>
                  <n-form-item label="模型服务商">
                    <n-select
                      v-if="isBaseWorkspace"
                      v-model:value="baseDraft.agent.provider"
                      :options="providerOptions"
                      @update:value="handleProviderChange"
                    />
                    <n-input v-else v-model:value="openClawDraft.values.provider_id" placeholder="例如：moonshot" />
                  </n-form-item>
                </n-form>
              </n-card>
            </n-grid-item>

            <n-grid-item>
              <n-card embedded title="Provider 接入">
                <n-form label-placement="top">
                  <n-form-item label="Base URL">
                    <n-input
                      v-if="isBaseWorkspace"
                      v-model:value="selectedProviderSection.api_base"
                      placeholder="https://openrouter.ai/api/v1"
                    />
                    <n-input v-else v-model:value="openClawDraft.values.provider_base_url" placeholder="https://api.moonshot.ai/v1" />
                  </n-form-item>
                  <n-form-item label="API Key">
                    <template v-if="secretSaved && !showSecretEditor">
                      <div class="secret-row">
                        <span>已保存，不回显</span>
                        <n-button text type="primary" @click="showSecretEditor = true">重新设置</n-button>
                      </div>
                    </template>
                    <n-input
                      v-else
                      :value="secretValue"
                      type="password"
                      show-password-on="click"
                      placeholder="输入新的 API Key"
                      @update:value="secretValue = $event"
                    />
                  </n-form-item>
                </n-form>
              </n-card>
            </n-grid-item>
          </n-grid>
        </template>

        <template v-else-if="currentStep === 3">
          <n-grid cols="1 l:2" responsive="screen" :x-gap="18" :y-gap="18">
            <n-grid-item>
              <n-card embedded title="渠道选择">
                <n-form label-placement="top">
                  <n-form-item v-if="isBaseWorkspace" label="主要渠道">
                    <n-select v-model:value="baseDraft.selectedChannelKey" :options="channelOptions" />
                  </n-form-item>
                  <n-form-item label="启用渠道">
                    <n-switch v-if="isBaseWorkspace" v-model:value="selectedChannelSection.enabled" />
                    <n-switch v-else v-model:value="openClawDraft.channel.enabled" />
                  </n-form-item>
                  <n-alert type="info" :show-icon="false">
                    普通用户只需要先绑定一个能用的主渠道；其它渠道可以稍后到专业模式再加。
                  </n-alert>
                </n-form>
              </n-card>
            </n-grid-item>

            <n-grid-item>
              <n-card embedded title="账号信息">
                <n-form label-placement="top">
                  <template v-if="isBaseWorkspace">
                    <n-form-item :label="selectedChannelLabel === 'DingTalk' ? 'Client ID' : 'App ID'">
                      <n-input v-model:value="selectedChannelPrimaryId" />
                    </n-form-item>
                    <n-form-item :label="selectedChannelLabel === 'DingTalk' ? 'Client Secret' : selectedChannelLabel === 'QQ' ? 'Secret' : 'App Secret'">
                      <n-input v-model:value="selectedChannelSecret" type="password" show-password-on="click" />
                    </n-form-item>
                  </template>
                  <template v-else>
                    <n-form-item label="飞书账号 ID">
                      <n-input v-model:value="openClawDraft.channel.account_id" />
                    </n-form-item>
                    <n-form-item label="飞书 App ID">
                      <n-input v-model:value="openClawDraft.channel.app_id" />
                    </n-form-item>
                    <n-form-item label="飞书 App Secret">
                      <n-input v-model:value="openClawDraft.channel.app_secret" type="password" show-password-on="click" />
                    </n-form-item>
                  </template>
                </n-form>
              </n-card>
            </n-grid-item>
          </n-grid>
        </template>

        <template v-else-if="currentStep === 4">
          <n-grid cols="1 l:2" responsive="screen" :x-gap="18" :y-gap="18">
            <n-grid-item>
              <n-card embedded title="运行方式">
                <n-form label-placement="top">
                  <template v-if="isBaseWorkspace">
                    <n-alert type="info" :show-icon="false">
                      Nanobot 工作区默认采用原生运行方式。你只需要确保模型和渠道可用，启动后即可使用。
                    </n-alert>
                  </template>
                  <template v-else>
                    <n-form-item label="会话可见范围">
                      <n-select v-model:value="openClawDraft.values.session_dm_scope" :options="sessionScopeOptions" />
                    </n-form-item>
                    <n-form-item label="文件操作范围">
                      <n-select v-model:value="openClawDraft.values.sandbox_mode" :options="sandboxOptions" />
                    </n-form-item>
                    <n-form-item label="启用定时任务">
                      <n-switch v-model:value="openClawDraft.values.cron_enabled" />
                    </n-form-item>
                  </template>
                </n-form>
              </n-card>
            </n-grid-item>

            <n-grid-item>
              <n-card embedded title="你将得到什么">
                <n-space vertical>
                  <div class="meta-label">完成本步后</div>
                  <div class="meta-value">工作区会具备可用的默认模型、主渠道和推荐运行方式。</div>
                  <n-text depth="3">如果后续需要自定义 JSON5、Hooks 或更多 Provider，可以到详情页的专业模式继续调整。</n-text>
                </n-space>
              </n-card>
            </n-grid-item>
          </n-grid>
        </template>

        <template v-else>
          <n-grid cols="1 l:2" responsive="screen" :x-gap="18" :y-gap="18">
            <n-grid-item>
              <n-card embedded title="配置摘要">
                <n-descriptions label-placement="top" :column="1" bordered>
                  <n-descriptions-item label="工作区类型">{{ workspaceTypeLabel(summary.workspace.workspace_type) }}</n-descriptions-item>
                  <n-descriptions-item label="默认模型">
                    {{ isBaseWorkspace ? baseDraft.agent.model : openClawDraft.values.primary_model }}
                  </n-descriptions-item>
                  <n-descriptions-item label="Provider">
                    {{ isBaseWorkspace ? baseDraft.agent.provider : openClawDraft.values.provider_id }}
                  </n-descriptions-item>
                  <n-descriptions-item label="渠道">
                    {{ isBaseWorkspace ? selectedChannelLabel : 'Feishu' }}
                  </n-descriptions-item>
                  <n-descriptions-item label="启动后动作">保存配置并立即启用工作区</n-descriptions-item>
                </n-descriptions>
              </n-card>
            </n-grid-item>

            <n-grid-item>
              <n-card embedded title="最终确认">
                <n-space vertical>
                  <n-alert type="warning" :show-icon="false">
                    OpenClaw 工作区会启用 route；共享 OpenClaw 服务是否已运行仍取决于管理员控制。
                  </n-alert>
                  <n-button type="primary" size="large" :loading="saving" block @click="handleFinish">保存并启动</n-button>
                </n-space>
              </n-card>
            </n-grid-item>
          </n-grid>
        </template>
      </n-card>

      <n-space justify="space-between">
        <n-button quaternary :disabled="currentStep === 1" @click="currentStep -= 1">上一步</n-button>
        <n-button v-if="currentStep < 5" type="primary" @click="handleNext">下一步</n-button>
      </n-space>
    </n-space>

    <n-spin v-else size="large" />
  </app-shell>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
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
  NSelect,
  NSpace,
  NSpin,
  NStep,
  NSteps,
  NSwitch,
  NText,
  useMessage,
} from 'naive-ui'
import { useRoute, useRouter } from 'vue-router'

import AppShell from '../components/AppShell.vue'
import { fetchWorkspaceSummary, getErrorMessage, saveWorkspaceSetupConfig } from '../api'
import type { WorkspaceSummary } from '../types'
import { buildBaseDraft, buildOpenClawDraft, dashboardStateLabel, MASKED_VALUE, workspaceTypeLabel } from '../utils/workspace'

const route = useRoute()
const router = useRouter()
const message = useMessage()

const workspaceId = computed(() => Number(route.params.id))
const summary = ref<WorkspaceSummary | null>(null)
const saving = ref(false)
const currentStep = ref(1)
const showSecretEditor = ref(false)

const baseDraft = reactive<any>(buildBaseDraft({} as WorkspaceSummary))
const openClawDraft = reactive<any>(buildOpenClawDraft({} as WorkspaceSummary))

const isBaseWorkspace = computed(() => summary.value?.workspace.workspace_type === 'base')
const providerOptions = computed(() =>
  Object.keys(baseDraft.providers).map((key) => ({
    label: key,
    value: key,
  })),
)
const channelOptions = [
  { label: 'Feishu', value: 'feishu' },
  { label: 'DingTalk', value: 'dingtalk' },
  { label: 'QQ', value: 'qq' },
]
const sessionScopeOptions = [
  { label: '主会话共享', value: 'main' },
  { label: '按联系人隔离', value: 'per-peer' },
  { label: '按群和联系人隔离', value: 'per-channel-peer' },
  { label: '按账号 / 群 / 联系人隔离', value: 'per-account-channel-peer' },
]
const sandboxOptions = [
  { label: '关闭沙盒限制', value: 'off' },
  { label: '仅限制主工作区外访问', value: 'non-main' },
  { label: '所有目录都走沙盒', value: 'all' },
]

const selectedProviderSection = computed(() => baseDraft.providers[baseDraft.selectedProviderKey] ?? {})
const selectedChannelSection = computed(() => baseDraft.channels[baseDraft.selectedChannelKey] ?? {})
const selectedChannelLabel = computed(() => channelOptions.find((option) => option.value === baseDraft.selectedChannelKey)?.label ?? 'Feishu')

const selectedChannelPrimaryId = computed({
  get() {
    if (baseDraft.selectedChannelKey === 'dingtalk') {
      return String(selectedChannelSection.value.client_id ?? '')
    }
    return String(selectedChannelSection.value.app_id ?? '')
  },
  set(value: string) {
    if (baseDraft.selectedChannelKey === 'dingtalk') {
      selectedChannelSection.value.client_id = value
      return
    }
    selectedChannelSection.value.app_id = value
  },
})

const selectedChannelSecret = computed({
  get() {
    if (baseDraft.selectedChannelKey === 'dingtalk') {
      return String(selectedChannelSection.value.client_secret ?? '')
    }
    if (baseDraft.selectedChannelKey === 'qq') {
      return String(selectedChannelSection.value.secret ?? '')
    }
    return String(selectedChannelSection.value.app_secret ?? '')
  },
  set(value: string) {
    if (baseDraft.selectedChannelKey === 'dingtalk') {
      selectedChannelSection.value.client_secret = value
      return
    }
    if (baseDraft.selectedChannelKey === 'qq') {
      selectedChannelSection.value.secret = value
      return
    }
    selectedChannelSection.value.app_secret = value
  },
})

const secretSaved = computed(() => {
  const value = secretValue.value
  return typeof value === 'string' && value.length > 0
})

const secretValue = computed({
  get() {
    return isBaseWorkspace.value ? String(selectedProviderSection.value.api_key ?? '') : String(openClawDraft.values.provider_api_key ?? '')
  },
  set(value: string) {
    if (isBaseWorkspace.value) {
      selectedProviderSection.value.api_key = value
      return
    }
    openClawDraft.values.provider_api_key = value
  },
})

function applySummary(nextSummary: WorkspaceSummary) {
  summary.value = nextSummary
  Object.assign(baseDraft, buildBaseDraft(nextSummary))
  Object.assign(openClawDraft, buildOpenClawDraft(nextSummary))
  showSecretEditor.value = false
}

async function loadSummary() {
  try {
    const data = await fetchWorkspaceSummary(workspaceId.value)
    applySummary(data)
  } catch (error) {
    message.error(getErrorMessage(error))
  }
}

function handleProviderChange(value: string) {
  baseDraft.agent.provider = value
  baseDraft.selectedProviderKey = value
  showSecretEditor.value = false
}

function validateCurrentStep() {
  if (currentStep.value === 2) {
    const model = isBaseWorkspace.value ? String(baseDraft.agent.model ?? '') : String(openClawDraft.values.primary_model ?? '')
    if (!model.trim()) {
      message.warning('请先填写默认模型')
      return false
    }
  }
  if (currentStep.value === 3) {
    if (isBaseWorkspace.value) {
      if (!selectedChannelSection.value.enabled || !String(selectedChannelPrimaryId.value).trim() || !String(selectedChannelSecret.value).trim()) {
        message.warning('请先完成主渠道配置')
        return false
      }
    } else if (
      !openClawDraft.channel.enabled ||
      !String(openClawDraft.channel.account_id ?? '').trim() ||
      !String(openClawDraft.channel.app_id ?? '').trim() ||
      !String(openClawDraft.channel.app_secret ?? '').trim()
    ) {
      message.warning('请先完成飞书账号配置')
      return false
    }
  }
  return true
}

function handleNext() {
  if (!validateCurrentStep()) {
    return
  }
  currentStep.value += 1
}

async function handlePersist(startAfterSave: boolean) {
  if (!summary.value) {
    return
  }
  saving.value = true
  try {
    await saveWorkspaceSetupConfig(
      summary.value.workspace.id,
      isBaseWorkspace.value
        ? {
            nanobot: baseDraft.channels,
            agent: baseDraft.agent,
            provider: baseDraft.providers,
            start_after_save: startAfterSave,
          }
        : {
            openclaw: openClawDraft.values,
            openclaw_channel: openClawDraft.channel,
            start_after_save: startAfterSave,
          },
    )
    message.success(startAfterSave ? '配置已保存并启用' : '配置已保存')
    router.push(`/workspaces/${summary.value.workspace.id}`)
  } catch (error) {
    message.error(getErrorMessage(error))
  } finally {
    saving.value = false
  }
}

async function handleSaveWithoutStart() {
  await handlePersist(false)
}

async function handleFinish() {
  if (!validateCurrentStep()) {
    return
  }
  await handlePersist(true)
}

watch(workspaceId, () => {
  void loadSummary()
})

onMounted(() => {
  void loadSummary()
})
</script>

<style scoped>
.wizard-hero {
  background:
    radial-gradient(circle at top left, rgba(56, 189, 248, 0.18), transparent 28%),
    linear-gradient(135deg, rgba(10, 18, 32, 0.86), rgba(23, 37, 84, 0.52));
}

.steps-card,
.wizard-card {
  background: rgba(11, 19, 35, 0.78);
}

.choice-card {
  background: rgba(15, 23, 42, 0.72);
}

.eyebrow {
  color: #fb923c;
  text-transform: uppercase;
  letter-spacing: 0.12em;
  font-size: 0.78rem;
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

.secret-row {
  display: flex;
  width: 100%;
  justify-content: space-between;
  align-items: center;
}
</style>
