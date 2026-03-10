export interface User {
  id: number
  username: string
  role: 'admin' | 'user'
  is_active: boolean
  created_at: string
}

export interface WorkspaceType {
  key: 'base' | 'openclaw'
  label: string
  description: string
}

export interface Workspace {
  id: number
  owner_user_id: number
  name: string
  slug: string
  workspace_type: 'base' | 'openclaw'
  host_path: string
  template_version: string
  status: string
  activation_state: 'active' | 'inactive' | 'error' | null
  listen_port: number | null
  created_at: string
}

export interface WorkspaceListItem extends Workspace {
  dashboard_state: 'running' | 'stopped' | 'needs_setup' | 'error'
  channel_summary: string
  model_summary: string
  completion_percent: number
  last_activity_at: string | null
}

export interface ConfigField {
  key: string
  label: string
  type: 'boolean' | 'text' | 'password' | 'number' | 'select' | 'textarea'
  sensitive?: boolean
  options?: string[]
  placeholder?: string
  readonly?: boolean
}

export interface ChannelSchemaSection {
  key: string
  title: string
  fields: ConfigField[]
}

export interface ChannelSchema {
  title: string
  type: string
  sections: ChannelSchemaSection[]
}

export interface FlatSchema {
  title: string
  type: string
  fields: ConfigField[]
}

export interface WorkspaceConfigRead<TSchema = ChannelSchema | FlatSchema, TValue = Record<string, unknown>> {
  schema: TSchema
  values: TValue
  rendered_path: string
  rendered_at: string | null
  warnings: string[]
}

export interface OpenClawConfigRead extends WorkspaceConfigRead<FlatSchema> {
  raw_json5: string
}

export interface RuntimeStatus {
  state: string
  scope: string
  controller_kind: string
  unit_name: string | null
  process_id: number | null
  listen_port: number | null
  config_path: string | null
  workspace_path: string | null
  last_error: string | null
  started_at: string | null
  stopped_at: string | null
  needs_restart: boolean
}

export interface OpenClawRoute {
  agent_id: string
  channel: string
  account_id: string
  enabled: boolean
}

export interface WorkspaceOverview {
  dashboard_state: 'running' | 'stopped' | 'needs_setup' | 'error'
  channel_summary: string
  model_summary: string
  entry_label: string | null
  entry_value: string | null
  last_activity_at: string | null
}

export interface WorkspaceHealth {
  service_state: string
  route_state: string
  model_state: string
  config_state: string
  last_error: string | null
  started_at: string | null
  checked_at: string
}

export interface WorkspaceSetupProgress {
  completion_percent: number
  completed_steps: string[]
  missing_items: string[]
}

export interface WorkspaceDiagnosticsSummary {
  latest_error: string | null
  has_logs: boolean
  available_checks: string[]
}

export interface DiagnosticCheck {
  code: string
  label: string
  status: 'ok' | 'warn' | 'error'
  message: string
  suggested_action: string | null
}

export interface DiagnosticChecksResponse {
  checked_at: string
  checks: DiagnosticCheck[]
}

export interface DiagnosticLogEntry {
  timestamp: string | null
  level: 'info' | 'warning' | 'error'
  message: string
}

export interface DiagnosticLogsResponse {
  source: string
  unit_name: string | null
  entries: DiagnosticLogEntry[]
}

export interface WorkspaceSummary {
  workspace: Workspace
  nanobot_config?: WorkspaceConfigRead<ChannelSchema> | null
  nanobot_agent_config?: WorkspaceConfigRead<FlatSchema> | null
  nanobot_provider_config?: WorkspaceConfigRead<ChannelSchema> | null
  runtime_status?: RuntimeStatus | null
  openclaw_config?: OpenClawConfigRead | null
  openclaw_channel_config?: WorkspaceConfigRead<FlatSchema> | null
  openclaw_route?: OpenClawRoute | null
  shared_runtime_status?: RuntimeStatus | null
  overview?: WorkspaceOverview | null
  health?: WorkspaceHealth | null
  setup_progress?: WorkspaceSetupProgress | null
  recommended_actions: string[]
  diagnostics_summary?: WorkspaceDiagnosticsSummary | null
}
