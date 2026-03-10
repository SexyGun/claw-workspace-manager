import type { User } from '../types'

import { api } from './client'

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
