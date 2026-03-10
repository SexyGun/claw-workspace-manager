import type { WorkspaceListItem, WorkspaceSummary } from '../types'

export const MASKED_VALUE = '__MASKED__'

export type WorkspaceViewMode = 'simple' | 'professional'
export type WorkspaceTabKey = 'overview' | 'config' | 'diagnostics' | 'advanced'
export type BaseChannelKey = 'feishu' | 'dingtalk' | 'qq'

export interface BaseWorkspaceDraft {
  agent: Record<string, unknown>
  channels: Record<string, Record<string, unknown>>
  providers: Record<string, Record<string, unknown>>
  selectedChannelKey: BaseChannelKey
  selectedProviderKey: string
}

export interface OpenClawWorkspaceDraft {
  values: Record<string, unknown>
  channel: Record<string, unknown>
  rawJson5: string
}

export function workspaceTypeLabel(workspaceType: 'base' | 'openclaw') {
  return workspaceType === 'openclaw' ? 'OpenClaw 工作区' : 'Nanobot 工作区'
}

export function dashboardStateLabel(state: WorkspaceListItem['dashboard_state'] | undefined | null) {
  switch (state) {
    case 'running':
      return '运行中'
    case 'error':
      return '异常'
    case 'needs_setup':
      return '待配置'
    default:
      return '未启动'
  }
}

export function dashboardTagType(state: WorkspaceListItem['dashboard_state'] | undefined | null) {
  switch (state) {
    case 'running':
      return 'success'
    case 'error':
      return 'error'
    case 'needs_setup':
      return 'warning'
    default:
      return 'default'
  }
}

export function activationTagType(value: string | null | undefined) {
  switch (value) {
    case 'active':
      return 'success'
    case 'error':
      return 'error'
    default:
      return 'default'
  }
}

export function runtimeStateLabel(value: string | null | undefined) {
  switch (value) {
    case 'running':
      return '运行中'
    case 'starting':
      return '启动中'
    case 'stopping':
      return '停止中'
    case 'configured':
      return '已配置'
    case 'inactive':
      return '未启用'
    case 'error':
      return '异常'
    default:
      return '未启动'
  }
}

export function boolText(value: unknown) {
  return value ? '已启用' : '未启用'
}

export function formatDateTime(value: string | null | undefined) {
  if (!value) {
    return '未记录'
  }
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return value
  }
  return date.toLocaleString('zh-CN', { hour12: false })
}

export function buildBaseDraft(summary: WorkspaceSummary): BaseWorkspaceDraft {
  const agent = { ...(summary.nanobot_agent_config?.values ?? {}) }
  const channels = Object.fromEntries(
    Object.entries(summary.nanobot_config?.values ?? {}).map(([key, value]) => [key, { ...(value as Record<string, unknown>) }]),
  )
  const providers = Object.fromEntries(
    Object.entries(summary.nanobot_provider_config?.values ?? {}).map(([key, value]) => [key, { ...(value as Record<string, unknown>) }]),
  )
  const enabledChannel = (Object.entries(channels).find(([, value]) => Boolean(value.enabled))?.[0] ?? 'feishu') as BaseChannelKey
  const providerFromAgent = typeof agent.provider === 'string' && agent.provider !== 'auto' ? agent.provider : ''
  const providerKeys = Object.keys(providers)
  const selectedProviderKey =
    (providerFromAgent && providerKeys.includes(providerFromAgent) ? providerFromAgent : providerKeys[0]) ?? 'custom'

  return {
    agent,
    channels,
    providers,
    selectedChannelKey: enabledChannel,
    selectedProviderKey,
  }
}

export function buildOpenClawDraft(summary: WorkspaceSummary): OpenClawWorkspaceDraft {
  return {
    values: { ...(summary.openclaw_config?.values ?? {}) },
    channel: { ...(summary.openclaw_channel_config?.values ?? {}) },
    rawJson5: summary.openclaw_config?.raw_json5 ?? '',
  }
}
