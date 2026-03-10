import type { User } from '../types'

import { api } from './client'

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
