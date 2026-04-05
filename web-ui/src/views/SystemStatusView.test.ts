import { shallowMount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'

import SystemStatusView from './SystemStatusView.vue'

vi.mock('@/api/apiClient', () => ({
  getSystemStatus: vi.fn(async () => ({
    redis_status: 'Connected',
    api_service_status: 'Running',
    api_uptime_seconds: 120,
    collector_service_status: 'Running',
    collector_runtime_mode: 'v2',
    collector_version: 'v2',
    tester_service_status: 'Running',
    overall_status: 'ok',
  })),
  getModuleStatus: vi.fn(async () => ([
    {
      moduleName: 'Collector',
      status: 'Running',
      lastHeartbeat: '2026-03-17T22:00:00',
      uptime: '1h',
      details: { version: 'v2' },
      performance: { active_jobs: 1, queue_backlog: 0 },
    },
  ])),
  getSystemMetrics: vi.fn(async () => ({
    api_performance: {
      avg_response_time_ms: 1,
      qps: 1,
      error_rate: 0,
      concurrent_connections: 1,
    },
    proxy_pool_metrics: {
      collect_rate_per_min: 1,
      test_rate_per_min: 1,
      success_rate: 1,
      cleanup_rate_per_min: 1,
    },
  })),
}))

vi.mock('@/services/realtime', () => ({
  dashboardRealtimeClient: {
    subscribe: vi.fn(() => () => {}),
    connect: vi.fn(),
  },
}))

vi.mock('element-plus', () => ({
  ElMessage: {
    error: vi.fn(),
  },
}))

const flushPromises = async () => {
  await new Promise((resolve) => setTimeout(resolve, 0))
}

describe('SystemStatusView', () => {
  it('应展示统一后的 Collector 模块状态', async () => {
    const wrapper = shallowMount(SystemStatusView, {
      global: {
        directives: {
          loading: () => {},
        },
        stubs: {
          MetricCard: true,
          'el-row': { template: '<div><slot /></div>' },
          'el-col': { template: '<div><slot /></div>' },
          'el-card': { template: '<div><slot name="header" /><slot /></div>' },
          'el-icon': { template: '<i><slot /></i>' },
          'el-switch': true,
          'el-button': { template: '<button><slot /></button>' },
          'el-tag': { props: ['type'], template: '<span :data-type="type"><slot /></span>' },
          'el-table': { template: '<div><slot /></div>' },
          'el-table-column': { template: '<div><slot :row="{ status: \'Unset\' }" /></div>' },
        },
      },
    })

    await flushPromises()
    await flushPromises()

    const vm = wrapper.vm as unknown as { moduleStatusList: any[] }
    expect(wrapper.text()).toContain('Collector 状态')
    expect(wrapper.text()).toContain('v2')
    expect(vm.moduleStatusList).toHaveLength(1)
    expect(vm.moduleStatusList[0].moduleName).toBe('Collector')
  })

  it('代理可用率高时不应因为阈值方向错误被标成异常', async () => {
    const wrapper = shallowMount(SystemStatusView, {
      global: {
        directives: {
          loading: () => {},
        },
        stubs: {
          MetricCard: true,
          'el-row': { template: '<div><slot /></div>' },
          'el-col': { template: '<div><slot /></div>' },
          'el-card': { template: '<div><slot name="header" /><slot /></div>' },
          'el-icon': { template: '<i><slot /></i>' },
          'el-switch': true,
          'el-button': { template: '<button><slot /></button>' },
          'el-tag': { props: ['type'], template: '<span :data-type="type"><slot /></span>' },
          'el-table': { template: '<div><slot /></div>' },
          'el-table-column': { template: '<div><slot :row="{ status: \'Unset\' }" /></div>' },
        },
      },
    })

    await flushPromises()
    await flushPromises()

    const vm = wrapper.vm as unknown as { proxyMetrics: Array<{ key: string; status: string; thresholds: { warning: number; error: number } }> }
    const successRateMetric = vm.proxyMetrics.find((item) => item.key === 'success_rate')

    expect(successRateMetric?.status).toBe('normal')
    expect(successRateMetric?.thresholds).toEqual({ warning: 0, error: 0 })
  })
})
