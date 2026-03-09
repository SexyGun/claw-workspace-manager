import { computed, reactive } from 'vue'

import { fetchMe, login as apiLogin, logout as apiLogout } from '../api'
import type { User } from '../types'

const state = reactive<{
  currentUser: User | null
  initialized: boolean
}>({
  currentUser: null,
  initialized: false,
})

export function useAuthStore() {
  async function ensureLoaded() {
    if (state.initialized) {
      return state.currentUser
    }
    try {
      state.currentUser = await fetchMe()
    } catch {
      state.currentUser = null
    } finally {
      state.initialized = true
    }
    return state.currentUser
  }

  async function login(username: string, password: string) {
    state.currentUser = await apiLogin(username, password)
    state.initialized = true
    return state.currentUser
  }

  async function logout() {
    await apiLogout()
    state.currentUser = null
    state.initialized = true
  }

  function reset() {
    state.currentUser = null
    state.initialized = false
  }

  return {
    state,
    currentUser: computed(() => state.currentUser),
    isAdmin: computed(() => state.currentUser?.role === 'admin'),
    ensureLoaded,
    login,
    logout,
    reset,
  }
}
