import { shallowMount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'

import MetricCard from './MetricCard.vue'

vi.mock('@/api/apiClient', () => ({
  getMetricsHistory: vi.fn(async () => ({
    time_labels: [],
    values: [],
  })),
}))

vi.mock('echarts', () => ({
  init: vi.fn(() => ({
    setOption: vi.fn(),
    resize: vi.fn(),
    dispose: vi.fn(),
  })),
  graphic: {
    LinearGradient: vi.fn(() => ({})),
  },
}))

describe('MetricCard', () => {
  it('使用 value 作为 radio 值，避免 label 充当 value 的废弃警告', () => {
    const wrapper = shallowMount(MetricCard, {
      props: {
        title: 'QPS',
        value: 1,
        metricKey: 'qps',
      },
      global: {
        stubs: {
          'el-card': {
            template: '<div><slot /></div>',
          },
          'el-tag': true,
          'el-icon': true,
          'el-collapse-transition': {
            template: '<div><slot /></div>',
          },
          'el-divider': true,
          'el-radio-group': {
            template: '<div><slot /></div>',
          },
          'el-radio-button': true,
        },
      },
    })

    const html = wrapper.html()
    expect(html).toContain('value="1h"')
    expect(html).toContain('value="6h"')
    expect(html).toContain('value="24h"')
    expect(html).not.toContain('label="1h"')
    expect(html).not.toContain('label="6h"')
    expect(html).not.toContain('label="24h"')
  })
})
