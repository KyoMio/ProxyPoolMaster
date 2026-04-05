<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getRuntimeInfo } from '@/api/apiClient'
import { useBreakpoint } from '@/composables/useBreakpoint'
import { appBuildLabel } from '@/config/buildInfo'

interface NavItem {
  name: string
  path: string
  icon: string
  title: string
}

const props = defineProps<{
  collapsed: boolean
}>()

const emit = defineEmits<{
  'update:collapsed': [value: boolean]
}>()

const route = useRoute()
const router = useRouter()
const { isMobile } = useBreakpoint()
const buildLabel = ref(appBuildLabel)

const navItems: NavItem[] = [
  { name: 'dashboard', path: '/dashboard', icon: 'LayoutGrid', title: '仪表盘' },
  { name: 'proxies', path: '/proxies', icon: 'Globe', title: '代理列表' },
  { name: 'collectors', path: '/collectors', icon: 'Collection', title: '收集器管理' },
  { name: 'logs', path: '/logs', icon: 'FileText', title: '日志查看' },
  { name: 'config', path: '/config', icon: 'Settings', title: '配置管理' },
  { name: 'system', path: '/system', icon: 'Monitor', title: '系统状态' },
]

const activeRoute = computed(() => route.path)

function isActive(path: string): boolean {
  return route.path === path || route.path.startsWith(path + '/')
}

function navigate(item: NavItem) {
  router.push(item.path)
  if (isMobile.value) {
    emit('update:collapsed', true)
  }
}

function toggleSidebar() {
  emit('update:collapsed', !props.collapsed)
}

onMounted(async () => {
  try {
    const runtimeInfo = await getRuntimeInfo()
    if (runtimeInfo?.label?.trim()) {
      buildLabel.value = runtimeInfo.label.trim()
    }
  } catch {
    // 运行时信息获取失败时使用构建期信息兜底
  }
})
</script>

<template>
  <aside class="sidebar" :class="{ collapsed: props.collapsed }">
    <!-- Header -->
    <div class="sidebar-header">
      <div class="logo" @click="toggleSidebar">
        <span class="logo-text">ProxyPool<span class="logo-accent">Master</span></span>
        <span class="logo-icon" title="展开">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
            <polygon points="12 2 2 7 12 12 22 7 12 2"/>
            <polyline points="2 17 12 22 22 17"/>
            <polyline points="2 12 12 17 22 12"/>
          </svg>
        </span>
      </div>
      <button class="sidebar-toggle" @click="toggleSidebar" title="收起">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <polyline points="15 18 9 12 15 6"/>
        </svg>
      </button>
    </div>

    <!-- Navigation -->
    <nav class="nav-menu">
      <a
        v-for="item in navItems"
        :key="item.name"
        class="nav-item"
        :class="{ active: isActive(item.path) }"
        :title="item.title"
        @click.prevent="navigate(item)"
      >
        <span class="nav-icon">
          <!-- Dashboard -->
          <svg v-if="item.icon === 'LayoutGrid'" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <rect x="3" y="3" width="7" height="7"/>
            <rect x="14" y="3" width="7" height="7"/>
            <rect x="14" y="14" width="7" height="7"/>
            <rect x="3" y="14" width="7" height="7"/>
          </svg>
          <!-- Globe -->
          <svg v-else-if="item.icon === 'Globe'" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="12" cy="12" r="10"/>
            <line x1="2" y1="12" x2="22" y2="12"/>
            <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/>
          </svg>
          <!-- Collection -->
          <svg v-else-if="item.icon === 'Collection'" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <rect x="3" y="3" width="18" height="18" rx="2"/>
            <path d="M3 9h18"/>
            <path d="M9 21V9"/>
          </svg>
          <!-- FileText -->
          <svg v-else-if="item.icon === 'FileText'" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
            <polyline points="14 2 14 8 20 8"/>
            <line x1="16" y1="13" x2="8" y2="13"/>
            <line x1="16" y1="17" x2="8" y2="17"/>
            <polyline points="10 9 9 9 8 9"/>
          </svg>
          <!-- Settings -->
          <svg v-else-if="item.icon === 'Settings'" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="12" cy="12" r="3"/>
            <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/>
          </svg>
          <!-- Monitor -->
          <svg v-else-if="item.icon === 'Monitor'" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <rect x="2" y="3" width="20" height="14" rx="2"/>
            <line x1="8" y1="21" x2="16" y2="21"/>
            <line x1="12" y1="17" x2="12" y2="21"/>
          </svg>
        </span>
        <span class="nav-text">{{ item.title }}</span>
      </a>
    </nav>

    <!-- Footer -->
    <div class="sidebar-footer">
      <span>{{ buildLabel }}</span>
    </div>
  </aside>
</template>

<style scoped>
.sidebar {
  width: var(--sidebar-width);
  background: var(--bg-primary);
  border-right: 1px solid var(--border-color);
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
  transition: width 0.3s var(--ease-out);
  height: 100vh;
}

.sidebar.collapsed {
  width: var(--sidebar-collapsed-width);
}

/* Header */
.sidebar-header {
  height: var(--header-height);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 12px;
  border-bottom: 1px solid var(--border-color);
  gap: 8px;
}

.logo {
  font-size: 18px;
  font-weight: 700;
  display: flex;
  align-items: center;
  gap: 2px;
  cursor: pointer;
  user-select: none;
}

.logo-text {
  display: flex;
  align-items: center;
  gap: 2px;
}

.logo-accent {
  color: var(--accent-primary);
}

.logo-icon {
  display: none;
  width: 36px;
  height: 36px;
  align-items: center;
  justify-content: center;
  background: var(--accent-primary);
  color: white;
  border-radius: 8px;
}

.sidebar-toggle {
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: 6px;
  color: var(--text-secondary);
  cursor: pointer;
  transition: all 0.2s ease;
  flex-shrink: 0;
}

.sidebar-toggle:hover {
  border-color: var(--accent-primary);
  color: var(--accent-primary);
}

/* Collapsed state */
.sidebar.collapsed .sidebar-header {
  justify-content: center;
  padding: 0;
}

.sidebar.collapsed .logo-text {
  display: none;
}

.sidebar.collapsed .logo-icon {
  display: flex;
}

.sidebar.collapsed .sidebar-toggle {
  display: none;
}

/* Navigation */
.nav-menu {
  flex: 1;
  padding: 12px 0;
  overflow-y: auto;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  margin: 4px 12px;
  color: var(--text-secondary);
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  border-radius: var(--radius-md);
  transition: all 0.2s ease;
  text-decoration: none;
}

.nav-item:hover {
  background: var(--bg-secondary);
  color: var(--text-primary);
}

.nav-item.active {
  background: rgba(8, 145, 178, 0.08);
  color: var(--accent-primary);
}

.nav-icon {
  width: 20px;
  height: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.nav-icon svg {
  width: 18px;
  height: 18px;
  stroke: currentColor;
}

.nav-text {
  white-space: nowrap;
}

/* Collapsed navigation */
.sidebar.collapsed .nav-item {
  justify-content: center;
  padding: 12px;
  margin: 4px 8px;
}

.sidebar.collapsed .nav-text {
  display: none;
}

/* Footer */
.sidebar-footer {
  padding: 16px;
  border-top: 1px solid var(--border-color);
  font-size: 12px;
  color: var(--text-tertiary);
  text-align: center;
}

.sidebar.collapsed .sidebar-footer {
  display: none;
}

/* Mobile overlay */
@media (max-width: 1023px) {
  .sidebar {
    position: fixed;
    left: 0;
    top: 0;
    bottom: 0;
    z-index: 100;
    transform: translateX(-100%);
  }
  
  .sidebar.open {
    transform: translateX(0);
  }
  
  .sidebar.collapsed {
    transform: translateX(-100%);
  }
}
</style>
