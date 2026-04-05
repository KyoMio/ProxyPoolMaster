<template>
  <div class="log-container" v-loading="loading">
    <!-- 日志筛选 -->
    <el-card shadow="hover" class="filter-card">
      <template #header>
        <div class="card-header">
          <span>日志筛选</span>
          <div class="header-actions">
            <el-switch
              v-model="autoRefresh"
              @change="toggleAutoRefresh"
              active-text="开启"
              inactive-text="关闭"
              inline-prompt
              style="--el-switch-on-color: #13ce66; --el-switch-off-color: #909399;"
            />
            <el-button :icon="Refresh" @click="fetchLogs" :loading="loading">
              刷新
            </el-button>
            <el-button type="danger" :icon="Delete" @click="confirmClearLogs">
              清空日志
            </el-button>
          </div>
        </div>
      </template>
      <el-form :inline="true" :model="filterForm" class="filter-form">
        <el-form-item label="日志级别">
          <el-select v-model="filterForm.level" placeholder="选择级别" clearable style="width: 120px">
            <el-option label="全部" value=""></el-option>
            <el-option label="DEBUG" value="DEBUG">
              <el-tag type="info" size="small">DEBUG</el-tag>
            </el-option>
            <el-option label="INFO" value="INFO">
              <el-tag type="success" size="small">INFO</el-tag>
            </el-option>
            <el-option label="WARNING" value="WARNING">
              <el-tag type="warning" size="small">WARNING</el-tag>
            </el-option>
            <el-option label="ERROR" value="ERROR">
              <el-tag type="danger" size="small">ERROR</el-tag>
            </el-option>
          </el-select>
        </el-form-item>
        <el-form-item label="组件">
          <el-select v-model="filterForm.component" placeholder="选择组件" clearable style="width: 140px">
            <el-option label="全部" value=""></el-option>
            <el-option label="API" value="API">
              <el-tag type="primary" size="small">API</el-tag>
            </el-option>
            <el-option label="COLLECTOR" value="COLLECTOR">
              <el-tag type="success" size="small">COLLECTOR</el-tag>
            </el-option>
            <el-option label="TESTER" value="TESTER">
              <el-tag type="warning" size="small">TESTER</el-tag>
            </el-option>
            <el-option label="REDIS" value="REDIS">
              <el-tag type="info" size="small">REDIS</el-tag>
            </el-option>
            <el-option label="APP" value="APP">
              <el-tag size="small">APP</el-tag>
            </el-option>
          </el-select>
        </el-form-item>
        <el-form-item label="降噪模式">
          <el-switch
            v-model="filterForm.noiseReduction"
            inline-prompt
            active-text="开"
            inactive-text="关"
            @change="applyFilter"
          />
        </el-form-item>
        <el-form-item label="关键词">
          <el-input v-model="filterForm.keyword" placeholder="搜索日志内容" clearable style="width: 200px" />
        </el-form-item>
        <el-form-item label="收集器标识">
          <el-input v-model="filterForm.collectorId" placeholder="输入收集器标识" clearable style="width: 180px" />
        </el-form-item>
        <el-form-item label="运行批次标识">
          <el-input v-model="filterForm.runId" placeholder="输入运行批次标识" clearable style="width: 180px" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="applyFilter">筛选</el-button>
          <el-button @click="resetFilter">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 日志列表 -->
    <el-card shadow="hover" class="log-list-card">
      <template #header>
        <div class="card-header">
          <span>日志列表</span>
          <div class="log-summary">
            <el-tag v-if="pendingNewLogs > 0 && currentPage !== 1" type="warning" size="small">
              有 {{ pendingNewLogs }} 条新日志
            </el-tag>
            <el-button
              v-if="pendingNewLogs > 0 && currentPage !== 1"
              size="small"
              type="primary"
              link
              @click="showLatestLogs"
            >
              查看最新
            </el-button>
            <el-tag type="info" size="small">共 {{ totalLogs }} 条</el-tag>
          </div>
        </div>
      </template>
      
      <el-table :data="logList" style="width: 100%" v-loading="loading" stripe border>
        <el-table-column prop="timestamp" label="时间" width="160" sortable />
        <el-table-column prop="level" label="级别" width="100" sortable>
          <template #default="scope">
            <el-tag :type="getLevelTagType(scope.row.level)" size="small" effect="dark">
              {{ scope.row.level }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="component" label="组件" width="110" sortable>
          <template #default="scope">
            <el-tag :type="getComponentTagType(scope.row.component)" size="small">
              {{ scope.row.component || 'APP' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="source" label="来源" width="150" show-overflow-tooltip />
        <el-table-column prop="message" label="日志内容" min-width="300" show-overflow-tooltip />
        <el-table-column label="上下文" width="100">
          <template #default="scope">
            <el-button 
              v-if="scope.row.context && Object.keys(scope.row.context).length > 0"
              size="small" 
              type="info" 
              link
              @click="showContext(scope.row)"
            >
              查看
            </el-button>
            <span v-else class="no-context">-</span>
          </template>
        </el-table-column>
      </el-table>
      
      <div class="pagination-block">
        <el-pagination
          v-model:current-page="currentPage"
          v-model:page-size="pageSize"
          @size-change="handleSizeChange"
          @current-change="handleCurrentChange"
          :page-sizes="[10, 20, 50, 100]"
          layout="total, sizes, prev, pager, next, jumper"
          :total="totalLogs"
          background
        />
      </div>
    </el-card>

    <!-- 上下文详情弹窗 -->
    <el-dialog
      v-model="contextDialogVisible"
      title="日志上下文"
      width="500px"
    >
      <pre class="context-json">{{ JSON.stringify(currentContext, null, 2) }}</pre>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue';
import { ElMessage, ElMessageBox } from 'element-plus';
import { Refresh, Delete } from '@element-plus/icons-vue';
import { useRoute, useRouter } from 'vue-router';
import { clearLogs, getLogs } from '@/api/apiClient';
import { logRealtimeClient } from '@/services/realtime';

interface LogItem {
  timestamp: string;
  timestamp_unix: number;
  level: string;
  component: string;
  source: string;
  message: string;
  context?: Record<string, any>;
}

const filterForm = ref({
  level: '',
  component: '',
  keyword: '',
  collectorId: '',
  runId: '',
  noiseReduction: true
});
const route = useRoute();
const router = useRouter();

const logList = ref<LogItem[]>([]);
const loading = ref(false);
const currentPage = ref(1);
const pageSize = ref(20);
const totalLogs = ref(0);

// 自动刷新
const autoRefresh = ref(false);
const pendingNewLogs = ref(0);
let unsubscribeSnapshot: (() => void) | null = null;
let unsubscribeAppend: (() => void) | null = null;
let unsubscribeOverflow: (() => void) | null = null;
const seenLogKeys = new Set<string>();

// 上下文弹窗
const contextDialogVisible = ref(false);
const currentContext = ref<Record<string, any>>({});

const getLevelTagType = (level: string) => {
  const types: Record<string, string> = {
    'DEBUG': 'info',
    'INFO': 'success',
    'WARNING': 'warning',
    'ERROR': 'danger',
    'CRITICAL': 'danger'
  };
  return types[level?.toUpperCase()] || 'info';
};

const getComponentTagType = (component: string) => {
  const types: Record<string, string> = {
    'API': 'primary',
    'COLLECTOR': 'success',
    'TESTER': 'warning',
    'REDIS': 'info',
    'APP': 'info'
  };
  return types[component?.toUpperCase()] || 'info';
};

const showContext = (row: LogItem) => {
  currentContext.value = row.context || {};
  contextDialogVisible.value = true;
};

function buildLogKey(item: Partial<LogItem>): string {
  return `${item.timestamp_unix || 0}|${item.level || ''}|${item.component || ''}|${item.source || ''}|${item.message || ''}`;
}

function rebuildSeenSet() {
  seenLogKeys.clear();
  logList.value.forEach((item) => {
    seenLogKeys.add(buildLogKey(item));
  });
}

function getSubscribePayload() {
  const requestFilters = buildRequestFilters();
  return {
    filters: {
      level: requestFilters.level || '',
      min_level: requestFilters.min_level || '',
      component: requestFilters.component || '',
      exclude_components: requestFilters.exclude_components || '',
      keyword: requestFilters.keyword || '',
      collector_id: requestFilters.collector_id || '',
      run_id: requestFilters.run_id || ''
    },
    pageSize: pageSize.value
  };
}

function buildRequestFilters() {
  const level = filterForm.value.level || '';
  const component = filterForm.value.component || '';
  const keyword = filterForm.value.keyword || '';
  const collectorId = filterForm.value.collectorId || '';
  const runId = filterForm.value.runId || '';
  const noiseReduction = filterForm.value.noiseReduction;

  return {
    level: level || undefined,
    min_level: noiseReduction && !level ? 'WARNING' : undefined,
    component: component || undefined,
    exclude_components: noiseReduction && !component ? 'TESTER' : undefined,
    keyword: keyword || undefined,
    collector_id: collectorId || undefined,
    run_id: runId || undefined
  };
}

function syncFilterQueryToRoute() {
  const query: Record<string, string> = {};
  if (filterForm.value.collectorId) {
    query.collector_id = filterForm.value.collectorId;
  }
  if (filterForm.value.runId) {
    query.run_id = filterForm.value.runId;
  }
  router.replace({ path: '/logs', query });
}

function hydrateFilterFromRoute() {
  const collectorId = String(route.query.collector_id || '').trim();
  const runId = String(route.query.run_id || '').trim();
  if (collectorId) {
    filterForm.value.collectorId = collectorId;
  }
  if (runId) {
    filterForm.value.runId = runId;
  }
}

function updateRealtimeSubscription() {
  if (!autoRefresh.value) {
    return;
  }
  logRealtimeClient.subscribeLogs(getSubscribePayload());
}

const fetchLogs = async (withLoading = true, resetPending = true) => {
  if (withLoading) {
    loading.value = true;
  }
  try {
    const params = {
      ...buildRequestFilters(),
      page: currentPage.value,
      size: pageSize.value,
    };

    const response = await getLogs(params);
    logList.value = (response.data || []) as LogItem[];
    totalLogs.value = response.total || 0;
    rebuildSeenSet();
    if (resetPending) {
      pendingNewLogs.value = 0;
    }
  } catch (error: any) {
    ElMessage.error('获取日志列表失败: ' + (error?.response?.data?.detail || error?.message || '未知错误'));
    console.error('Failed to fetch logs:', error);
    logList.value = [];
    totalLogs.value = 0;
  } finally {
    if (withLoading) {
      loading.value = false;
    }
  }
};

const applyFilter = () => {
  currentPage.value = 1;
  syncFilterQueryToRoute();
  fetchLogs();
  updateRealtimeSubscription();
};

const resetFilter = () => {
  filterForm.value = {
    level: '',
    component: '',
    keyword: '',
    collectorId: '',
    runId: '',
    noiseReduction: true
  };
  currentPage.value = 1;
  syncFilterQueryToRoute();
  fetchLogs();
  updateRealtimeSubscription();
};

const handleSizeChange = (val: number) => {
  pageSize.value = val;
  fetchLogs();
  updateRealtimeSubscription();
};

const handleCurrentChange = (val: number) => {
  currentPage.value = val;
  fetchLogs();
};

async function showLatestLogs() {
  currentPage.value = 1;
  await fetchLogs();
}

const confirmClearLogs = async () => {
  try {
    await ElMessageBox.confirm(
      '确定要清空所有日志吗？此操作不可恢复。',
      '警告',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning',
      }
    );
    await clearLogs();
    pendingNewLogs.value = 0;
    await fetchLogs();
    updateRealtimeSubscription();
    ElMessage.success('日志已清空');
  } catch {
    // 用户取消或请求失败时保持当前状态
  }
};

function deduplicateLogs(logs: LogItem[]): LogItem[] {
  const uniqueLogs: LogItem[] = [];
  logs.forEach((item) => {
    const key = buildLogKey(item);
    if (!seenLogKeys.has(key)) {
      seenLogKeys.add(key);
      uniqueLogs.push(item);
    }
  });
  return uniqueLogs;
}

function handleLogSnapshot(message: any) {
  if (!autoRefresh.value) {
    return;
  }
  const snapshotLogs = (message?.data?.logs || []) as LogItem[];
  const total = Number(message?.data?.total || 0);

  if (typeof total === 'number' && Number.isFinite(total)) {
    totalLogs.value = total;
  }

  if (currentPage.value !== 1) {
    return;
  }

  logList.value = snapshotLogs;
  rebuildSeenSet();
  pendingNewLogs.value = 0;
}

function handleLogAppend(message: any) {
  if (!autoRefresh.value) {
    return;
  }
  const incoming = (message?.data?.logs || []) as LogItem[];
  if (!incoming.length) {
    return;
  }

  const newLogs = deduplicateLogs(incoming);
  if (!newLogs.length) {
    return;
  }

  totalLogs.value += newLogs.length;

  if (currentPage.value !== 1) {
    pendingNewLogs.value += newLogs.length;
    return;
  }

  logList.value = [...newLogs, ...logList.value].slice(0, pageSize.value);
}

function handleLogOverflow(message: any) {
  if (!autoRefresh.value) {
    return;
  }
  const dropped = Number(message?.data?.dropped || 0);
  ElMessage.warning(`日志推送过快，已丢弃 ${dropped} 条，建议手动刷新`);
}

// 自动刷新控制
const toggleAutoRefresh = (value: boolean) => {
  if (value) {
    updateRealtimeSubscription();
    ElMessage.success('已开启自动刷新 (WebSocket)');
  } else {
    logRealtimeClient.unsubscribeLogs();
    pendingNewLogs.value = 0;
    ElMessage.info('已关闭自动刷新');
  }
};

onMounted(() => {
  hydrateFilterFromRoute();
  unsubscribeSnapshot = logRealtimeClient.subscribe('log_snapshot', handleLogSnapshot);
  unsubscribeAppend = logRealtimeClient.subscribe('log_append', handleLogAppend);
  unsubscribeOverflow = logRealtimeClient.subscribe('log_overflow', handleLogOverflow);
  fetchLogs();
});

onUnmounted(() => {
  unsubscribeSnapshot?.();
  unsubscribeAppend?.();
  unsubscribeOverflow?.();
  unsubscribeSnapshot = null;
  unsubscribeAppend = null;
  unsubscribeOverflow = null;
  logRealtimeClient.unsubscribeLogs();
});
</script>

<style scoped>
.log-container {
  padding: 20px;
}

.filter-card, .log-list-card {
  margin-bottom: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 16px;
  font-weight: bold;
  color: #303133;
}

.log-summary {
  display: flex;
  align-items: center;
  gap: 8px;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 16px;
}

.header-actions .el-switch {
  transform: scale(1.15);
}

.filter-form {
  margin-top: 10px;
}

.pagination-block {
  margin-top: 20px;
  display: flex;
  justify-content: flex-end;
}

.no-context {
  color: #c0c4cc;
}

.context-json {
  background-color: #f5f7fa;
  padding: 15px;
  border-radius: 4px;
  font-family: 'Courier New', monospace;
  font-size: 13px;
  overflow-x: auto;
  max-height: 400px;
  overflow-y: auto;
}

:deep(.el-table) {
  font-size: 13px;
}

:deep(.el-table th) {
  background-color: #f5f7fa;
  font-weight: 600;
}
</style>
