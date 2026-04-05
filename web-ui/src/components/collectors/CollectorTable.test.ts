import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import CollectorTable from './CollectorTable.vue'
import type { CollectorTableRow } from './CollectorTable.vue'

const sampleRow: CollectorTableRow = {
  id: 'demo',
  name: 'Demo Collector',
  mode: 'simple',
  source: 'api',
  enabled: true,
  lifecycle: 'draft',
  interval_seconds: 300,
  spec: {},
  actionLoading: false,
  lastRun: {
    run_id: 'run-1',
    collector_id: 'demo',
    trigger: 'test',
    status: 'success',
    started_at: '2026-03-09T12:00:00',
    ended_at: '2026-03-09T12:00:01',
    duration_ms: 1000,
    metrics: {
      raw_count: 1,
      valid_count: 1,
      stored_count: 1,
      duplicate_count: 0,
      cooldown_blocked_count: 2,
    },
    error_details: [],
  },
}

describe('CollectorTable', () => {
  it('应以卡片方式展示收集器的关键状态与最近运行指标', async () => {
    const wrapper = mount(CollectorTable, {
      props: {
        collectors: [sampleRow],
      },
      global: {
        stubs: {
          'el-empty': true,
          'el-tag': { template: '<span><slot /></span>' },
          'el-button': { template: '<button @click="$emit(\'click\')"><slot /></button>' },
        },
      },
    })

    const cards = wrapper.findAll('[data-testid="collector-card"]')
    expect(cards).toHaveLength(1)

    expect(wrapper.text()).toContain('Demo Collector')
    expect(wrapper.text()).toContain('草稿')
    expect(wrapper.text()).toContain('简单模式')
    expect(wrapper.text()).toContain('API')
    expect(wrapper.text()).toContain('执行间隔')
    expect(wrapper.text()).toContain('5分钟')
    expect(wrapper.text()).toContain('最近运行')
    expect(wrapper.text()).toContain('成功')
    expect(wrapper.text()).toContain('raw 1')
    expect(wrapper.text()).toContain('valid 1')
    expect(wrapper.text()).toContain('stored 1')
    expect(wrapper.text()).toContain('duplicate 0')
    expect(wrapper.text()).toContain('冷却阻断 2')

    const publishButton = wrapper.findAll('button').find(btn => btn.text().includes('发布'))
    expect(publishButton).toBeTruthy()
    await publishButton!.trigger('click')

    const events = wrapper.emitted('publish')
    expect(events).toBeTruthy()
    const firstPayload = events?.[0]?.[0] as CollectorTableRow
    expect(firstPayload.id).toBe('demo')
  })
})
