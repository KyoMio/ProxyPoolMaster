import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      redirect: '/dashboard'
    },
    {
      path: '/dashboard',
      name: 'dashboard',
      component: () => import('../views/DashboardView.vue')
    },
    {
      path: '/proxies',
      name: 'proxies',
      component: () => import('../views/ProxyListView.vue')
    },
    {
      path: '/collectors',
      name: 'collectors',
      component: () => import('../views/CollectorManagerView.vue')
    },
    {
      path: '/logs',
      name: 'logs',
      component: () => import('../views/LogView.vue')
    },
    {
      path: '/config',
      name: 'config',
      component: () => import('../views/ConfigView.vue')
    },
    {
      path: '/system',
      name: 'system',
      component: () => import('../views/SystemStatusView.vue')
    }
  ]
})

export default router
