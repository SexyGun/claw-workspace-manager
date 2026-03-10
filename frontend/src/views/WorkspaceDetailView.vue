<template>
  <app-shell>
    <n-space v-if="summary" vertical size="large">
      <n-card :bordered="false" class="header-card">
        <n-space justify="space-between" align="start" wrap>
          <div>
            <div class="eyebrow">Workspace Dashboard</div>
            <n-space align="center">
              <n-h2 style="margin: 0">{{ summary.workspace.name }}</n-h2>
              <n-tag size="small" :type="dashboardTagType(summary.overview?.dashboard_state ?? 'stopped')">
                {{ dashboardStateLabel(summary.overview?.dashboard_state ?? 'stopped') }}
              </n-tag>
              <n-tag size="small" type="info">{{ workspaceTypeLabel(summary.workspace.workspace_type) }}</n-tag>
            </n-space>
            <n-space size="small" style="margin-top: 10px">
              <n-tag size="small">{{ summary.overview?.channel_summary ?? '未配置' }}</n-tag>
              <n-tag size="small">{{ summary.overview?.model_summary ?? '未配置' }}</n-tag>
              <n-tag size="small" :type="activationTagType(summary.workspace.activation_state)">
                {{ summary.workspace.activation_state === 'active' ? '已启用' : summary.workspace.activation_state === 'error' ? '异常' : '未启用' }}
              </n-tag>
            </n-space>
            <div class="path-text">{{ summary.workspace.host_path }}</div>
            <n-text depth="3">
              {{ summary.overview?.entry_label ?? '入口' }}: {{ summary.overview?.entry_value ?? '未提供' }} · 最近更新
              {{ formatDateTime(summary.overview?.last_activity_at) }}
            </n-text>
          </div>

          <n-space vertical align="end">
            <n-space>
              <n-button quaternary @click="setViewMode('simple')" :type="viewMode === 'simple' ? 'primary' : 'default'">简洁模式</n-button>
              <n-button quaternary @click="setViewMode('professional')" :type="viewMode === 'professional' ? 'primary' : 'default'">
                专业模式
              </n-button>
            </n-space>
            <n-progress
              class="progress-strip"
              type="line"
              :percentage="summary.setup_progress?.completion_percent ?? 0"
              :show-indicator="false"
              processing
            />
            <n-text depth="3">配置完成度 {{ summary.setup_progress?.completion_percent ?? 0 }}%</n-text>
            <n-space>
              <n-button type="primary" :loading="savingAll" @click="handleSaveAll">保存配置</n-button>
              <n-button secondary :loading="runtimeBusy" @click="handleRuntimeAction(summary.workspace.activation_state === 'active' ? 'stop' : 'start')">
                {{ summary.workspace.activation_state === 'active' ? '停止' : '启动' }}
              </n-button>
              <n-button tertiary :loading="runtimeBusy" @click="handleRuntimeAction('restart')">重启</n-button>
              <n-dropdown trigger="click" :options="moreOptions" @select="handleMoreAction">
                <n-button quaternary>更多</n-button>
              </n-dropdown>
            </n-space>
          </n-space>
        </n-space>
      </n-card>

      <n-tabs v-model:value="activeTab" type="line" animated>
        <n-tab-pane name="overview" tab="概览">
          <n-grid cols="1 l:2" responsive="screen" :x-gap="18" :y-gap="18">
            <n-grid-item>
              <n-card title="当前可用性" class="panel-card">
                <n-space vertical>
                  <div class="health-row">
                    <span>服务状态</span>
                    <strong>{{ runtimeStateLabel(summary.health?.service_state) }}</strong>
                  </div>
                  <div class="health-row">
                    <span>路由状态</span>
                    <strong>{{ summary.health?.route_state === 'connected' ? '已连接' : summary.health?.route_state === 'not_applicable' ? '不适用' : '未连接' }}</strong>
                  </div>
                  <div class="health-row">
                    <span>模型状态</span>
                    <strong>{{ summary.health?.model_state === 'configured' ? '已配置' : '未配置' }}</strong>
                  </div>
                  <div class="health-row">
                    <span>配置完整度</span>
                    <strong>{{ summary.health?.config_state === 'complete' ? '已完成' : '待补充' }}</strong>
                  </div>
                  <div class="health-row">
                    <span>最近启动时间</span>
                    <strong>{{ formatDateTime(summary.health?.started_at) }}</strong>
                  </div>
                </n-space>
              </n-card>
            </n-grid-item>

            <n-grid-item>
              <n-card title="下一步建议" class="panel-card">
                <n-space vertical>
                  <n-alert v-if="summary.health?.last_error" type="error" :show-icon="false">
                    {{ summary.health.last_error }}
                  </n-alert>
                  <n-empty v-if="!summary.recommended_actions.length" description="当前没有阻塞项" />
                  <n-card v-for="action in summary.recommended_actions" :key="action" embedded class="action-card">
                    <n-space justify="space-between" align="center">
                      <span>{{ action }}</span>
                      <n-button
                        v-if="action.includes('诊断')"
                        text
                        type="primary"
                        @click="activeTab = 'diagnostics'"
                      >
                        前往处理
                      </n-button>
                      <n-button
                        v-else-if="action.includes('配置') || action.includes('绑定')"
                        text
                        type="primary"
                        @click="summary.setup_progress?.completion_percent ?? 0 < 100 ? router.push(`/workspaces/${summary.workspace.id}/setup`) : (activeTab = 'config')"
                      >
                        现在处理
                      </n-button>
                      <n-button
                        v-else-if="action.includes('启动')"
                        text
                        type="primary"
                        @click="handleRuntimeAction('start')"
                      >
                        立即启动
                      </n-button>
                    </n-space>
                  </n-card>
                </n-space>
              </n-card>
            </n-grid-item>

            <n-grid-item>
              <n-card title="配置进度" class="panel-card">
                <n-space vertical>
                  <n-progress
                    type="line"
                    :percentage="summary.setup_progress?.completion_percent ?? 0"
                    :show-indicator="false"
                    processing
                  />
                  <n-grid cols="1 s:2" :x-gap="12" :y-gap="12">
                    <n-grid-item>
                      <div class="meta-label">已完成</div>
                      <n-space vertical size="small">
                        <n-tag v-for="item in summary.setup_progress?.completed_steps ?? []" :key="item" size="small" type="success">
                          {{ item }}
                        </n-tag>
                      </n-space>
                    </n-grid-item>
                    <n-grid-item>
                      <div class="meta-label">仍缺少</div>
                      <n-space vertical size="small">
                        <n-tag
                          v-for="item in summary.setup_progress?.missing_items ?? []"
                          :key="item"
                          size="small"
                          type="warning"
                        >
                          {{ item }}
                        </n-tag>
                      </n-space>
                    </n-grid-item>
                  </n-grid>
                </n-space>
              </n-card>
            </n-grid-item>

            <n-grid-item>
              <n-card title="快捷入口" class="panel-card">
                <n-space vertical>
                  <n-button tertiary block @click="router.push(`/workspaces/${summary.workspace.id}/setup`)">继续分步骤配置</n-button>
                  <n-button tertiary block @click="activeTab = 'config'">打开核心配置</n-button>
                  <n-button tertiary block @click="openDiagnosticsTab">查看日志与诊断</n-button>
                </n-space>
              </n-card>
            </n-grid-item>
          </n-grid>
        </n-tab-pane>

        <n-tab-pane name="config" tab="配置">
          <n-grid cols="1 l:2" responsive="screen" :x-gap="18" :y-gap="18">
            <n-grid-item>
              <n-card :title="summary.workspace.workspace_type === 'openclaw' ? '模型与运行方式' : '模型与 Provider'" class="panel-card">
                <template v-if="isBaseWorkspace">
                  <n-form label-placement="top">
                    <n-form-item label="默认模型">
                      <n-input v-model:value="baseDraft.agent.model" placeholder="例如：anthropic/claude-sonnet-4-5" />
                    </n-form-item>
                    <n-form-item label="模型服务商">
                      <n-select
                        v-model:value="baseDraft.agent.provider"
                        :options="providerOptions"
                        @update:value="handleProviderChange"
                      />
                    </n-form-item>
                    <n-form-item label="Provider API Base">
                      <n-input v-model:value="selectedProviderSection.api_base" placeholder="https://openrouter.ai/api/v1" />
                    </n-form-item>
                    <n-form-item label="Provider API Key">
                      <template v-if="!showProviderSecret && hasProviderSecret">
                        <div class="secret-row">
                          <span>已保存，不回显</span>
                          <n-button text type="primary" @click="showProviderSecret = true">重新设置</n-button>
                        </div>
                      </template>
                      <n-input
                        v-else
                        v-model:value="selectedProviderSection.api_key"
                        type="password"
                        show-password-on="click"
                        placeholder="输入新的 API Key"
                      />
                    </n-form-item>
                  </n-form>
                </template>

                <template v-else>
                  <n-form label-placement="top">
                    <n-form-item label="默认模型">
                      <n-input v-model:value="openClawDraft.values.primary_model" placeholder="例如：moonshot/kimi-k2.5" />
                    </n-form-item>
                    <n-form-item label="模型服务商 ID">
                      <n-input v-model:value="openClawDraft.values.provider_id" placeholder="例如：moonshot" />
                    </n-form-item>
                    <n-form-item label="Base URL">
                      <n-input v-model:value="openClawDraft.values.provider_base_url" placeholder="https://api.moonshot.ai/v1" />
                    </n-form-item>
                    <n-form-item label="API Key">
                      <template v-if="!showOpenClawProviderSecret && hasOpenClawProviderSecret">
                        <div class="secret-row">
                          <span>已保存，不回显</span>
                          <n-button text type="primary" @click="showOpenClawProviderSecret = true">重新设置</n-button>
                        </div>
                      </template>
                      <n-input
                        v-else
                        v-model:value="openClawDraft.values.provider_api_key"
                        type="password"
                        show-password-on="click"
                        placeholder="输入新的 API Key"
                      />
                    </n-form-item>
                    <n-form-item label="会话可见范围">
                      <n-select v-model:value="openClawDraft.values.session_dm_scope" :options="sessionScopeOptions" />
                    </n-form-item>
                    <n-form-item label="文件操作范围">
                      <n-select v-model:value="openClawDraft.values.sandbox_mode" :options="sandboxOptions" />
                    </n-form-item>
                    <n-form-item label="启用定时任务">
                      <n-switch v-model:value="openClawDraft.values.cron_enabled" />
                    </n-form-item>
                  </n-form>
                </template>
              </n-card>
            </n-grid-item>

            <n-grid-item>
              <n-card title="渠道配置" class="panel-card">
                <template v-if="isBaseWorkspace">
                  <n-form label-placement="top">
                    <n-form-item label="主要渠道">
                      <n-select v-model:value="baseDraft.selectedChannelKey" :options="channelOptions" />
                    </n-form-item>
                    <n-form-item label="启用渠道">
                      <n-switch v-model:value="selectedChannelSection.enabled" />
                    </n-form-item>
                    <n-form-item :label="selectedChannelKeyLabel === 'QQ' ? 'App ID' : 'App ID / Client ID'">
                      <n-input v-model:value="selectedChannelPrimaryId" @update:value="selectedChannelPrimaryId = $event" />
                    </n-form-item>
                    <n-form-item :label="selectedChannelKeyLabel === 'Feishu' ? 'App Secret' : selectedChannelKeyLabel === 'DingTalk' ? 'Client Secret' : 'Secret'">
                      <template v-if="!showChannelSecret && hasSelectedChannelSecret">
                        <div class="secret-row">
                          <span>已保存，不回显</span>
                          <n-button text type="primary" @click="showChannelSecret = true">重新设置</n-button>
                        </div>
                      </template>
                      <n-input
                        v-else
                        v-model:value="selectedChannelSecret"
                        type="password"
                        show-password-on="click"
                        placeholder="输入新的密钥"
                        @update:value="selectedChannelSecret = $event"
                      />
                    </n-form-item>
                  </n-form>
                </template>

                <template v-else>
                  <n-form label-placement="top">
                    <n-form-item label="启用飞书渠道">
                      <n-switch v-model:value="openClawDraft.channel.enabled" />
                    </n-form-item>
                    <n-form-item label="飞书账号 ID">
                      <n-input v-model:value="openClawDraft.channel.account_id" placeholder="例如：feishu-bot-001" />
                    </n-form-item>
                    <n-form-item label="飞书 App ID">
                      <n-input v-model:value="openClawDraft.channel.app_id" placeholder="输入 App ID" />
                    </n-form-item>
                    <n-form-item label="飞书 App Secret">
                      <template v-if="!showOpenClawChannelSecret && hasOpenClawChannelSecret">
                        <div class="secret-row">
                          <span>已保存，不回显</span>
                          <n-button text type="primary" @click="showOpenClawChannelSecret = true">重新设置</n-button>
                        </div>
                      </template>
                      <n-input
                        v-else
                        v-model:value="openClawDraft.channel.app_secret"
                        type="password"
                        show-password-on="click"
                        placeholder="输入新的 App Secret"
                      />
                    </n-form-item>
                  </n-form>
                </template>
              </n-card>
            </n-grid-item>
          </n-grid>
        </n-tab-pane>

        <n-tab-pane name="diagnostics" tab="日志与诊断">
          <n-space vertical size="large">
            <n-card title="健康状态卡" class="panel-card">
              <template #header-extra>
                <n-space>
                  <n-button quaternary @click="loadDiagnostics">检查配置</n-button>
                  <n-button quaternary @click="loadDiagnostics">刷新日志</n-button>
                  <n-button quaternary @click="handleRuntimeAction('restart')">重新连接</n-button>
                  <n-button v-if="canControlSharedService" quaternary @click="handleSharedServiceAction('restart')">重启共享服务</n-button>
                </n-space>
              </template>
              <n-grid cols="1 s:3" :x-gap="12" :y-gap="12">
                <n-grid-item>
                  <div class="meta-label">服务状态</div>
                  <div class="meta-value">{{ runtimeStateLabel(summary.health?.service_state) }}</div>
                </n-grid-item>
                <n-grid-item>
                  <div class="meta-label">配置完整度</div>
                  <div class="meta-value">{{ summary.health?.config_state === 'complete' ? '已完成' : '待补充' }}</div>
                </n-grid-item>
                <n-grid-item>
                  <div class="meta-label">最近错误</div>
                  <div class="meta-value">{{ summary.health?.last_error ?? '暂无' }}</div>
                </n-grid-item>
              </n-grid>
            </n-card>

            <n-grid cols="1 l:2" responsive="screen" :x-gap="18" :y-gap="18">
              <n-grid-item>
                <n-card title="检查结果" class="panel-card">
                  <n-spin :show="diagnosticsLoading">
                    <n-space vertical>
                      <n-empty v-if="!diagnosticChecks?.checks.length" description="点击“检查配置”生成检查结果" />
                      <n-card
                        v-for="check in diagnosticChecks?.checks ?? []"
                        :key="check.code"
                        embedded
                        class="check-card"
                      >
                        <n-space justify="space-between" align="start">
                          <div>
                            <div class="meta-value">{{ check.label }}</div>
                            <n-text depth="3">{{ check.message }}</n-text>
                            <div v-if="check.suggested_action" class="meta-note">{{ check.suggested_action }}</div>
                          </div>
                          <n-tag :type="check.status === 'ok' ? 'success' : check.status === 'warn' ? 'warning' : 'error'">
                            {{ check.status === 'ok' ? '正常' : check.status === 'warn' ? '注意' : '失败' }}
                          </n-tag>
                        </n-space>
                      </n-card>
                    </n-space>
                  </n-spin>
                </n-card>
              </n-grid-item>

              <n-grid-item>
                <n-card title="最近日志" class="panel-card">
                  <n-spin :show="diagnosticsLoading">
                    <n-space vertical>
                      <n-text depth="3">来源：{{ diagnosticLogs?.source ?? '未加载' }} {{ diagnosticLogs?.unit_name ? `· ${diagnosticLogs.unit_name}` : '' }}</n-text>
                      <n-empty v-if="!diagnosticLogs?.entries.length" description="暂无日志" />
                      <div v-for="(entry, index) in diagnosticLogs?.entries ?? []" :key="`${entry.timestamp ?? 'entry'}-${index}`" class="log-entry">
                        <span class="log-time">{{ formatDateTime(entry.timestamp) }}</span>
                        <n-tag size="small" :type="entry.level === 'error' ? 'error' : entry.level === 'warning' ? 'warning' : 'default'">
                          {{ entry.level }}
                        </n-tag>
                        <span class="log-message">{{ entry.message }}</span>
                      </div>
                    </n-space>
                  </n-spin>
                </n-card>
              </n-grid-item>
            </n-grid>
          </n-space>
        </n-tab-pane>

        <n-tab-pane v-if="viewMode === 'professional'" name="advanced" tab="高级">
          <n-grid cols="1 l:2" responsive="screen" :x-gap="18" :y-gap="18">
            <n-grid-item>
              <n-card title="技术详情" class="panel-card">
                <n-descriptions label-placement="top" :column="1" bordered>
                  <n-descriptions-item label="Runtime State">{{ summary.runtime_status?.state ?? '-' }}</n-descriptions-item>
                  <n-descriptions-item label="Unit">{{ summary.runtime_status?.unit_name ?? summary.shared_runtime_status?.unit_name ?? '-' }}</n-descriptions-item>
                  <n-descriptions-item label="PID">{{ summary.runtime_status?.process_id ?? summary.shared_runtime_status?.process_id ?? '-' }}</n-descriptions-item>
                  <n-descriptions-item label="配置文件">
                    {{ summary.runtime_status?.config_path ?? summary.openclaw_config?.rendered_path ?? summary.nanobot_config?.rendered_path ?? '-' }}
                  </n-descriptions-item>
                  <n-descriptions-item label="工作区目录">
                    {{ summary.runtime_status?.workspace_path ?? summary.workspace.host_path }}
                  </n-descriptions-item>
                  <n-descriptions-item label="最近错误">
                    {{ summary.runtime_status?.last_error ?? summary.shared_runtime_status?.last_error ?? '无' }}
                  </n-descriptions-item>
                </n-descriptions>
              </n-card>
            </n-grid-item>

            <n-grid-item>
              <n-card v-if="!isBaseWorkspace" title="OpenClaw 原始 JSON5" class="panel-card">
                <n-space vertical>
                  <n-input v-model:value="openClawDraft.rawJson5" type="textarea" :autosize="{ minRows: 18, maxRows: 28 }" />
                  <n-button type="primary" :loading="savingAdvanced" @click="handleSaveAdvanced">应用高级配置</n-button>
                </n-space>
              </n-card>
              <n-card v-else title="当前配置快照" class="panel-card">
                <n-space vertical>
                  <n-alert type="info" :show-icon="false">
                    当前简单模式只暴露高频字段。其余 Provider 或渠道原始结构保留在后端配置文件中。
                  </n-alert>
                  <pre class="config-preview">{{ JSON.stringify({ agent: baseDraft.agent, providers: baseDraft.providers, channels: baseDraft.channels }, null, 2) }}</pre>
                </n-space>
              </n-card>
            </n-grid-item>
          </n-grid>
        </n-tab-pane>
      </n-tabs>
    </n-space>

    <n-spin v-else size="large" />

    <n-modal v-model:show="showRename" preset="card" title="重命名工作区" style="width: 420px">
      <n-form>
        <n-form-item label="新名称">
          <n-input v-model:value="renameInput" />
        </n-form-item>
        <n-button type="primary" block :loading="renameBusy" @click="handleRename">保存名称</n-button>
      </n-form>
    </n-modal>
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
  NDropdown,
  NEmpty,
  NForm,
  NFormItem,
  NGrid,
  NGridItem,
  NH2,
  NInput,
  NModal,
  NProgress,
  NSelect,
  NSpace,
  NSpin,
  NSwitch,
  NTabPane,
  NTabs,
  NTag,
  NText,
  useMessage,
} from 'naive-ui'
import { useRoute, useRouter } from 'vue-router'

import AppShell from '../components/AppShell.vue'
import {
  deleteWorkspace,
  fetchDiagnosticChecks,
  fetchDiagnosticLogs,
  fetchWorkspaceSummary,
  getErrorMessage,
  restartOpenClawService,
  restartWorkspaceRuntime,
  saveOpenClawConfig,
  saveWorkspaceSetupConfig,
  startOpenClawService,
  startWorkspaceRuntime,
  stopOpenClawService,
  stopWorkspaceRuntime,
  updateWorkspaceName,
} from '../api'
import { useAuthStore } from '../stores/auth'
import type { DiagnosticChecksResponse, DiagnosticLogsResponse, WorkspaceSummary } from '../types'
import {
  activationTagType,
  BaseChannelKey,
  buildBaseDraft,
  buildOpenClawDraft,
  dashboardStateLabel,
  dashboardTagType,
  formatDateTime,
  MASKED_VALUE,
  runtimeStateLabel,
  WorkspaceTabKey,
  WorkspaceViewMode,
  workspaceTypeLabel,
} from '../utils/workspace'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const message = useMessage()

const workspaceId = computed(() => Number(route.params.id))
const summary = ref<WorkspaceSummary | null>(null)
const loading = ref(false)
const savingAll = ref(false)
const savingAdvanced = ref(false)
const runtimeBusy = ref(false)
const diagnosticsLoading = ref(false)
const renameBusy = ref(false)
const showRename = ref(false)
const renameInput = ref('')
const activeTab = ref<WorkspaceTabKey>('overview')
const viewMode = ref<WorkspaceViewMode>('simple')
const diagnosticChecks = ref<DiagnosticChecksResponse | null>(null)
const diagnosticLogs = ref<DiagnosticLogsResponse | null>(null)

const baseDraft = reactive<any>(buildBaseDraft({} as WorkspaceSummary))
const openClawDraft = reactive<any>(buildOpenClawDraft({} as WorkspaceSummary))

const showProviderSecret = ref(false)
const showChannelSecret = ref(false)
const showOpenClawProviderSecret = ref(false)
const showOpenClawChannelSecret = ref(false)

const isBaseWorkspace = computed(() => summary.value?.workspace.workspace_type === 'base')
const canControlSharedService = computed(() => authStore.isAdmin.value && !isBaseWorkspace.value)
const moreOptions = computed(() => [
  { label: '重命名', key: 'rename' },
  { label: '继续向导配置', key: 'setup' },
  { label: '查看诊断', key: 'diagnostics' },
  { label: '删除工作区', key: 'delete' },
])

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

const selectedProviderSection = computed(() => {
  return baseDraft.providers[baseDraft.selectedProviderKey] ?? {}
})
const selectedChannelSection = computed(() => {
  return baseDraft.channels[baseDraft.selectedChannelKey] ?? {}
})
const selectedChannelKeyLabel = computed(() => {
  const current = channelOptions.find((item) => item.value === baseDraft.selectedChannelKey)
  return current?.label ?? 'Feishu'
})

const hasProviderSecret = computed(() => {
  const value = selectedProviderSection.value.api_key
  return typeof value === 'string' && value.length > 0
})
const hasSelectedChannelSecret = computed(() => {
  const value = selectedChannelSecret.value
  return typeof value === 'string' && value.length > 0
})
const hasOpenClawProviderSecret = computed(() => {
  const value = openClawDraft.values.provider_api_key
  return typeof value === 'string' && value.length > 0
})
const hasOpenClawChannelSecret = computed(() => {
  const value = openClawDraft.channel.app_secret
  return typeof value === 'string' && value.length > 0
})

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

function resetSecretEditors() {
  showProviderSecret.value = false
  showChannelSecret.value = false
  showOpenClawProviderSecret.value = false
  showOpenClawChannelSecret.value = false
}

function applySummary(nextSummary: WorkspaceSummary) {
  summary.value = nextSummary
  Object.assign(baseDraft, buildBaseDraft(nextSummary))
  Object.assign(openClawDraft, buildOpenClawDraft(nextSummary))
  renameInput.value = nextSummary.workspace.name
  resetSecretEditors()
}

async function loadSummary() {
  loading.value = true
  try {
    const data = await fetchWorkspaceSummary(workspaceId.value)
    applySummary(data)
  } catch (error) {
    message.error(getErrorMessage(error))
  } finally {
    loading.value = false
  }
}

async function loadDiagnostics() {
  diagnosticsLoading.value = true
  try {
    const [checks, logs] = await Promise.all([
      fetchDiagnosticChecks(workspaceId.value),
      fetchDiagnosticLogs(workspaceId.value),
    ])
    diagnosticChecks.value = checks
    diagnosticLogs.value = logs
  } catch (error) {
    message.error(getErrorMessage(error))
  } finally {
    diagnosticsLoading.value = false
  }
}

function handleProviderChange(value: string) {
  baseDraft.agent.provider = value
  baseDraft.selectedProviderKey = value
  showProviderSecret.value = false
}

async function handleSaveAll() {
  if (!summary.value) {
    return
  }
  savingAll.value = true
  try {
    const data = await saveWorkspaceSetupConfig(
      summary.value.workspace.id,
      isBaseWorkspace.value
        ? {
            nanobot: baseDraft.channels,
            agent: baseDraft.agent,
            provider: baseDraft.providers,
          }
        : {
            openclaw: openClawDraft.values,
            openclaw_channel: openClawDraft.channel,
          },
    )
    applySummary(data)
    message.success('配置已保存')
  } catch (error) {
    message.error(getErrorMessage(error))
  } finally {
    savingAll.value = false
  }
}

async function handleSaveAdvanced() {
  if (!summary.value || isBaseWorkspace.value) {
    return
  }
  savingAdvanced.value = true
  try {
    await saveOpenClawConfig(summary.value.workspace.id, openClawDraft.values, openClawDraft.rawJson5)
    await loadSummary()
    message.success('高级配置已应用')
  } catch (error) {
    message.error(getErrorMessage(error))
  } finally {
    savingAdvanced.value = false
  }
}

async function handleRuntimeAction(action: 'start' | 'stop' | 'restart') {
  if (!summary.value) {
    return
  }
  runtimeBusy.value = true
  try {
    if (action === 'start') {
      await startWorkspaceRuntime(summary.value.workspace.id)
    } else if (action === 'stop') {
      await stopWorkspaceRuntime(summary.value.workspace.id)
    } else {
      await restartWorkspaceRuntime(summary.value.workspace.id)
    }
    await loadSummary()
    if (activeTab.value === 'diagnostics') {
      await loadDiagnostics()
    }
    message.success(action === 'start' ? '已发送启动命令' : action === 'stop' ? '已发送停止命令' : '已发送重启命令')
  } catch (error) {
    message.error(getErrorMessage(error))
  } finally {
    runtimeBusy.value = false
  }
}

async function handleSharedServiceAction(action: 'start' | 'stop' | 'restart') {
  if (!summary.value) {
    return
  }
  runtimeBusy.value = true
  try {
    if (action === 'start') {
      await startOpenClawService()
    } else if (action === 'stop') {
      await stopOpenClawService()
    } else {
      await restartOpenClawService()
    }
    await loadSummary()
    if (activeTab.value === 'diagnostics') {
      await loadDiagnostics()
    }
    message.success('共享 OpenClaw 服务状态已更新')
  } catch (error) {
    message.error(getErrorMessage(error))
  } finally {
    runtimeBusy.value = false
  }
}

async function handleMoreAction(action: string | number) {
  if (!summary.value) {
    return
  }
  if (action === 'rename') {
    showRename.value = true
    return
  }
  if (action === 'setup') {
    router.push(`/workspaces/${summary.value.workspace.id}/setup`)
    return
  }
  if (action === 'diagnostics') {
    openDiagnosticsTab()
    return
  }
  if (action === 'delete') {
    const confirmed = window.confirm(`确认删除工作区“${summary.value.workspace.name}”吗？此操作不可恢复。`)
    if (!confirmed) {
      return
    }
    try {
      await deleteWorkspace(summary.value.workspace.id)
      message.success('工作区已删除')
      router.push('/workspaces')
    } catch (error) {
      message.error(getErrorMessage(error))
    }
  }
}

async function handleRename() {
  if (!summary.value) {
    return
  }
  renameBusy.value = true
  try {
    await updateWorkspaceName(summary.value.workspace.id, renameInput.value)
    showRename.value = false
    await loadSummary()
    message.success('名称已更新')
  } catch (error) {
    message.error(getErrorMessage(error))
  } finally {
    renameBusy.value = false
  }
}

function openDiagnosticsTab() {
  activeTab.value = 'diagnostics'
}

function setViewMode(nextMode: WorkspaceViewMode) {
  viewMode.value = nextMode
  localStorage.setItem('claw-workspace-view-mode', nextMode)
  if (nextMode === 'simple' && activeTab.value === 'advanced') {
    activeTab.value = 'overview'
  }
}

watch(
  () => route.query.tab,
  (value) => {
    const nextTab = typeof value === 'string' ? value : 'overview'
    if (['overview', 'config', 'diagnostics', 'advanced'].includes(nextTab)) {
      activeTab.value = nextTab as WorkspaceTabKey
    }
  },
  { immediate: true },
)

watch(
  () => route.query.mode,
  (value) => {
    if (value === 'professional' || value === 'simple') {
      setViewMode(value)
      return
    }
    const stored = localStorage.getItem('claw-workspace-view-mode')
    if (stored === 'professional' || stored === 'simple') {
      viewMode.value = stored
    }
  },
  { immediate: true },
)

watch(activeTab, (value) => {
  router.replace({ query: { ...route.query, tab: value, mode: viewMode.value } })
  if (value === 'diagnostics') {
    void loadDiagnostics()
  }
})

watch(viewMode, (value) => {
  router.replace({ query: { ...route.query, tab: activeTab.value, mode: value } })
})

watch(workspaceId, () => {
  diagnosticChecks.value = null
  diagnosticLogs.value = null
  void loadSummary()
})

onMounted(async () => {
  await authStore.ensureLoaded()
  await loadSummary()
  if (activeTab.value === 'diagnostics') {
    await loadDiagnostics()
  }
})
</script>

<style scoped>
.header-card {
  background:
    radial-gradient(circle at top right, rgba(251, 146, 60, 0.2), transparent 28%),
    linear-gradient(135deg, rgba(10, 18, 32, 0.84), rgba(18, 47, 88, 0.52));
}

.panel-card {
  background: rgba(11, 19, 35, 0.78);
}

.eyebrow {
  color: #fb923c;
  text-transform: uppercase;
  letter-spacing: 0.12em;
  font-size: 0.78rem;
}

.progress-strip {
  width: 240px;
}

.path-text {
  margin: 12px 0 6px;
  color: #94a3b8;
  word-break: break-all;
}

.health-row {
  display: flex;
  justify-content: space-between;
  gap: 16px;
}

.action-card,
.check-card {
  background: rgba(15, 23, 42, 0.74);
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

.secret-row {
  display: flex;
  width: 100%;
  justify-content: space-between;
  align-items: center;
}

.log-entry {
  display: grid;
  grid-template-columns: 152px 60px minmax(0, 1fr);
  gap: 10px;
  align-items: start;
}

.log-time {
  color: #94a3b8;
  font-size: 0.82rem;
}

.log-message {
  word-break: break-word;
}

.config-preview {
  margin: 0;
  padding: 16px;
  overflow: auto;
  border-radius: 12px;
  background: rgba(15, 23, 42, 0.7);
  color: #dbeafe;
}
</style>
