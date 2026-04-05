import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import CollectorToolbar from './CollectorToolbar.vue'

describe('CollectorToolbar', () => {
  it('应渲染控制头部并在点击新建按钮时发出 create 事件', async () => {
    const wrapper = mount(CollectorToolbar, {
      global: {
        stubs: {
          'el-button': { template: '<button @click="$emit(\'click\')"><slot /></button>' },
          'el-tag': { template: '<span><slot /></span>' },
        },
      },
    })

    expect(wrapper.text()).toContain('收集器管理')
    expect(wrapper.text()).toContain('运维视图')
    expect(wrapper.text()).toContain('V2 流程：测试运行 -> 发布 -> 暂停/恢复')

    const createButton = wrapper.findAll('button').find(button => button.text().includes('新建收集器'))
    expect(createButton).toBeTruthy()

    await createButton!.trigger('click')
    expect(wrapper.emitted('create')).toBeTruthy()
  })

  it('传入 worker 摘要时应展示状态、执行中与待执行', () => {
    const wrapper = mount(CollectorToolbar, {
      props: {
        workerSummary: {
          status: 'running',
          activeJobs: 3,
          queueBacklog: 8,
          lastHeartbeat: '2026-03-09T18:10:00',
        },
        overviewSummary: {
          total: 12,
          published: 7,
          paused: 3,
          draft: 2,
          recentStoredCount: 24,
          successRate: 0.75,
          cooldownPoolCount: 4,
        },
      },
      global: {
        stubs: {
          'el-button': { template: '<button><slot /></button>' },
          'el-tag': { template: '<span><slot /></span>' },
        },
      },
    })

    const text = wrapper.text()
    expect(text).toContain('Collector Worker：运行中')
    expect(text).toContain('执行中 3')
    expect(text).toContain('待执行 8')
    expect(text).toContain('总数 12')
    expect(text).toContain('最近入库 24')
    expect(text).toContain('冷却池 4')
  })

  it('非运行状态时应弱化显示指标含义', () => {
    const wrapper = mount(CollectorToolbar, {
      props: {
        workerSummary: {
          status: 'stopped',
          activeJobs: 0,
          queueBacklog: 0,
          lastHeartbeat: '',
        },
      },
      global: {
        stubs: {
          'el-button': { template: '<button><slot /></button>' },
          'el-tag': { template: '<span><slot /></span>' },
        },
      },
    })

    const text = wrapper.text()
    expect(text).toContain('Collector Worker：离线')
    expect(text).toContain('执行中 0')
    expect(text).toContain('待执行 0')
    expect(text).toContain('当前状态下指标仅供参考')
  })
})
