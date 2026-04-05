<template>
  <el-drawer
    :model-value="visible"
    size="55%"
    direction="rtl"
    :with-header="true"
    @update:model-value="$emit('update:visible', $event)"
  >
    <template #header>
      <div>运行记录 - {{ collectorName || '-' }}</div>
    </template>

    <el-skeleton v-if="loading" :rows="5" animated />
    <el-empty v-else-if="runs.length === 0" description="暂无运行记录" />

    <div v-else class="run-rows">
      <div v-for="run in runs" :key="run.run_id" class="run-row">
        <div class="run-main">
          <div class="run-id">{{ run.run_id }}</div>
          <div class="run-meta">
            <el-tag :type="runTagType(run.status)">{{ runText(run.status) }}</el-tag>
            <span>{{ run.trigger }}</span>
            <span>{{ formatTime(run.ended_at) }}</span>
            <span>{{ run.duration_ms }}ms</span>
          </div>
        </div>

        <el-button
          size="small"
          type="primary"
          link
          @click="$emit('view-log', run.collector_id, run.run_id)"
        >
          查看日志
        </el-button>
      </div>
    </div>
  </el-drawer>
</template>

<script setup lang="ts">
import type { CollectorRunRecord, CollectorRunStatus } from '@/types/collector'

defineProps<{
  visible: boolean
  loading: boolean
  collectorName: string
  runs: CollectorRunRecord[]
}>()

defineEmits<{
  (e: 'update:visible', value: boolean): void
  (e: 'view-log', collectorId: string, runId: string): void
}>()

const formatTime = (time: string): string => {
  const d = new Date(time)
  return isNaN(d.getTime()) ? time : d.toLocaleString('zh-CN')
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
.run-rows {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.run-row {
  border: 1px solid var(--el-border-color-light);
  border-radius: 8px;
  padding: 10px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.run-id {
  font-weight: 600;
}

.run-meta {
  margin-top: 4px;
  display: flex;
  gap: 8px;
  align-items: center;
  color: var(--el-text-color-secondary);
  font-size: 13px;
}
</style>
