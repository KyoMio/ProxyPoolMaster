<script setup lang="ts">
import { useThemeStore } from '@/stores/theme'

const themeStore = useThemeStore()

function handleToggle() {
  themeStore.toggleTheme()
}
</script>

<template>
  <button
    class="theme-toggle"
    :title="themeStore.isDark ? '切换到浅色模式' : '切换到深色模式'"
    @click="handleToggle"
  >
    <span v-if="themeStore.isDark" class="icon">☀️</span>
    <span v-else class="icon">🌙</span>
  </button>
</template>

<style scoped>
.theme-toggle {
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  font-size: 16px;
  color: var(--text-secondary);
  cursor: pointer;
  transition: all 0.2s ease;
}

.theme-toggle:hover {
  border-color: var(--accent-primary);
  color: var(--accent-primary);
}

.icon {
  line-height: 1;
}
</style>
