<template>
  <div class="collector-table-wrapper">
    <el-empty v-if="collectors.length === 0" description="暂无收集器" />

    <div v-else class="collector-rows">
      <div v-for="row in collectors" :key="row.id" class="collector-card" data-testid="collector-card">
        <div class="collector-card__header">
          <div class="collector-card__title-block">
            <div class="collector-card__title-row">
              <h3 class="collector-card__title">{{ row.name }}</h3>
              <el-tag :type="lifecycleTagType(row.lifecycle)" size="small">{{ lifecycleText(row.lifecycle) }}</el-tag>
            </div>
            <div class="collector-card__badges">
              <el-tag :type="row.mode === 'simple' ? 'primary' : 'warning'" size="small">
                {{ row.mode === 'simple' ? '简单模式' : '专家模式' }}
              </el-tag>
              <el-tag size="small" effect="plain">{{ row.source.toUpperCase() }}</el-tag>
              <span class="status-chip" :class="row.enabled ? 'status-chip--on' : 'status-chip--off'">
                {{ row.enabled ? '已启用' : '已停用' }}
              </span>
            </div>
          </div>

          <div class="collector-card__status">
            <div class="status-label">最近运行</div>
            <template v-if="row.lastRun">
              <el-tag :type="runTagType(row.lastRun.status)" size="small">{{ runText(row.lastRun.status) }}</el-tag>
              <span class="status-muted">{{ formatTime(row.lastRun.ended_at) }}</span>
            </template>
            <span v-else class="status-muted">暂无记录</span>
          </div>
        </div>

        <div class="collector-card__body">
          <div class="collector-meta-grid">
            <div class="collector-meta-item">
              <span class="collector-meta-label">生命周期</span>
              <span class="collector-meta-value">{{ lifecycleText(row.lifecycle) }}</span>
            </div>
            <div class="collector-meta-item">
              <span class="collector-meta-label">模式</span>
              <span class="collector-meta-value">{{ row.mode === 'simple' ? '简单' : '专家' }}</span>
            </div>
            <div class="collector-meta-item">
              <span class="collector-meta-label">来源</span>
              <span class="collector-meta-value">{{ row.source.toUpperCase() }}</span>
            </div>
            <div class="collector-meta-item">
              <span class="collector-meta-label">执行间隔</span>
              <span class="collector-meta-value">{{ formatInterval(row.interval_seconds) }}</span>
            </div>
          </div>

          <div v-if="row.lastRun" class="collector-metrics">
            <div class="collector-metrics__summary">
              <span>结束于 {{ formatTime(row.lastRun.ended_at) }}</span>
              <span>耗时 {{ row.lastRun.duration_ms }}ms</span>
              <span>结果 {{ runText(row.lastRun.status) }}</span>
            </div>
            <div class="collector-metrics__grid">
              <span class="metric-pill">raw {{ row.lastRun.metrics.raw_count }}</span>
              <span class="metric-pill">valid {{ row.lastRun.metrics.valid_count }}</span>
              <span class="metric-pill">stored {{ row.lastRun.metrics.stored_count }}</span>
              <span class="metric-pill">duplicate {{ row.lastRun.metrics.duplicate_count }}</span>
              <span class="metric-pill">冷却阻断 {{ row.lastRun.metrics.cooldown_blocked_count ?? 0 }}</span>
            </div>
          </div>
          <div v-else class="collector-empty-state">
            暂无最近运行记录，建议先测试运行
          </div>
        </div>

        <div class="collector-card__actions">
          <el-button size="small" @click="$emit('edit', row)">编辑</el-button>
          <el-button size="small" type="success" :loading="row.actionLoading" @click="$emit('test-run', row)">测试运行</el-button>
          <el-button size="small" @click="$emit('show-runs', row)">运行记录</el-button>

          <el-button
            v-if="row.lifecycle === 'draft' || row.lifecycle === 'paused'"
            size="small"
            type="primary"
            :loading="row.actionLoading"
            @click="$emit('publish', row)"
          >
            发布
          </el-button>

          <el-button
            v-if="row.lifecycle === 'published'"
            size="small"
            type="warning"
            :loading="row.actionLoading"
            @click="$emit('pause', row)"
          >
            暂停
          </el-button>

          <el-button
            v-if="row.lifecycle === 'paused'"
            size="small"
            type="primary"
            :loading="row.actionLoading"
            @click="$emit('resume', row)"
          >
            恢复
          </el-button>

          <el-button
            v-if="row.lifecycle !== 'published'"
            size="small"
            type="danger"
            :loading="row.actionLoading"
            @click="$emit('delete', row)"
          >
            删除
          </el-button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { CollectorLifecycle, CollectorRunRecord, CollectorRunStatus, CollectorV2 } from '@/types/collector'

export interface CollectorTableRow extends CollectorV2 {
  actionLoading?: boolean
  lastRun?: CollectorRunRecord | null
}

defineProps<{
  collectors: CollectorTableRow[]
}>()

defineEmits<{
  (e: 'edit', row: CollectorTableRow): void
  (e: 'test-run', row: CollectorTableRow): void
  (e: 'show-runs', row: CollectorTableRow): void
  (e: 'publish', row: CollectorTableRow): void
  (e: 'pause', row: CollectorTableRow): void
  (e: 'resume', row: CollectorTableRow): void
  (e: 'delete', row: CollectorTableRow): void
}>()

const formatInterval = (seconds: number): string => {
  if (seconds < 60) return `${seconds}秒`
  if (seconds < 3600) return `${Math.floor(seconds / 60)}分钟`
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}小时`
  return `${Math.floor(seconds / 86400)}天`
}

const formatTime = (time: string): string => {
  const d = new Date(time)
  return isNaN(d.getTime()) ? time : d.toLocaleString('zh-CN')
}

const lifecycleTagType = (lifecycle: CollectorLifecycle): 'info' | 'success' | 'warning' => {
  if (lifecycle === 'published') return 'success'
  if (lifecycle === 'paused') return 'warning'
  return 'info'
}

const lifecycleText = (lifecycle: CollectorLifecycle): string => {
  if (lifecycle === 'published') return '已发布'
  if (lifecycle === 'paused') return '已暂停'
  return '草稿'
}

const runTagType = (status: CollectorRunStatus): 'success' | 'warning' | 'danger' => {
  if (status === 'success') return 'success'
  if (status === 'partial_success') return 'warning'
  return 'danger'
}

const runText = (status: CollectorRunStatus): string => {
  if (status === 'success') return '成功'
  if (status === 'partial_success') return '部分成功'
  if (status === 'timeout') return '超时'
  return '失败'
}
</script>

<style scoped>
.collector-rows {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.collector-card {
  border: 1px solid var(--el-border-color-light);
  border-radius: 16px;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 16px;
  background: var(--el-bg-color);
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.04);
}

.collector-card__header {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
  flex-wrap: wrap;
}

.collector-card__title-block {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.collector-card__title-row {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.collector-card__title {
  margin: 0;
  font-weight: 600;
  font-size: 18px;
}

.collector-card__badges {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.status-chip {
  padding: 4px 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 600;
  background: var(--el-fill-color-light);
  color: var(--el-text-color-secondary);
}

.status-chip--on {
  background: rgba(103, 194, 58, 0.14);
  color: var(--el-color-success);
}

.status-chip--off {
  background: rgba(245, 108, 108, 0.14);
  color: var(--el-color-danger);
}

.collector-card__status {
  display: flex;
  flex-direction: column;
  gap: 8px;
  align-items: flex-start;
  min-width: 160px;
}

.status-label {
  color: var(--el-text-color-secondary);
  font-size: 12px;
  font-weight: 600;
}

.status-muted {
  color: var(--el-text-color-secondary);
  font-size: 13px;
}

.collector-card__body {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.collector-meta-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.collector-meta-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 10px 12px;
  border-radius: 12px;
  background: var(--el-fill-color-lighter);
}

.collector-meta-label {
  color: var(--el-text-color-secondary);
  font-size: 12px;
}

.collector-meta-value {
  color: var(--el-text-color-primary);
  font-size: 14px;
  font-weight: 600;
}

.collector-metrics {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.collector-metrics__summary {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  color: var(--el-text-color-secondary);
  font-size: 13px;
}

.collector-metrics__grid {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.metric-pill {
  padding: 4px 10px;
  border-radius: 999px;
  background: var(--bg-secondary, #f5f7fa);
  color: var(--text-secondary, var(--el-text-color-secondary));
  font-weight: 500;
  font-size: 13px;
}

.collector-empty-state {
  color: var(--el-text-color-secondary);
  font-size: 13px;
}

.collector-card__actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

@media (max-width: 1024px) {
  .collector-meta-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 640px) {
  .collector-card {
    padding: 14px;
    border-radius: 14px;
  }

  .collector-card__header {
    gap: 12px;
  }

  .collector-card__title {
    font-size: 16px;
  }

  .collector-meta-grid {
    grid-template-columns: 1fr;
  }

  .collector-card__actions {
    width: 100%;
  }

  .collector-card__actions :deep(.el-button) {
    flex: 1 1 calc(50% - 4px);
  }
}
</style>
