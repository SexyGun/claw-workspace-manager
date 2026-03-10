import type {
  OpenClawConfigRead,
  RuntimeStatus,
  Workspace,
  WorkspaceConfigRead,
  WorkspaceSummary,
  WorkspaceType,
} from '../types'

import { api } from './client'

export async function listWorkspaceTypes(): Promise<WorkspaceType[]> {
  const response = await api.get<WorkspaceType[]>('/workspace-types')
  return response.data
}

export async function listWorkspaces(): Promise<Workspace[]> {
  const response = await api.get<Workspace[]>('/workspaces')
  return response.data
}

export async function createWorkspace(name: string, workspaceType: 'base' | 'openclaw'): Promise<Workspace> {
  const response = await api.post<Workspace>('/workspaces', { name, workspace_type: workspaceType })
  return response.data
}

export async function fetchWorkspaceSummary(workspaceId: number): Promise<WorkspaceSummary> {
  const response = await api.get<WorkspaceSummary>(`/workspaces/${workspaceId}`)
  return response.data
}

export async function updateWorkspaceName(workspaceId: number, name: string): Promise<Workspace> {
  const response = await api.patch<Workspace>(`/workspaces/${workspaceId}`, { name })
  return response.data
}

export async function saveNanobotConfig(workspaceId: number, values: Record<string, unknown>): Promise<WorkspaceConfigRead> {
  const response = await api.put<WorkspaceConfigRead>(`/workspaces/${workspaceId}/nanobot-config`, { values })
  return response.data
}

export async function saveAgentConfig(workspaceId: number, values: Record<string, unknown>): Promise<WorkspaceConfigRead> {
  const response = await api.put<WorkspaceConfigRead>(`/workspaces/${workspaceId}/agent-config`, { values })
  return response.data
}

export async function saveProviderConfig(workspaceId: number, values: Record<string, unknown>): Promise<WorkspaceConfigRead> {
  const response = await api.put<WorkspaceConfigRead>(`/workspaces/${workspaceId}/provider-config`, { values })
  return response.data
}

export async function fetchWorkspaceRuntime(workspaceId: number): Promise<RuntimeStatus> {
  const response = await api.get<RuntimeStatus>(`/workspaces/${workspaceId}/runtime`)
  return response.data
}

export async function startWorkspaceRuntime(workspaceId: number): Promise<RuntimeStatus> {
  const response = await api.post<RuntimeStatus>(`/workspaces/${workspaceId}/runtime/start`)
  return response.data
}

export async function stopWorkspaceRuntime(workspaceId: number): Promise<RuntimeStatus> {
  const response = await api.post<RuntimeStatus>(`/workspaces/${workspaceId}/runtime/stop`)
  return response.data
}

export async function restartWorkspaceRuntime(workspaceId: number): Promise<RuntimeStatus> {
  const response = await api.post<RuntimeStatus>(`/workspaces/${workspaceId}/runtime/restart`)
  return response.data
}

export async function saveOpenClawConfig(
  workspaceId: number,
  structuredValues: Record<string, unknown>,
  rawJson5: string,
): Promise<OpenClawConfigRead> {
  const response = await api.put<OpenClawConfigRead>(`/workspaces/${workspaceId}/openclaw-config`, {
    structured_values: structuredValues,
    raw_json5: rawJson5,
  })
  return response.data
}

export async function saveOpenClawChannelConfig(
  workspaceId: number,
  values: Record<string, unknown>,
): Promise<WorkspaceConfigRead> {
  const response = await api.put<WorkspaceConfigRead>(`/workspaces/${workspaceId}/openclaw-channel-config`, { values })
  return response.data
}

export async function fetchOpenClawServiceStatus(): Promise<RuntimeStatus> {
  const response = await api.get<RuntimeStatus>('/runtime/openclaw/service')
  return response.data
}

export async function startOpenClawService(): Promise<RuntimeStatus> {
  const response = await api.post<RuntimeStatus>('/runtime/openclaw/service/start')
  return response.data
}

export async function stopOpenClawService(): Promise<RuntimeStatus> {
  const response = await api.post<RuntimeStatus>('/runtime/openclaw/service/stop')
  return response.data
}

export async function restartOpenClawService(): Promise<RuntimeStatus> {
  const response = await api.post<RuntimeStatus>('/runtime/openclaw/service/restart')
  return response.data
}
