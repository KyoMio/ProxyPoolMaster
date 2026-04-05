<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import ThemeToggle from '@/components/common/ThemeToggle.vue'
import TokenSettingsDialog from '@/components/common/TokenSettingsDialog.vue'
import { dashboardRealtimeClient } from '@/services/realtime'
import { OPEN_TOKEN_DIALOG_EVENT } from '@/constants/events'

defineProps<{
  title: string
  showMenuBtn?: boolean
}>()

const emit = defineEmits<{
  menuClick: []
}>()

function handleMenuClick() {
  emit('menuClick')
}

// Token dialog
const showTokenDialog = ref(false)

const wsStatus = dashboardRealtimeClient.status

function handleWsClick() {
  if (wsStatus.value === 'disconnected') {
    dashboardRealtimeClient.reconnect()
  }
}

function openTokenDialog() {
  showTokenDialog.value = true
}

function handleOpenTokenDialogEvent() {
  openTokenDialog()
}

onMounted(() => {
  if (typeof window !== 'undefined') {
    window.addEventListener(OPEN_TOKEN_DIALOG_EVENT, handleOpenTokenDialogEvent)
  }
  dashboardRealtimeClient.connect()
})

onUnmounted(() => {
  if (typeof window !== 'undefined') {
    window.removeEventListener(OPEN_TOKEN_DIALOG_EVENT, handleOpenTokenDialogEvent)
  }
  dashboardRealtimeClient.disconnect()
})
</script>

<template>
  <header class="header">
    <div class="header-left">
      <button 
        v-if="showMenuBtn" 
        class="menu-btn"
        @click="handleMenuClick"
      >
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <line x1="3" y1="12" x2="21" y2="12"/>
          <line x1="3" y1="6" x2="21" y2="6"/>
          <line x1="3" y1="18" x2="21" y2="18"/>
        </svg>
      </button>
      <h1 class="page-title">{{ title }}</h1>
    </div>
    
    <div class="header-actions">
      <!-- WS Status Indicator -->
      <button 
        class="icon-btn ws-status-btn" 
        :class="wsStatus"
        :title="wsStatus === 'connected' ? 'WebSocket Connected' : wsStatus === 'connecting' ? 'Connecting...' : 'WebSocket Disconnected - Click to reconnect'"
        @click="handleWsClick"
      >
        <span class="ws-indicator" :class="wsStatus"></span>
      </button>
      
      <!-- Theme Toggle -->
      <ThemeToggle />
      
      <!-- Token Settings -->
      <button class="icon-btn" title="API Token" @click="openTokenDialog">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <rect x="3" y="11" width="18" height="11" rx="2" ry="2"/>
          <path d="M7 11V7a5 5 0 0 1 10 0v4"/>
        </svg>
      </button>
    </div>
    
    <!-- Token Dialog -->
    <TokenSettingsDialog v-model="showTokenDialog" />
  </header>
</template>

<style scoped>
.header {
  height: var(--header-height);
  background: var(--bg-primary);
  border-bottom: 1px solid var(--border-color);
  padding: 0 24px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-shrink: 0;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.menu-btn {
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  color: var(--text-secondary);
  cursor: pointer;
  transition: all 0.2s ease;
}

.menu-btn:hover {
  border-color: var(--accent-primary);
  color: var(--accent-primary);
}

.page-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.icon-btn {
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  color: var(--text-secondary);
  cursor: pointer;
  transition: all 0.2s ease;
}

.icon-btn:hover {
  border-color: var(--accent-primary);
  color: var(--accent-primary);
}

.icon-btn svg {
  stroke: currentColor;
}

@media (max-width: 1023px) {
  .header {
    padding: 0 16px;
  }
}

/* WebSocket Status Indicator */
.ws-status-btn {
  position: relative;
}

.ws-indicator {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  display: block;
}

.ws-indicator.connected {
  background: #22c55e;
  box-shadow: 0 0 6px #22c55e;
  animation: pulse 2s infinite;
}

.ws-indicator.connecting {
  background: #f59e0b;
  animation: pulse 1s infinite;
}

.ws-indicator.disconnected {
  background: #ef4444;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}
</style>
