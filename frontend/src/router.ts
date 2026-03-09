import { createRouter, createWebHistory } from 'vue-router'

import { useAuthStore } from './stores/auth'

const routes = [
  {
    path: '/login',
    name: 'login',
    component: () => import('./views/LoginView.vue'),
    meta: { guestOnly: true },
  },
  {
    path: '/',
    redirect: '/workspaces',
  },
  {
    path: '/workspaces',
    name: 'workspaces',
    component: () => import('./views/WorkspacesView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/workspaces/:id',
    name: 'workspace-detail',
    component: () => import('./views/WorkspaceDetailView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/users',
    name: 'users',
    component: () => import('./views/UsersView.vue'),
    meta: { requiresAuth: true, requiresAdmin: true },
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach(async (to) => {
  const auth = useAuthStore()
  const currentUser = await auth.ensureLoaded()

  if (to.meta.requiresAuth && !currentUser) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }

  if (to.meta.guestOnly && currentUser) {
    return { name: 'workspaces' }
  }

  if (to.meta.requiresAdmin && currentUser?.role !== 'admin') {
    return { name: 'workspaces' }
  }

  return true
})

export default router
