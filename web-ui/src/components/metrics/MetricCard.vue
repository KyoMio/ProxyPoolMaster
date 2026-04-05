<template>
  <el-card shadow="hover" class="metric-card" :class="{ 'is-expanded': isExpanded }">
    <div class="metric-header" @click="toggleExpand">
      <div class="metric-info">
        <div class="metric-title">{{ title }}</div>
        <div class="metric-value" :style="valueStyle">
          {{ formatValue }}
          <span class="metric-unit" v-if="unit">{{ unit }}</span>
        </div>
      </div>
      <div class="metric-actions">
        <el-tag :type="statusType" size="small" effect="plain">{{ statusText }}</el-tag>
        <el-icon class="expand-icon" :class="{ 'is-expanded': isExpanded }">
          <ArrowDown />
        </el-icon>
      </div>
    </div>
    
    <!-- 展开的详情区域 -->
    <el-collapse-transition @after-enter="handleAfterEnter">
      <div v-show="isExpanded" class="metric-detail">
        <el-divider />
        <div class="detail-header">
          <span class="detail-title">{{ detailTitle }}</span>
          <el-radio-group v-model="timeRange" size="small" @change="onTimeRangeChange">
            <el-radio-button value="1h">1小时</el-radio-button>
            <el-radio-button value="6h">6小时</el-radio-button>
            <el-radio-button value="24h">24小时</el-radio-button>
          </el-radio-group>
        </div>
        <div :id="chartId" class="metric-chart"></div>
      </div>
    </el-collapse-transition>
  </el-card>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue';
import { ArrowDown } from '@element-plus/icons-vue';
import * as echarts from 'echarts';
import { getMetricsHistory } from '@/api/apiClient';

interface Props {
  title: string;
  value: number;
  unit?: string;
  metricKey: string;  // 用于API请求历史数据
  status?: 'normal' | 'warning' | 'error';
  thresholds?: {
    warning: number;
    error: number;
  };
  detailTitle?: string;
}

const props = withDefaults(defineProps<Props>(), {
  unit: '',
  status: 'normal',
  thresholds: () => ({ warning: 0, error: 0 }),
  detailTitle: '历史趋势'
});

const isExpanded = ref(false);
const timeRange = ref('1h');
const chartId = computed(() => `chart-${props.metricKey}`);
let chart: echarts.ECharts | null = null;

// 格式化数值显示
const formatValue = computed(() => {
  if (props.value === null || props.value === undefined) return '-';
  if (typeof props.value === 'number') {
    // 只有错误率指标才显示为百分比
    if (props.metricKey === 'error_rate' || props.metricKey === 'success_rate') {
      return props.value.toFixed(1) + '%';
    }
    // 其他指标直接显示数值
    if (props.value < 0.01) {
      return props.value.toFixed(3);
    } else if (props.value < 1) {
      return props.value.toFixed(2);
    }
    return props.value.toLocaleString();
  }
  return props.value;
});

// 根据数值和阈值计算状态
const computedStatus = computed(() => {
  if (props.status !== 'normal') return props.status;
  if (props.thresholds.error && props.value >= props.thresholds.error) return 'error';
  if (props.thresholds.warning && props.value >= props.thresholds.warning) return 'warning';
  return 'normal';
});

const statusType = computed(() => {
  switch (computedStatus.value) {
    case 'error': return 'danger';
    case 'warning': return 'warning';
    default: return 'success';
  }
});

const statusText = computed(() => {
  switch (computedStatus.value) {
    case 'error': return '异常';
    case 'warning': return '警告';
    default: return '正常';
  }
});

const valueStyle = computed(() => {
  const colors = {
    normal: '#303133',
    warning: '#e6a23c',
    error: '#f56c6c'
  };
  return { color: colors[computedStatus.value] };
});

// 展开/收起
const toggleExpand = () => {
  isExpanded.value = !isExpanded.value;
  if (isExpanded.value) {
    nextTick(() => {
      initChart();
      loadChartData();
    });
  }
};

// 初始化图表
const initChart = () => {
  if (chart) {
    chart.dispose();
  }
  const chartDom = document.getElementById(chartId.value);
  if (!chartDom) return;
  chart = echarts.init(chartDom);
  
  const option = {
    grid: {
      left: '15%',
      right: '4%',
      bottom: '10%',
      top: '15%',
      containLabel: false
    },
    tooltip: {
      trigger: 'axis',
      formatter: '{b}<br/>{a}: {c} ' + props.unit
    },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: [],
      axisLabel: {
        fontSize: 11
      }
    },
    yAxis: {
      type: 'value',
      name: props.unit,
      nameTextStyle: {
        padding: [0, 0, 0, 10],
        fontSize: 11
      },
      axisLabel: {
        fontSize: 11,
        formatter: function(value: number) {
          if (value >= 1000) {
            return (value / 1000).toFixed(1) + 'k';
          }
          return value;
        }
      }
    },
    series: [{
      name: props.title,
      type: 'line',
      smooth: true,
      symbol: 'none',
      areaStyle: {
        opacity: 0.3,
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: '#409eff' },
          { offset: 1, color: 'rgba(64,158,255,0.1)' }
        ])
      },
      lineStyle: {
        color: '#409eff',
        width: 2
      },
      data: []
    }]
  };
  
  chart.setOption(option);
};

// 加载图表数据
const loadChartData = async () => {
  if (!chart) return;
  
  try {
    const data = await getMetricsHistory(props.metricKey, timeRange.value);
    
    chart.setOption({
      xAxis: {
        data: data.time_labels
      },
      series: [{
        data: data.values
      }]
    });
  } catch (error) {
    console.error('Failed to load chart data:', error);
  }
};

// 时间范围变化
const onTimeRangeChange = () => {
  loadChartData();
};

// 折叠动画结束后重绘，避免过渡阶段初始化导致图表尺寸异常
const handleAfterEnter = () => {
  chart?.resize();
};

// 监听展开状态
watch(isExpanded, (expanded) => {
  if (expanded) {
    nextTick(() => {
      chart?.resize();
    });
  }
});

// 窗口大小变化时重绘
const handleResize = () => {
  chart?.resize();
};

onMounted(() => {
  window.addEventListener('resize', handleResize);
});

onUnmounted(() => {
  window.removeEventListener('resize', handleResize);
  chart?.dispose();
});
</script>

<style scoped>
.metric-card {
  margin-bottom: 10px;
  transition: all 0.3s ease;
}

.metric-card.is-expanded {
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.15);
}

.metric-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  cursor: pointer;
  padding: 5px 0;
}

.metric-info {
  flex: 1;
}

.metric-title {
  font-size: 14px;
  color: #909399;
  margin-bottom: 8px;
}

.metric-value {
  font-size: 28px;
  font-weight: bold;
  transition: color 0.3s;
}

.metric-unit {
  font-size: 14px;
  font-weight: normal;
  margin-left: 4px;
  color: #909399;
}

.metric-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.expand-icon {
  font-size: 16px;
  color: #909399;
  transition: transform 0.3s;
}

.expand-icon.is-expanded {
  transform: rotate(180deg);
}

.metric-detail {
  margin-top: 10px;
}

.detail-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 15px;
}

.detail-title {
  font-size: 14px;
  color: #606266;
  font-weight: 500;
}

.metric-chart {
  width: 100%;
  height: 200px;
}
</style>
