import { ref, computed, onMounted, onUnmounted } from 'vue'

// Breakpoints (mobile-first)
const breakpoints = {
  sm: 480,   // Mobile landscape
  md: 768,   // Tablet
  lg: 1024,  // Desktop
  xl: 1440,  // Large desktop
}

export function useBreakpoint() {
  const width = ref(window.innerWidth)
  const height = ref(window.innerHeight)
  
  // Computed
  const breakpoint = computed(() => {
    const w = width.value
    if (w < breakpoints.sm) return 'xs'
    if (w < breakpoints.md) return 'sm'
    if (w < breakpoints.lg) return 'md'
    if (w < breakpoints.xl) return 'lg'
    return 'xl'
  })
  
  const isMobile = computed(() => width.value < breakpoints.md)
  const isTablet = computed(() => width.value >= breakpoints.md && width.value < breakpoints.lg)
  const isDesktop = computed(() => width.value >= breakpoints.lg)
  
  const isSmallScreen = computed(() => width.value < 900)
  
  // Methods
  function update() {
    width.value = window.innerWidth
    height.value = window.innerHeight
  }
  
  // Lifecycle
  onMounted(() => {
    window.addEventListener('resize', update)
  })
  
  onUnmounted(() => {
    window.removeEventListener('resize', update)
  })
  
  return {
    width,
    height,
    breakpoint,
    isMobile,
    isTablet,
    isDesktop,
    isSmallScreen,
  }
}
