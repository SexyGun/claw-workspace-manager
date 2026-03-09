import axios from 'axios'

import type { GatewayStatus, User, Workspace, WorkspaceConfigRead, WorkspaceSummary } from './types'

const api = axios.create({
  baseURL: '/api',
  withCredentials: true,
})

export type ApiError = {
  detail?: string
}

export function getErrorMessage(error: unknown): string {
  if (axios.isAxiosError<ApiError>(error)) {
    return error.response?.data?.detail ?? error.message
  }
  if (error instanceof Error) {
    return error.message
  }
  return 'Unexpected error'
}

export async function login(username: string, password: string): Promise<User> {
  const response = await api.post<User>('/auth/login', { username, password })
  return response.data
}

export async function logout(): Promise<void> {
  await api.post('/auth/logout')
}

export async function fetchMe(): Promise<User> {
  const response = await api.get<User>('/auth/me')
  return response.data
}

export async function listUsers(): Promise<User[]> {
  const response = await api.get<User[]>('/users')
  return response.data
}

export async function createUser(payload: { username: string; password: string; role: 'admin' | 'user'; is_active: boolean }) {
  const response = await api.post<User>('/users', payload)
  return response.data
}

export async function updateUser(userId: number, payload: Partial<Pick<User, 'role' | 'is_active'>>) {
  const response = await api.patch<User>(`/users/${userId}`, payload)
  return response.data
}

export async function resetPassword(userId: number, password: string) {
  await api.post(`/users/${userId}/reset-password`, { password })
}

export async function listWorkspaces(): Promise<Workspace[]> {
  const response = await api.get<Workspace[]>('/workspaces')
  return response.data
}

export async function createWorkspace(name: string): Promise<Workspace> {
  const response = await api.post<Workspace>('/workspaces', { name })
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

export async function saveGatewayConfig(workspaceId: number, values: Record<string, unknown>): Promise<WorkspaceConfigRead> {
  const response = await api.put<WorkspaceConfigRead>(`/workspaces/${workspaceId}/gateway-config`, { values })
  return response.data
}

export async function fetchGatewayStatus(workspaceId: number): Promise<GatewayStatus> {
  const response = await api.get<GatewayStatus>(`/workspaces/${workspaceId}/gateway/status`)
  return response.data
}

export async function startGateway(workspaceId: number): Promise<GatewayStatus> {
  const response = await api.post<GatewayStatus>(`/workspaces/${workspaceId}/gateway/start`)
  return response.data
}

export async function stopGateway(workspaceId: number): Promise<GatewayStatus> {
  const response = await api.post<GatewayStatus>(`/workspaces/${workspaceId}/gateway/stop`)
  return response.data
}

export async function restartGateway(workspaceId: number): Promise<GatewayStatus> {
  const response = await api.post<GatewayStatus>(`/workspaces/${workspaceId}/gateway/restart`)
  return response.data
}
