import { defineStore } from 'pinia'
import { ref, computed, watch } from 'vue'

export type Theme = 'light' | 'dark' | 'auto'

export const useThemeStore = defineStore('theme', () => {
  // State
  const theme = ref<Theme>('auto')
  const systemDark = ref(false)
  
  // Computed
  const isDark = computed(() => {
    if (theme.value === 'auto') {
      return systemDark.value
    }
    return theme.value === 'dark'
  })
  
  const currentTheme = computed(() => {
    if (theme.value === 'auto') {
      return systemDark.value ? 'dark' : 'light'
    }
    return theme.value
  })
  
  // Actions
  function setTheme(newTheme: Theme) {
    theme.value = newTheme
    localStorage.setItem('theme', newTheme)
    applyTheme()
  }
  
  function toggleTheme() {
    const newTheme = isDark.value ? 'light' : 'dark'
    setTheme(newTheme)
  }
  
  function applyTheme() {
    const root = document.documentElement
    const isDarkMode = isDark.value
    
    if (isDarkMode) {
      root.setAttribute('data-theme', 'dark')
    } else {
      root.removeAttribute('data-theme')
    }
  }
  
  function initTheme() {
    // Load from localStorage
    const saved = localStorage.getItem('theme') as Theme
    if (saved && ['light', 'dark', 'auto'].includes(saved)) {
      theme.value = saved
    }
    
    // Listen to system theme changes
    const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)')
    systemDark.value = mediaQuery.matches
    
    mediaQuery.addEventListener('change', (e) => {
      systemDark.value = e.matches
      if (theme.value === 'auto') {
        applyTheme()
      }
    })
    
    // Apply initial theme
    applyTheme()
  }
  
  // Watch for theme changes
  watch(theme, applyTheme)
  watch(systemDark, () => {
    if (theme.value === 'auto') {
      applyTheme()
    }
  })
  
  return {
    theme,
    isDark,
    currentTheme,
    setTheme,
    toggleTheme,
    initTheme,
  }
})
