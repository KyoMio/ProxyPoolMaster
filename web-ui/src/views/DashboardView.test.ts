import { shallowMount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'

import DashboardView from './DashboardView.vue'
import { getDashboardOverview } from '@/api/apiClient'

vi.mock('@/api/apiClient', () => ({
  getDashboardOverview: vi.fn(async () => ({
    total_proxies: 10,
    available_proxies: 6,
    avg_response_time: 120,
    last_updated: '2026-03-28 10:00:00',
    available_grade_distribution: {
      S: 1,
      A: 2,
      B: 3,
    },
    available_proxy_type_distribution: [],
    available_country_distribution: [],
  })),
}))

vi.mock('@/stores/theme', () => ({
  useThemeStore: () => ({
    isDark: { value: false },
  }),
}))

vi.mock('@/services/realtime', () => ({
  dashboardRealtimeClient: {
    subscribe: vi.fn(() => () => {}),
    connect: vi.fn(),
  },
}))

vi.mock('@/components/charts/WorldMap.vue', () => ({
  default: {
    template: '<div data-testid="world-map" />',
  },
}))

vi.mock('element-plus', () => ({
  ElMessage: {
    error: vi.fn(),
    success: vi.fn(),
    warning: vi.fn(),
  },
}))

const flushPromises = async () => {
  await new Promise((resolve) => setTimeout(resolve, 0))
}

describe('DashboardView', () => {
  it('应将可用代理文案收紧为 B 级及以上', async () => {
    const wrapper = shallowMount(DashboardView, {
      global: {
        directives: {
          loading: () => {},
        },
        stubs: {
          'el-button': { template: '<button><slot /></button>' },
          'el-card': { template: '<div><slot /></div>' },
          'el-tag': { template: '<span><slot /></span>' },
          'el-icon': { template: '<i><slot /></i>' },
          'el-tooltip': { template: '<div><slot /></div>' },
          'el-skeleton': true,
          'el-empty': true,
        },
      },
    })

    await flushPromises()
    await flushPromises()

    expect(wrapper.text()).toContain('可用代理(B级及以上)')
  })

  it('应移除假的国家筛选按钮，只展示前列国家和数量', async () => {
    vi.mocked(getDashboardOverview).mockResolvedValueOnce({
      total_proxies: 10,
      available_proxies: 6,
      avg_response_time: 120,
      last_updated: '2026-03-28 10:00:00',
      available_grade_distribution: {
        S: 1,
        A: 2,
        B: 3,
      },
      available_proxy_type_distribution: [],
      available_country_distribution: [
        { country_code: 'US', country_name: '美国', count: 4 },
        { country_code: 'JP', country_name: '日本', count: 2 },
      ],
    })

    const wrapper = shallowMount(DashboardView, {
      global: {
        directives: {
          loading: () => {},
        },
        stubs: {
          'el-button': { template: '<button><slot /></button>' },
          'el-card': { template: '<div><slot /></div>' },
          'el-tag': { template: '<span><slot /></span>' },
          'el-icon': { template: '<i><slot /></i>' },
          'el-tooltip': { template: '<div><slot /></div>' },
          'el-skeleton': true,
          'el-empty': true,
        },
      },
    })

    await flushPromises()
    await flushPromises()

    expect(wrapper.text()).not.toContain('全部')
    expect(wrapper.text()).toContain('美国')
    expect(wrapper.text()).toContain('4')
  })
})
