<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import Sidebar from '@/components/layout/Sidebar.vue'
import Header from '@/components/layout/Header.vue'
import { useBreakpoint } from '@/composables/useBreakpoint'

const route = useRoute()
const { isMobile, isTablet } = useBreakpoint()

// Sidebar collapsed state
const sidebarCollapsed = ref(false)
const mobileSidebarOpen = ref(false)

// Page titles
const pageTitles: Record<string, string> = {
  '/dashboard': '仪表盘',
  '/proxies': '代理列表',
  '/collectors': '收集器管理',
  '/logs': '日志查看',
  '/config': '配置管理',
  '/system': '系统状态',
}

const pageTitle = computed(() => {
  return pageTitles[route.path] || 'ProxyPool'
})

// Handle mobile sidebar
function openMobileSidebar() {
  mobileSidebarOpen.value = true
}

function closeMobileSidebar() {
  mobileSidebarOpen.value = false
}

// Watch for route changes to close mobile sidebar
onMounted(() => {
  // Auto-collapse sidebar on small screens
  if (isTablet.value) {
    sidebarCollapsed.value = true
  }
})
</script>

<template>
  <div class="layout">
    <!-- Sidebar -->
    <Sidebar 
      v-model:collapsed="sidebarCollapsed"
      :class="{ open: mobileSidebarOpen }"
    />
    
    <!-- Mobile Overlay -->
    <div 
      v-if="mobileSidebarOpen && isMobile" 
      class="mobile-overlay"
      @click="closeMobileSidebar"
    />

    <!-- Main Content -->
    <div class="main-content">
      <Header 
        :title="pageTitle"
        :show-menu-btn="isMobile || isTablet"
        @menu-click="openMobileSidebar"
      />
      
      <main class="page-content">
        <router-view />
      </main>
    </div>
  </div>
</template>

<style>
.layout {
  display: flex;
  height: 100vh;
  overflow: hidden;
}

.main-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  min-width: 0;
}

.page-content {
  flex: 1;
  overflow: auto;
  padding: 20px 24px;
}

.mobile-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  z-index: 99;
}

@media (max-width: 1023px) {
  .page-content {
    padding: 16px;
  }
}
</style>
