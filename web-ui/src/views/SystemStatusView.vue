<template>
  <div class="system-status-container" v-loading="loading">
    <!-- 页面标题和操作栏 -->
    <div class="page-header">
      <h2>系统状态</h2>
      <div class="header-actions">
        <el-switch
          v-model="autoRefresh"
          active-text="开启"
          inactive-text="关闭"
          inline-prompt
          style="--el-switch-on-color: #13ce66; --el-switch-off-color: #909399;"
        />
        <el-button 
          :icon="Refresh" 
          @click="fetchAllData"
          :loading="loading"
        >
          刷新
        </el-button>
      </div>
    </div>

    <!-- API性能指标区 -->
    <el-row :gutter="20" class="metrics-section">
      <el-col :span="24">
        <h3 class="section-title">
          <el-icon><Timer /></el-icon>
          API 性能指标
        </h3>
      </el-col>
      <el-col :xs="24" :sm="12" :md="6" v-for="metric in apiMetrics" :key="metric.key">
        <MetricCard
          :title="metric.title"
          :value="metric.value"
          :unit="metric.unit"
          :metricKey="metric.key"
          :status="metric.status"
          :thresholds="metric.thresholds"
          :detailTitle="metric.detailTitle"
        />
      </el-col>
    </el-row>

    <!-- 代理池业务指标区 -->
    <el-row :gutter="20" class="metrics-section">
      <el-col :span="24">
        <h3 class="section-title">
          <el-icon><DataAnalysis /></el-icon>
          代理池业务指标
        </h3>
      </el-col>
      <el-col :xs="24" :sm="12" :md="6" v-for="metric in proxyMetrics" :key="metric.key">
        <MetricCard
          :title="metric.title"
          :value="metric.value"
          :unit="metric.unit"
          :metricKey="metric.key"
          :status="metric.status"
          :thresholds="metric.thresholds"
          :detailTitle="metric.detailTitle"
        />
      </el-col>
    </el-row>

    <!-- 系统服务状态卡片（保留原有设计） -->
    <el-row :gutter="20" class="status-overview">
      <el-col :span="24">
        <h3 class="section-title">
          <el-icon><Monitor /></el-icon>
          服务状态
        </h3>
      </el-col>
      <el-col :xs="24" :sm="12" :md="8">
        <el-card shadow="hover">
          <template #header>
            <div class="card-header">
              <span>Redis 连接状态</span>
            </div>
          </template>
          <div class="status-item">
            <el-icon :size="28" :color="systemStatus.redis_status === 'Connected' ? '#67c23a' : '#f56c6c'">
              <CircleCheck v-if="systemStatus.redis_status === 'Connected'" />
              <CircleClose v-else />
            </el-icon>
            <span class="status-text" :class="{ 'status-ok': systemStatus.redis_status === 'Connected' }">
              {{ systemStatus.redis_status }}
            </span>
          </div>
        </el-card>
      </el-col>
      <el-col :xs="24" :sm="12" :md="8">
        <el-card shadow="hover">
          <template #header>
            <div class="card-header">
              <span>API 服务状态</span>
            </div>
          </template>
          <div class="status-item">
            <el-icon :size="28" color="#67c23a">
              <CircleCheck />
            </el-icon>
            <span class="status-text status-ok">{{ systemStatus.api_service_status }}</span>
            <span class="uptime-text" v-if="systemStatus.api_uptime_seconds">
              ({{ formatUptime(systemStatus.api_uptime_seconds) }})
            </span>
          </div>
        </el-card>
      </el-col>
      <el-col :xs="24" :sm="12" :md="8">
        <el-card shadow="hover">
          <template #header>
            <div class="card-header">
              <span>Collector 状态</span>
            </div>
          </template>
          <div class="status-item">
            <el-icon :size="28" :color="getServiceStatusColor(systemStatus.collector_service_status)">
              <CircleCheck v-if="systemStatus.collector_service_status === 'Running'" />
              <CircleClose v-else />
            </el-icon>
            <span class="status-text" :class="{ 'status-ok': systemStatus.collector_service_status === 'Running' }">
              {{ formatCollectorRuntimeStatus(systemStatus.collector_service_status, systemStatus.collector_version) }}
            </span>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 模块状态表格 -->
    <el-row :gutter="20" class="module-status">
      <el-col :span="24">
        <el-card shadow="hover">
          <template #header>
            <div class="card-header">
              <span>各模块运行状态</span>
            </div>
          </template>
          <el-table 
            :data="moduleStatusList" 
            style="width: 100%"
          >
            <el-table-column prop="moduleName" label="模块名称" min-width="200" />
            <el-table-column prop="version" label="版本" width="120" />
            <el-table-column prop="status" label="状态" width="120">
              <template #default="scope">
                <el-tag :type="getStatusTagType(scope.row.status)">{{ scope.row.status }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="lastHeartbeat" label="最后心跳时间" min-width="180" />
            <el-table-column prop="uptime" label="运行时长" min-width="120" />
          </el-table>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed, watch } from 'vue';
import { ElMessage } from 'element-plus';
import { 
  Refresh, 
  Timer, 
  DataAnalysis, 
  Monitor,
  CircleCheck,
  CircleClose
} from '@element-plus/icons-vue';
import { 
  getSystemStatus, 
  getModuleStatus, 
  getSystemMetrics
} from '@/api/apiClient';
import MetricCard from '@/components/metrics/MetricCard.vue';
import { dashboardRealtimeClient } from '@/services/realtime';

// 指标项类型
interface MetricItem {
  title: string;
  value: number;
  unit: string;
  key: string;
  status: 'normal' | 'warning' | 'error';
  thresholds: { warning: number; error: number };
  detailTitle: string;
}

// 加载状态
const loading = ref(false);

// 自动刷新
const autoRefresh = ref(true);
let unsubscribeSystemUpdate: (() => void) | null = null;

// 系统状态
const systemStatus = ref({
  redis_status: 'Loading...',
  api_service_status: 'Loading...',
  collector_service_status: 'Loading...',
  collector_runtime_mode: '',
  collector_version: '',
  tester_service_status: 'Loading...',
  api_uptime_seconds: 0,
});

// 性能指标
const performanceMetrics = ref({
  api_performance: {
    avg_response_time_ms: 0,
    qps: 0,
    error_rate: 0,
    concurrent_connections: 0
  },
  proxy_pool_metrics: {
    collect_rate_per_min: 0,
    test_rate_per_min: 0,
    success_rate: 0,
    cleanup_rate_per_min: 0
  }
});

// 模块状态
const moduleStatusList = ref([]);

// API性能指标配置
const apiMetrics = computed<MetricItem[]>(() => [
  {
    title: '平均响应时间',
    value: performanceMetrics.value.api_performance?.avg_response_time_ms || 0,
    unit: 'ms',
    key: 'api_response_time',
    status: (performanceMetrics.value.api_performance?.avg_response_time_ms > 500 ? 'warning' : 'normal') as 'normal' | 'warning' | 'error',
    thresholds: { warning: 500, error: 1000 },
    detailTitle: '响应时间趋势'
  },
  {
    title: 'QPS',
    value: performanceMetrics.value.api_performance?.qps || 0,
    unit: 'req/s',
    key: 'qps',
    status: 'normal',
    thresholds: { warning: 1000, error: 2000 },
    detailTitle: '吞吐量趋势'
  },
  {
    title: '错误率',
    value: (performanceMetrics.value.api_performance?.error_rate || 0) * 100,
    unit: '%',
    key: 'error_rate',
    status: ((performanceMetrics.value.api_performance?.error_rate || 0) > 0.05 ? 'warning' : 'normal') as 'normal' | 'warning' | 'error',
    thresholds: { warning: 5, error: 20 },
    detailTitle: '错误率趋势'
  },
  {
    title: '并发连接',
    value: performanceMetrics.value.api_performance?.concurrent_connections || 0,
    unit: '个',
    key: 'concurrent_connections',
    status: 'normal',
    thresholds: { warning: 100, error: 200 },
    detailTitle: '连接数趋势'
  }
]);

// 代理池业务指标配置
const proxyMetrics = computed<MetricItem[]>(() => [
  {
    title: '采集速率',
    value: performanceMetrics.value.proxy_pool_metrics?.collect_rate_per_min || 0,
    unit: '个/分钟',
    key: 'collect_rate',
    status: 'normal',
    thresholds: { warning: 0, error: 0 },
    detailTitle: '采集趋势'
  },
  {
    title: '检测速率',
    value: performanceMetrics.value.proxy_pool_metrics?.test_rate_per_min || 0,
    unit: '个/分钟',
    key: 'test_rate',
    status: 'normal',
    thresholds: { warning: 0, error: 0 },
    detailTitle: '检测趋势'
  },
  {
    title: '代理可用率',
    value: (performanceMetrics.value.proxy_pool_metrics?.success_rate || 0) * 100,
    unit: '%',
    key: 'success_rate',
    status: (
      (performanceMetrics.value.proxy_pool_metrics?.success_rate || 0) < 0.3
        ? 'error'
        : (performanceMetrics.value.proxy_pool_metrics?.success_rate || 0) < 0.5
          ? 'warning'
          : 'normal'
    ) as 'normal' | 'warning' | 'error',
    thresholds: { warning: 0, error: 0 },
    detailTitle: '可用率趋势'
  },
  {
    title: '清理速率',
    value: performanceMetrics.value.proxy_pool_metrics?.cleanup_rate_per_min || 0,
    unit: '个/分钟',
    key: 'cleanup_rate',
    status: 'normal',
    thresholds: { warning: 0, error: 0 },
    detailTitle: '清理趋势'
  }
]);

// 获取状态标签类型
const getStatusTagType = (status: string) => {
  switch (status) {
    case 'Running':
    case 'Connected':
      return 'success';
    case 'Stopped':
    case 'Disconnected':
      return 'danger';
    case 'Degraded':
      return 'warning';
    case 'Unset':
    case 'Idle':
      return 'info';
    default:
      return 'info';
  }
};

const getServiceStatusColor = (status: string) => {
  if (status === 'Running') return '#67c23a'
  if (status === 'Degraded') return '#e6a23c'
  if (status === 'Unset') return '#909399'
  return '#f56c6c'
}

const formatCollectorRuntimeStatus = (status: string, version: string) => {
  if (!version) return status || 'N/A'
  const normalized = status || 'Unset'
  if (normalized === 'Running') return `运行中（${version}）`
  if (normalized === 'Degraded') return `降级（${version}）`
  if (normalized === 'Unset') return `未设置（${version}）`
  return `已停止（${version}）`
}

// 格式化运行时长
const formatUptime = (seconds: number) => {
  if (!seconds || seconds < 0) return 'N/A';
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const secs = seconds % 60;
  let result = '';
  if (hours > 0) result += `${hours}小时`;
  if (minutes > 0) result += `${minutes}分钟`;
  if (secs > 0 && result === '') result += `${secs}秒`;
  return result;
};

// 格式化时间
const formatTime = (isoString: string) => {
  if (!isoString) return 'N/A';
  try {
    return new Date(isoString).toLocaleString();
  } catch {
    return isoString;
  }
};



function applySystemRealtimePayload(payload: any) {
  if (!payload) return;

  if (payload.status) {
    systemStatus.value = payload.status;
  }

  if (payload.metrics) {
    performanceMetrics.value = payload.metrics;
  }

  if (Array.isArray(payload.modules)) {
    moduleStatusList.value = payload.modules.map((module: any) => ({
      moduleName: module.moduleName || module.module_name,
      version: module.details?.version || '',
      status: module.status,
      lastHeartbeat: formatTime(module.lastHeartbeat || module.last_heartbeat),
      uptime: module.uptime,
      performance: module.performance || {},
      details: module.details || {}
    }));
  }
}

// 获取所有数据（手动刷新）
const fetchAllData = async () => {
  loading.value = true;
  try {
    // 并行获取所有数据
    const [statusRes, modulesRes, metricsRes] = await Promise.all([
      getSystemStatus(),
      getModuleStatus(),
      getSystemMetrics()
    ]);

    // 更新系统状态
    systemStatus.value = statusRes;

    // 更新性能指标
    performanceMetrics.value = metricsRes;

    // 更新模块状态 - 确保字段名正确映射
    moduleStatusList.value = modulesRes.map((module: any) => ({
      moduleName: module.moduleName || module.module_name,
      version: module.details?.version || '',
      status: module.status,
      lastHeartbeat: formatTime(module.lastHeartbeat || module.last_heartbeat),
      uptime: module.uptime,
      performance: module.performance || {},
      details: module.details || {}
    }));

  } catch (error: any) {
    ElMessage.error('获取系统状态失败: ' + (error.response?.data?.detail || error.message));
    console.error('Failed to fetch system status:', error);
  } finally {
    loading.value = false;
  }
};

function handleSystemUpdate(message: any) {
  if (!autoRefresh.value) {
    return;
  }
  applySystemRealtimePayload(message?.data);
}

// 监听自动刷新开关
watch(autoRefresh, (enabled) => {
  if (enabled) {
    dashboardRealtimeClient.connect();
  }
});

onMounted(() => {
  fetchAllData();
  unsubscribeSystemUpdate = dashboardRealtimeClient.subscribe('system_update', handleSystemUpdate);
  dashboardRealtimeClient.connect();
});

onUnmounted(() => {
  unsubscribeSystemUpdate?.();
  unsubscribeSystemUpdate = null;
});
</script>

<style scoped>
.system-status-container {
  padding: 20px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.page-header h2 {
  margin: 0;
  font-size: 24px;
  color: #303133;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 16px;
}

.header-actions .el-switch {
  transform: scale(1.15);
}

.section-title {
  font-size: 16px;
  font-weight: 600;
  color: #303133;
  margin: 20px 0 15px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.section-title .el-icon {
  color: #409eff;
}

.metrics-section {
  margin-bottom: 10px;
}

.status-overview {
  margin-bottom: 20px;
}

.card-header {
  font-size: 16px;
  font-weight: bold;
  color: #303133;
}

.status-item {
  display: flex;
  align-items: center;
  font-size: 20px;
  padding: 10px 0;
}

.status-item .el-icon {
  margin-right: 10px;
}

.status-text {
  font-weight: bold;
  color: #f56c6c;
}

.status-text.status-ok {
  color: #67c23a;
}

.uptime-text {
  font-size: 14px;
  color: #909399;
  margin-left: 10px;
}

.module-status {
  margin-top: 20px;
}

</style>
