<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch, computed } from 'vue'
import * as echarts from 'echarts'
import { useThemeStore } from '@/stores/theme'
import { useBreakpoint } from '@/composables/useBreakpoint'

interface MapDataItem {
  name: string
  value: number[] // [lng, lat, count]
}

const props = defineProps<{
  data: MapDataItem[]
  loading?: boolean
}>()

const emit = defineEmits<{
  countryClick: [name: string, value: number]
}>()

const themeStore = useThemeStore()
const { isMobile } = useBreakpoint()

// Refs
const mapContainer = ref<HTMLDivElement>()
let chart: echarts.ECharts | null = null
const mapLoaded = ref(false)

// Computed
const isDark = computed(() => themeStore.isDark)

// Load world map data
async function loadMapData() {
  try {
    const response = await fetch('/maps/world.json')
    if (!response.ok) throw new Error('Failed to load map')
    const worldJson = await response.json()
    echarts.registerMap('world', worldJson)
    mapLoaded.value = true
    initChart()
  } catch (error) {
    console.error('Failed to load world map:', error)
  }
}

// Initialize chart
function initChart() {
  if (!mapContainer.value || !mapLoaded.value) return
  
  chart = echarts.init(mapContainer.value)
  
  const option: any = {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'item',
      backgroundColor: isDark.value ? '#1e293b' : '#ffffff',
      borderColor: isDark.value ? '#334155' : '#e2e8f0',
      borderWidth: 1,
      padding: [10, 14],
      textStyle: {
        color: isDark.value ? '#f8fafc' : '#0f172a',
        fontSize: 13,
      },
      formatter: (params: any) => {
        if (params.value && params.value[2]) {
          return `<div style="font-weight:600;margin-bottom:4px;font-size:14px;">${params.name}</div>
                  <div style="color:${isDark.value ? '#4ade80' : '#22c55e'};font-size:13px;">可用代理: ${params.value[2]} 个</div>`
        }
        return params.name
      },
    },
    geo: {
      map: 'world',
      roam: !isMobile.value, // Disable roam on mobile
      zoom: isMobile.value ? 0.6 : 1.0,
      center: isMobile.value ? [0, 20] : [10, 20],
      silent: false,
      itemStyle: {
        areaColor: isDark.value ? '#1e293b' : '#f1f5f9',
        borderColor: isDark.value ? '#334155' : '#e2e8f0',
        borderWidth: 1,
      },
      emphasis: {
        disabled: true,
      },
    },
    series: [
      {
        type: 'scatter',
        coordinateSystem: 'geo',
        data: props.data,
        symbolSize: (val: any) => {
          return Math.max(8, Math.sqrt(val[2]) * 1.2)
        },
        itemStyle: {
          color: isDark.value ? '#4ade80' : '#22c55e',
          shadowBlur: 10,
          shadowColor: isDark.value ? 'rgba(74, 222, 128, 0.4)' : 'rgba(34, 197, 94, 0.4)',
        },
        emphasis: {
          scale: 1.5,
          itemStyle: {
            color: isDark.value ? '#86efac' : '#4ade80',
            shadowBlur: 20,
            shadowColor: isDark.value ? 'rgba(134, 239, 172, 0.6)' : 'rgba(74, 222, 128, 0.6)',
          },
        },
      },
      {
        type: 'effectScatter',
        coordinateSystem: 'geo',
        data: props.data.slice(0, 5), // Top 5 countries have ripple effect
        symbolSize: 12,
        showEffectOn: 'render',
        rippleEffect: {
          brushType: 'stroke',
          scale: 3,
          period: 4,
        },
        itemStyle: {
          color: isDark.value ? '#4ade80' : '#22c55e',
        },
        zlevel: 1,
      },
    ],
  }
  
  chart.setOption(option)
  
  // Click event
  chart.on('click', (params: any) => {
    if (params.componentType === 'series' && params.value) {
      emit('countryClick', params.name, params.value[2])
    }
  })
  
  // Resize on window resize
  window.addEventListener('resize', handleResize)
}

// Handle resize
function handleResize() {
  chart?.resize()
}

// Update chart when data changes
watch(() => props.data, (newData) => {
  if (!chart) return
  chart.setOption({
    series: [
      { data: newData },
      { data: newData.slice(0, 5) },
    ],
  })
}, { deep: true })

// Update chart when theme changes
watch(isDark, () => {
  if (!chart) return
  
  const newOption: any = {
    tooltip: {
      backgroundColor: isDark.value ? '#1e293b' : '#ffffff',
      borderColor: isDark.value ? '#334155' : '#e2e8f0',
      textStyle: {
        color: isDark.value ? '#f8fafc' : '#0f172a',
      },
    },
    geo: {
      itemStyle: {
        areaColor: isDark.value ? '#1e293b' : '#f1f5f9',
        borderColor: isDark.value ? '#334155' : '#e2e8f0',
      },
    },
    series: [
      {
        itemStyle: {
          color: isDark.value ? '#4ade80' : '#22c55e',
          shadowColor: isDark.value ? 'rgba(74, 222, 128, 0.4)' : 'rgba(34, 197, 94, 0.4)',
        },
        emphasis: {
          itemStyle: {
            color: isDark.value ? '#86efac' : '#4ade80',
            shadowColor: isDark.value ? 'rgba(134, 239, 172, 0.6)' : 'rgba(74, 222, 128, 0.6)',
          },
        },
      },
      {
        itemStyle: {
          color: isDark.value ? '#4ade80' : '#22c55e',
        },
      },
    ],
  }
  
  chart.setOption(newOption)
})

// Zoom controls
function zoomIn() {
  if (!chart) return
  const option = chart.getOption()
  const currentZoom = (option.geo as any)[0].zoom || 1
  chart.setOption({
    geo: { zoom: currentZoom * 1.2 } as any,
  })
}

function zoomOut() {
  if (!chart) return
  const option = chart.getOption()
  const currentZoom = (option.geo as any)[0].zoom || 1
  chart.setOption({
    geo: { zoom: currentZoom / 1.2 } as any,
  })
}

function resetZoom() {
  if (!chart) return
  chart.setOption({
    geo: {
      zoom: isMobile.value ? 0.6 : 1.0,
      center: isMobile.value ? [0, 20] : [10, 20],
    } as any,
  })
}

// Lifecycle
onMounted(() => {
  loadMapData()
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  chart?.dispose()
  chart = null
})
</script>

<template>
  <div class="world-map">
    <!-- Loading State -->
    <div v-if="!mapLoaded || loading" class="loading-overlay">
      <div class="loading-spinner"></div>
      <span class="loading-text">加载地图中...</span>
    </div>
    
    <!-- Map Container -->
    <div ref="mapContainer" class="map-container"></div>
    
    <!-- Zoom Controls -->
    <div class="map-controls">
      <button class="control-btn" @click="zoomIn" title="放大">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <line x1="12" y1="5" x2="12" y2="19"/>
          <line x1="5" y1="12" x2="19" y2="12"/>
        </svg>
      </button>
      <button class="control-btn" @click="resetZoom" title="重置">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <polyline points="23 4 23 10 17 10"/>
          <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/>
        </svg>
      </button>
      <button class="control-btn" @click="zoomOut" title="缩小">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <line x1="5" y1="12" x2="19" y2="12"/>
        </svg>
      </button>
    </div>
  </div>
</template>

<style scoped>
.world-map {
  position: relative;
  width: 100%;
  height: 100%;
  background: var(--bg-primary);
  border-radius: var(--radius-xl);
  overflow: hidden;
}

.map-container {
  width: 100%;
  height: 100%;
}

/* Loading Overlay */
.loading-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: var(--bg-primary);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  z-index: 10;
}

.loading-spinner {
  width: 32px;
  height: 32px;
  border: 3px solid var(--border-color);
  border-top-color: var(--accent-primary);
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.loading-text {
  font-size: 13px;
  color: var(--text-secondary);
}

/* Zoom Controls */
.map-controls {
  position: absolute;
  bottom: 16px;
  right: 16px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  z-index: 5;
}

.control-btn {
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--bg-primary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  color: var(--text-primary);
  cursor: pointer;
  box-shadow: var(--shadow);
  transition: all 0.2s ease;
}

.control-btn:hover {
  background: var(--bg-secondary);
  border-color: var(--accent-primary);
  color: var(--accent-primary);
}

.control-btn svg {
  stroke: currentColor;
}

@media (max-width: 767px) {
  .map-controls {
    bottom: 12px;
    right: 12px;
  }
  
  .control-btn {
    width: 32px;
    height: 32px;
  }
}
</style>
