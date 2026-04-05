import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import CollectorRunHistoryDrawer from './CollectorRunHistoryDrawer.vue'

describe('CollectorRunHistoryDrawer', () => {
  it('点击查看日志应发出 view-log 事件并携带 collector_id/run_id', async () => {
    const wrapper = mount(CollectorRunHistoryDrawer, {
      props: {
        visible: true,
        loading: false,
        collectorName: 'Demo',
        runs: [
          {
            run_id: 'run-123',
            collector_id: 'collector-a',
            trigger: 'test',
            status: 'failed',
            started_at: '2026-03-09T12:00:00',
            ended_at: '2026-03-09T12:00:01',
            duration_ms: 1000,
            metrics: {
              raw_count: 1,
              valid_count: 0,
              stored_count: 0,
              duplicate_count: 0,
              cooldown_blocked_count: 0,
            },
            error_details: ['boom'],
          },
        ],
      },
      global: {
        stubs: {
          'el-drawer': { template: '<div><slot name="header" /><slot /></div>' },
          'el-skeleton': true,
          'el-empty': true,
          'el-table': { template: '<div><slot /></div>' },
          'el-table-column': { template: '<div><slot :row="$attrs.row || {}" /></div>' },
          'el-tag': { template: '<span><slot /></span>' },
          'el-button': { template: '<button @click="$emit(\'click\')"><slot /></button>' },
        },
      },
    })

    const viewLogButton = wrapper.findAll('button').find(btn => btn.text().includes('查看日志'))
    expect(viewLogButton).toBeTruthy()
    await viewLogButton!.trigger('click')

    const events = wrapper.emitted('view-log')
    expect(events).toBeTruthy()
    expect(events?.[0]).toEqual(['collector-a', 'run-123'])
  })
})
