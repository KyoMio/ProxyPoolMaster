<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import WorldMap from '@/components/charts/WorldMap.vue'
import { useThemeStore } from '@/stores/theme'
import { getDashboardOverview } from '@/api/apiClient'
import { normalizeApiBaseUrl } from '@/api/baseUrl'
import { OPEN_TOKEN_DIALOG_EVENT } from '@/constants/events'
import { ElMessage } from 'element-plus'
import { dashboardRealtimeClient } from '@/services/realtime'
import { buildRandomProxyUrl, appendTokenToUrl } from './dashboardQuickStart'

const themeStore = useThemeStore()

// Loading state
const loading = ref(true)

// Stats
const stats = ref({
  total: 0,
  available: 0,
  avgLatency: 0,
  lastUpdate: '-',
})

// Grade distribution
const gradeData = ref([
  { value: 0, name: 'S级', itemStyle: { color: '#22c55e' } },
  { value: 0, name: 'A级', itemStyle: { color: '#3b82f6' } },
  { value: 0, name: 'B级', itemStyle: { color: '#f59e0b' } },
  { value: 0, name: 'C级', itemStyle: { color: '#94a3b8' } },
])

// Type distribution
const typeData = ref([
  { value: 0, name: 'HTTP', itemStyle: { color: '#0891b2' } },
  { value: 0, name: 'HTTPS', itemStyle: { color: '#3b82f6' } },
  { value: 0, name: 'SOCKS5', itemStyle: { color: '#f97316' } },
])

// Country coordinates mapping (for world map)
const countryCoordinates: Record<string, [number, number]> = {
  'CN': [104.195397, 35.86166],      // 中国
  'US': [-95.712891, 37.09024],      // 美国
  'JP': [138.252924, 36.204824],     // 日本
  'DE': [10.451526, 51.165691],      // 德国
  'GB': [-3.435973, 55.378051],      // 英国
  'SG': [103.819836, 1.352083],      // 新加坡
  'KR': [127.766922, 35.907757],     // 韩国
  'FR': [2.213749, 46.227638],       // 法国
  'CA': [-106.346771, 56.130366],    // 加拿大
  'AU': [133.775136, -25.274398],    // 澳大利亚
  'NL': [5.291266, 52.132633],       // 荷兰
  'RU': [105.318756, 61.52401],      // 俄罗斯
  'IN': [78.96288, 20.593684],       // 印度
  'BR': [-51.92528, -14.235004],     // 巴西
  'HK': [114.169361, 22.319303],     // 香港
  'TW': [120.960515, 23.69781],      // 台湾
  'VN': [108.277199, 14.058324],     // 越南
  'TH': [100.992541, 15.870032],     // 泰国
  'MY': [101.975766, 4.210484],      // 马来西亚
  'ID': [113.921327, -0.789275],     // 印尼
  'PH': [121.774017, 12.879721],     // 菲律宾
  'IT': [12.56738, 41.87194],        // 意大利
  'ES': [-3.74922, 40.463667],       // 西班牙
  'PL': [19.145136, 51.919438],      // 波兰
  'SE': [18.643501, 60.128161],      // 瑞典
  'CH': [8.227512, 46.818188],       // 瑞士
  'TR': [35.243322, 38.963745],      // 土耳其
  'UA': [31.16558, 48.379433],       // 乌克兰
  'MX': [-102.552784, 23.634501],    // 墨西哥
  'ZA': [22.937506, -30.559482],     // 南非
}

// World Map Data
const mapData = ref<any[]>([])
const countryCount = computed(() => mapData.value.length)
const topCountries = computed(() =>
  mapData.value.slice(0, 5).map((item: any) => ({
    code: item.code,
    name: item.name,
    count: item.value[2],
  })),
)

const apiBaseUrl = normalizeApiBaseUrl(import.meta.env.VITE_API_BASE_URL)
const pageOrigin = typeof window !== 'undefined' ? window.location.origin : ''
const randomProxyUrl = computed(() => buildRandomProxyUrl(apiBaseUrl, pageOrigin))

function fallbackCopyToClipboard(text: string): boolean {
  if (typeof document === 'undefined') {
    return false
  }

  const textarea = document.createElement('textarea')
  textarea.value = text
  textarea.setAttribute('readonly', '')
  textarea.style.position = 'fixed'
  textarea.style.opacity = '0'
  document.body.appendChild(textarea)
  textarea.select()

  let success = false
  try {
    success = document.execCommand('copy')
  } catch {
    success = false
  }

  document.body.removeChild(textarea)
  return success
}

async function copyQuickStartUrl() {
  const token = (localStorage.getItem('api_token') || '').trim()
  if (!token) {
    ElMessage.warning('请先配置 API Token')
    if (typeof window !== 'undefined') {
      window.dispatchEvent(new Event(OPEN_TOKEN_DIALOG_EVENT))
    }
    return
  }

  const urlWithToken = appendTokenToUrl(randomProxyUrl.value, token)
  try {
    if (typeof navigator !== 'undefined' && navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(urlWithToken)
      ElMessage.success('已复制随机代理 URL（含 Token）')
      return
    }
  } catch {
    // 忽略，回退到 execCommand 复制
  }

  if (fallbackCopyToClipboard(urlWithToken)) {
    ElMessage.success('已复制随机代理 URL（含 Token）')
    return
  }

  ElMessage.error('复制失败，请手动复制')
}

// Format time ago
function formatTimeAgo(dateStr: string): string {
  if (!dateStr || dateStr === '-') return '-'
  
  const date = new Date(dateStr)
  const now = new Date()
  const diff = Math.floor((now.getTime() - date.getTime()) / 1000)
  
  if (diff < 60) return '刚刚'
  if (diff < 3600) return `${Math.floor(diff / 60)}分钟前`
  if (diff < 86400) return `${Math.floor(diff / 3600)}小时前`
  return `${Math.floor(diff / 86400)}天前`
}

function applyOverview(overview: any) {
  // Update stats
  // Note: avg_response_time from backend is already in milliseconds
  stats.value = {
    total: overview.total_proxies || 0,
    available: overview.available_proxies || 0,
    avgLatency: Math.round(overview.avg_response_time || 0),
    lastUpdate: formatTimeAgo(overview.last_updated),
  }

  // Update grade distribution
  const gradeDist = overview.available_grade_distribution || {}
  gradeData.value = [
    { value: gradeDist['S'] || 0, name: 'S级', itemStyle: { color: '#22c55e' } },
    { value: gradeDist['A'] || 0, name: 'A级', itemStyle: { color: '#3b82f6' } },
    { value: gradeDist['B'] || 0, name: 'B级', itemStyle: { color: '#f59e0b' } },
    { value: gradeDist['C'] || 0, name: 'C级', itemStyle: { color: '#94a3b8' } },
  ].filter(g => g.value > 0)

  // Update type distribution
  const typeDist = overview.available_proxy_type_distribution || []
  const typeMap: Record<string, number> = {}
  typeDist.forEach((item: any) => {
    typeMap[item.protocol?.toUpperCase() || 'UNKNOWN'] = item.count || 0
  })
  typeData.value = [
    { value: typeMap['HTTP'] || 0, name: 'HTTP', itemStyle: { color: '#0891b2' } },
    { value: typeMap['HTTPS'] || 0, name: 'HTTPS', itemStyle: { color: '#3b82f6' } },
    { value: typeMap['SOCKS4'] || 0, name: 'SOCKS4', itemStyle: { color: '#a855f7' } },
    { value: typeMap['SOCKS5'] || 0, name: 'SOCKS5', itemStyle: { color: '#f97316' } },
  ].filter(t => t.value > 0)

  // Update map data
  const countryDist = overview.available_country_distribution || []
  mapData.value = countryDist
    .map((item: any) => {
      const countryCode = (item.country_code || '').toUpperCase()
      const coords = countryCoordinates[countryCode]
      if (!coords) {
        return null
      }
      return {
        name: item.country_name || countryCode,
        code: countryCode,
        value: [coords[0], coords[1], item.count || 0],
      }
    })
    .filter(Boolean)
    .sort((a: any, b: any) => b.value[2] - a.value[2])

}

// Load dashboard data (manual refresh)
async function loadDashboardData() {
  loading.value = true
  try {
    const overview = await getDashboardOverview()
    applyOverview(overview)
  } catch (error: any) {
    console.error('Failed to load dashboard data:', error)
    ElMessage.error('获取仪表盘数据失败: ' + (error.response?.data?.detail || error.message))
  } finally {
    loading.value = false
  }
}

function handleRealtimeOverview(message: any) {
  if (!message?.data) {
    return
  }
  applyOverview(message.data)
  loading.value = false
}

// Handle country click
function handleCountryClick(name: string, value: number) {
  console.log('Country clicked:', name, value)
}

// Theme
const isDark = computed(() => themeStore.isDark)

let unsubscribeInitial: (() => void) | null = null
let unsubscribeUpdate: (() => void) | null = null

// Lifecycle
onMounted(() => {
  loadDashboardData()
  unsubscribeInitial = dashboardRealtimeClient.subscribe('initial', handleRealtimeOverview)
  unsubscribeUpdate = dashboardRealtimeClient.subscribe('update', handleRealtimeOverview)
  dashboardRealtimeClient.connect()
})

onUnmounted(() => {
  unsubscribeInitial?.()
  unsubscribeUpdate?.()
  unsubscribeInitial = null
  unsubscribeUpdate = null
})
</script>

<template>
  <div class="dashboard" v-loading="loading">
    <div class="quick-start-bar">
      <div class="quick-start-left">
        <span class="quick-start-tag">快速开始</span>
        <div class="quick-start-content">
          <span class="quick-start-label">获取随机代理</span>
          <code class="quick-start-url">{{ randomProxyUrl }}</code>
        </div>
      </div>
      <button class="quick-start-copy-btn" @click="copyQuickStartUrl">
        复制带 Token URL
      </button>
    </div>

    <!-- Stats Row -->
    <div class="stats-row">
      <div class="stat-card">
        <div class="stat-header">
          <div class="stat-dot blue"></div>
          <span class="stat-label">总代理数</span>
        </div>
        <div class="stat-value">{{ stats.total.toLocaleString() }}</div>
      </div>
      
      <div class="stat-card">
        <div class="stat-header">
          <div class="stat-dot green"></div>
          <span class="stat-label">可用代理(B级及以上)</span>
        </div>
        <div class="stat-value">{{ stats.available.toLocaleString() }}</div>
      </div>
      
      <div class="stat-card">
        <div class="stat-header">
          <div class="stat-dot orange"></div>
          <span class="stat-label">平均延迟</span>
        </div>
        <div class="stat-value">
          {{ stats.avgLatency }}
          <span class="stat-unit">ms</span>
        </div>
      </div>
      
      <div class="stat-card">
        <div class="stat-header">
          <div class="stat-dot purple"></div>
          <span class="stat-label">最近更新</span>
        </div>
        <div class="stat-value">{{ stats.lastUpdate }}</div>
      </div>
    </div>

    <!-- Middle Section: Top Countries + Map -->
    <div class="middle-section">
      <div class="filter-bar">
        <div class="country-summary">
          <div
            v-for="country in topCountries"
            :key="country.code"
            class="country-pill"
          >
            <span class="country-name">{{ country.name }}</span>
            <span class="country-pill-count">{{ country.count }}</span>
          </div>
          <span v-if="!topCountries.length" class="country-empty">
            暂无国家分布数据
          </span>
        </div>
        <button class="filter-btn sort-btn" @click="loadDashboardData">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polyline points="23 4 23 10 17 10"/>
            <polyline points="1 20 1 14 7 14"/>
            <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/>
          </svg>
          刷新
        </button>
      </div>
      
      <!-- Map Info -->
      <div class="map-info">
        代理分布在 {{ countryCount }} 个国家和地区
      </div>
      
      <!-- World Map -->
      <div class="map-wrapper">
        <WorldMap 
          :data="mapData"
          :loading="loading"
          @country-click="handleCountryClick"
        />
      </div>
    </div>

    <!-- Bottom Charts -->
    <div class="charts-row">
      <!-- Grade Distribution -->
      <div class="chart-card">
        <div class="chart-header">
          <span class="chart-title">等级分布</span>
        </div>
        <div class="chart-body">
          <div class="pie-chart-container">
            <div 
              v-for="item in gradeData" 
              :key="item.name"
              class="pie-legend-item"
            >
              <span class="legend-dot" :style="{ background: item.itemStyle.color }"></span>
              <span class="legend-name">{{ item.name }}</span>
              <span class="legend-value">{{ item.value }}</span>
            </div>
          </div>
          <div class="pie-chart-visual">
            <svg viewBox="0 0 100 100" class="pie-svg">
              <circle
                v-for="(item, index) in gradeData"
                :key="item.name"
                cx="50"
                cy="50"
                r="40"
                fill="none"
                :stroke="item.itemStyle.color"
                :stroke-width="20"
                :stroke-dasharray="stats.available > 0 ? `${(item.value / stats.available) * 251.2} 251.2` : '0 251.2'"
                :stroke-dashoffset="-gradeData.slice(0, index).reduce((sum, i) => sum + (stats.available > 0 ? (i.value / stats.available) * 251.2 : 0), 0)"
                transform="rotate(-90 50 50)"
              />
              <circle cx="50" cy="50" r="25" :fill="isDark ? '#0f172a' : '#ffffff'" />
            </svg>
          </div>
        </div>
      </div>
      
      <!-- Type Distribution -->
      <div class="chart-card">
        <div class="chart-header">
          <span class="chart-title">类型分布</span>
        </div>
        <div class="chart-body">
          <div class="pie-chart-container">
            <div 
              v-for="item in typeData" 
              :key="item.name"
              class="pie-legend-item"
            >
              <span class="legend-dot" :style="{ background: item.itemStyle.color }"></span>
              <span class="legend-name">{{ item.name }}</span>
              <span class="legend-value">
                {{ stats.available > 0 ? Math.round((item.value / stats.available) * 100) : 0 }}%
              </span>
            </div>
          </div>
          <div class="pie-chart-visual">
            <svg viewBox="0 0 100 100" class="pie-svg">
              <circle
                v-for="(item, index) in typeData"
                :key="item.name"
                cx="50"
                cy="50"
                r="40"
                fill="none"
                :stroke="item.itemStyle.color"
                :stroke-width="20"
                :stroke-dasharray="stats.available > 0 ? `${(item.value / stats.available) * 251.2} 251.2` : '0 251.2'"
                :stroke-dashoffset="-typeData.slice(0, index).reduce((sum, i) => sum + (stats.available > 0 ? (i.value / stats.available) * 251.2 : 0), 0)"
                transform="rotate(-90 50 50)"
              />
              <circle cx="50" cy="50" r="25" :fill="isDark ? '#0f172a' : '#ffffff'" />
            </svg>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.dashboard {
  display: flex;
  flex-direction: column;
  gap: 16px;
  height: 100%;
  overflow: hidden;
}

.quick-start-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 14px;
  background: linear-gradient(90deg, rgba(59, 130, 246, 0.08), rgba(16, 185, 129, 0.08));
  border: 1px solid rgba(59, 130, 246, 0.2);
  border-radius: var(--radius-lg);
  flex-shrink: 0;
}

.quick-start-left {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.quick-start-tag {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 4px 10px;
  border-radius: 999px;
  background: rgba(59, 130, 246, 0.12);
  color: #1d4ed8;
  font-size: 12px;
  font-weight: 600;
  white-space: nowrap;
}

.quick-start-content {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.quick-start-label {
  font-size: 13px;
  color: var(--text-secondary);
  white-space: nowrap;
}

.quick-start-url {
  font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
  font-size: 12px;
  color: var(--text-primary);
  background: var(--bg-primary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-sm);
  padding: 4px 8px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.quick-start-copy-btn {
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  height: 32px;
  padding: 0 12px;
  border-radius: var(--radius-md);
  border: 1px solid var(--accent-primary);
  background: var(--bg-primary);
  color: var(--accent-primary);
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
}

.quick-start-copy-btn:hover {
  background: var(--accent-primary);
  color: #ffffff;
}

/* Stats Row */
.stats-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  flex-shrink: 0;
}

.stat-card {
  background: var(--bg-primary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  transition: all 0.2s ease;
}

.stat-card:hover {
  box-shadow: var(--shadow-sm);
}

.stat-header {
  display: flex;
  align-items: center;
  gap: 8px;
}

.stat-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.stat-dot.blue { background: #3b82f6; }
.stat-dot.green { background: #22c55e; }
.stat-dot.orange { background: #f59e0b; }
.stat-dot.purple { background: #8b5cf6; }

.stat-label {
  font-size: 12px;
  color: var(--text-secondary);
}

.stat-value {
  font-size: 24px;
  font-weight: 700;
  color: var(--text-primary);
  display: flex;
  align-items: baseline;
  gap: 2px;
}

.stat-unit {
  font-size: 12px;
  font-weight: 500;
  color: var(--text-secondary);
}

/* Middle Section */
.middle-section {
  display: flex;
  flex-direction: column;
  gap: 12px;
  flex: 1;
  min-height: 0;
}

/* Filter Bar */
.filter-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  flex-shrink: 0;
}

.country-summary {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  min-height: 32px;
}

.country-pill {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 6px 12px;
  background: var(--bg-primary);
  border: 1px solid var(--border-color);
  border-radius: 16px;
  font-size: 12px;
  color: var(--text-secondary);
}

.country-name {
  color: var(--text-primary);
}

.country-pill-count {
  color: var(--accent-primary);
  font-weight: 600;
}

.country-empty {
  font-size: 12px;
  color: var(--text-tertiary);
}

.filter-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  background: var(--bg-primary);
  border: 1px solid var(--border-color);
  border-radius: 16px;
  font-size: 12px;
  color: var(--text-secondary);
  cursor: pointer;
  transition: all 0.2s ease;
}

.filter-btn:hover {
  border-color: var(--accent-primary);
  color: var(--text-primary);
}

.sort-btn {
  margin-left: auto;
  display: flex;
  align-items: center;
  gap: 4px;
}

.sort-btn svg {
  stroke: currentColor;
}

/* Map Info */
.map-info {
  font-size: 12px;
  color: var(--text-tertiary);
  flex-shrink: 0;
}

/* Map Wrapper */
.map-wrapper {
  flex: 1;
  min-height: 0;
  position: relative;
}

/* Bottom Charts */
.charts-row {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px;
  height: 200px;
  flex-shrink: 0;
}

.chart-card {
  background: var(--bg-primary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.chart-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  border-bottom: 1px solid var(--border-color);
  flex-shrink: 0;
}

.chart-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
}

.chart-body {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;  /* 新增：整体居中 */
  padding: 12px 16px;
  gap: 24px;  /* 增大间距 */
  min-height: 0;
}

.pie-chart-container {
  flex: 0 0 auto;  /* 不伸缩 */
  display: grid;
  grid-template-columns: repeat(2, 1fr);  /* 2列布局 */
  gap: 6px 48px;  /* 行间距6px，列间距48px - 两列间距更明显 */
  min-width: 140px;  /* 保证最小宽度 */
}

.pie-legend-item {
  display: flex;
  align-items: center;
  gap: 4px;  /* 更紧凑 */
  font-size: 12px;
  padding: 2px 0;
  white-space: nowrap;  /* 防止换行 */
}

.legend-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.legend-name {
  color: var(--text-secondary);
  min-width: 32px;  /* 更紧凑 */
}

.legend-value {
  font-weight: 600;
  color: var(--text-primary);
  margin-left: 2px;  /* 更靠近名称 */
  text-align: right;
  min-width: 24px;  /* 更紧凑 */
}

.pie-chart-visual {
  width: 80px;
  height: 80px;
  flex-shrink: 0;
}

.pie-svg {
  width: 100%;
  height: 100%;
  transform: rotate(-90deg);
}

/* Responsive */
@media (max-width: 1023px) {
  .stats-row {
    grid-template-columns: repeat(2, 1fr);
  }
  
  .charts-row {
    height: 180px;
  }
}

@media (max-width: 767px) {
  .quick-start-bar {
    flex-direction: column;
    align-items: stretch;
  }

  .quick-start-left {
    flex-direction: column;
    align-items: flex-start;
  }

  .quick-start-content {
    width: 100%;
    flex-direction: column;
    align-items: flex-start;
    gap: 6px;
  }

  .quick-start-url {
    width: 100%;
    box-sizing: border-box;
  }

  .stats-row {
    gap: 12px;
  }
  
  .stat-card {
    padding: 12px;
  }
  
  .stat-value {
    font-size: 20px;
  }
  
  .filter-bar {
    flex-wrap: nowrap;
    overflow-x: auto;
    -webkit-overflow-scrolling: touch;
    scrollbar-width: none;
  }

  .country-summary {
    flex-wrap: nowrap;
  }
  
  .filter-bar::-webkit-scrollbar {
    display: none;
  }
  
  .charts-row {
    grid-template-columns: 1fr;
    height: auto;
    min-height: 160px;
  }
  
  .chart-card {
    min-height: 160px;
  }
}
</style>
