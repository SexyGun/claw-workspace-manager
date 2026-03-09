export interface User {
  id: number
  username: string
  role: 'admin' | 'user'
  is_active: boolean
  created_at: string
}

export interface Workspace {
  id: number
  owner_user_id: number
  name: string
  slug: string
  host_path: string
  template_version: string
  status: string
  created_at: string
}

export interface ConfigField {
  key: string
  label: string
  type: 'boolean' | 'text' | 'password' | 'number' | 'select'
  sensitive?: boolean
  options?: string[]
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

export interface GatewaySchema {
  title: string
  type: string
  fields: ConfigField[]
}

export interface WorkspaceConfigRead<TSchema = ChannelSchema | GatewaySchema, TValue = Record<string, unknown>> {
  schema: TSchema
  values: TValue
  rendered_path: string
  rendered_at: string | null
}

export interface GatewayStatus {
  state: string
  container_name: string
  last_container_id: string | null
  last_error: string | null
  started_at: string | null
  stopped_at: string | null
}

export interface WorkspaceSummary {
  workspace: Workspace
  nanobot_config: WorkspaceConfigRead<ChannelSchema>
  gateway_config: WorkspaceConfigRead<GatewaySchema>
  gateway_status: GatewayStatus
}
