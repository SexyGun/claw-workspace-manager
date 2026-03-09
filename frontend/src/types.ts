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
  created_at: string
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

export interface WorkspaceSummary {
  workspace: Workspace
  nanobot_config?: WorkspaceConfigRead<ChannelSchema> | null
  gateway_config?: WorkspaceConfigRead<FlatSchema> | null
  runtime_status?: RuntimeStatus | null
  openclaw_config?: OpenClawConfigRead | null
  openclaw_channel_config?: WorkspaceConfigRead<FlatSchema> | null
  openclaw_route?: OpenClawRoute | null
  shared_runtime_status?: RuntimeStatus | null
}
