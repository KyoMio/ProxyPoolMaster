<template>
  <section class="collector-toolbar">
    <div class="toolbar-head">
      <div class="toolbar-title-block">
        <div class="toolbar-eyebrow">运维视图</div>
        <div class="toolbar-title-row">
          <h1>收集器管理</h1>
          <el-tag v-if="workerSummary" :type="workerStatusTag(workerSummary.status)" size="small">
            Collector Worker：{{ workerStatusText(workerSummary.status) }}
          </el-tag>
        </div>
        <p>V2 流程：测试运行 -> 发布 -> 暂停/恢复</p>
      </div>
      <el-button type="primary" @click="$emit('create')">新建收集器</el-button>
    </div>

    <div class="toolbar-band">
      <div v-if="workerSummary" class="band-group">
        <span class="band-label">Worker</span>
        <span class="metric-pill" :class="{ muted: isWorkerInactive(workerSummary.status) }">执行中 {{ workerSummary.activeJobs }}</span>
        <span class="metric-pill" :class="{ muted: isWorkerInactive(workerSummary.status) }">待执行 {{ workerSummary.queueBacklog }}</span>
        <span class="heartbeat-text">最近心跳 {{ formatHeartbeat(workerSummary.lastHeartbeat) }}</span>
        <span v-if="isWorkerInactive(workerSummary.status)" class="summary-note">当前状态下指标仅供参考</span>
      </div>

      <div v-if="overviewSummary" class="band-group band-group--overview">
        <span class="band-label">概览</span>
        <span class="metric-pill">总数 {{ overviewSummary.total }}</span>
        <span class="metric-pill">已发布 {{ overviewSummary.published }}</span>
        <span class="metric-pill">已暂停 {{ overviewSummary.paused }}</span>
        <span class="metric-pill">草稿 {{ overviewSummary.draft }}</span>
        <span class="metric-pill">最近入库 {{ overviewSummary.recentStoredCount }}</span>
        <span class="metric-pill">成功率 {{ formatSuccessRate(overviewSummary.successRate) }}</span>
        <span class="metric-pill">冷却池 {{ overviewSummary.cooldownPoolCount }}</span>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import type { CollectorOverviewSummary, CollectorWorkerSummary } from '@/types/collector'

defineProps<{
  workerSummary?: CollectorWorkerSummary | null
  overviewSummary?: CollectorOverviewSummary | null
}>()

defineEmits<{
  (e: 'create'): void
}>()

const workerStatusText = (status: CollectorWorkerSummary['status']): string => {
  if (status === 'running') return '运行中'
  if (status === 'degraded') return '降级'
  if (status === 'unset') return '未设置'
  return '离线'
}

const workerStatusTag = (status: CollectorWorkerSummary['status']): 'success' | 'warning' | 'danger' | 'info' => {
  if (status === 'running') return 'success'
  if (status === 'degraded') return 'warning'
  if (status === 'unset') return 'info'
  return 'danger'
}

const isWorkerInactive = (status: CollectorWorkerSummary['status']): boolean => (
  status === 'stopped' || status === 'unset'
)

const formatHeartbeat = (time: string): string => {
  if (!time) return 'N/A'
  const parsed = new Date(time)
  return isNaN(parsed.getTime()) ? time : parsed.toLocaleString('zh-CN')
}

const formatSuccessRate = (rate: number): string => {
  if (!Number.isFinite(rate)) return '0%'
  return `${Math.round(rate * 100)}%`
}
</script>

<style scoped>
.collector-toolbar {
  margin-bottom: 20px;
  padding: 20px;
  border: 1px solid var(--el-border-color-light);
  border-radius: 16px;
  background: linear-gradient(180deg, var(--el-bg-color) 0%, var(--el-fill-color-lighter) 100%);
  box-shadow: 0 12px 30px rgba(15, 23, 42, 0.05);
}

.toolbar-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
  flex-wrap: wrap;
}

.toolbar-title-block {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.toolbar-eyebrow {
  color: var(--el-color-primary);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.toolbar-title-row {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.collector-toolbar h1 {
  margin: 0 0 8px;
  font-size: 24px;
}

.collector-toolbar p {
  margin: 0;
  color: var(--el-text-color-secondary);
}

.toolbar-band {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid var(--el-border-color-lighter);
}

.band-group {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  font-size: 13px;
  color: var(--el-text-color-secondary);
}

.band-group--overview {
  gap: 8px;
}

.band-label {
  color: var(--el-text-color-primary);
  font-weight: 600;
}

.metric-pill {
  padding: 4px 10px;
  border-radius: 999px;
  background: var(--bg-secondary, #f5f7fa);
  color: var(--text-secondary, var(--el-text-color-secondary));
  font-weight: 500;
}

.metric-pill.muted {
  opacity: 0.65;
}

.heartbeat-text {
  color: var(--el-text-color-secondary);
}

.summary-note {
  color: var(--text-tertiary, #909399);
  font-size: 12px;
}

@media (max-width: 768px) {
  .collector-toolbar {
    padding: 16px;
    border-radius: 14px;
  }

  .collector-toolbar h1 {
    font-size: 20px;
  }

  .toolbar-head {
    align-items: stretch;
  }

  .toolbar-head :deep(.el-button) {
    width: 100%;
  }
}
</style>
