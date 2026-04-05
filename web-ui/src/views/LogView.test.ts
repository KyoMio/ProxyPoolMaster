import { shallowMount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'

import LogView from './LogView.vue'

const { mockConfirm, mockSuccess } = vi.hoisted(() => ({
  mockConfirm: vi.fn(() => Promise.resolve()),
  mockSuccess: vi.fn(),
}))

vi.mock('@/api/apiClient', () => ({
  getLogs: vi.fn(async () => ({
    data: [],
    total: 0,
  })),
  clearLogs: vi.fn(async () => ({
    message: 'ok',
  })),
}))

vi.mock('element-plus', () => ({
  ElMessage: {
    success: mockSuccess,
    error: vi.fn(),
    info: vi.fn(),
  },
  ElMessageBox: {
    confirm: mockConfirm,
  },
}))

vi.mock('@/services/realtime', () => ({
  logRealtimeClient: {
    subscribe: vi.fn(() => () => {}),
    subscribeLogs: vi.fn(),
    unsubscribeLogs: vi.fn(),
  },
}))

vi.mock('vue-router', () => ({
  useRoute: () => ({
    query: {},
  }),
  useRouter: () => ({
    replace: vi.fn(),
  }),
}))

describe('LogView tag type', () => {
  it('APP 组件应返回合法 ElTag type，避免空字符串触发校验警告', () => {
    const wrapper = shallowMount(LogView, {
      global: {
        directives: {
          loading: () => {},
        },
        stubs: {
          'el-card': { template: '<div><slot name="header" /><slot /></div>' },
          'el-switch': true,
          'el-button': true,
          'el-form': { template: '<form><slot /></form>' },
          'el-form-item': {
            props: ['label'],
            template: '<div><span class="form-item-label">{{ label }}</span><slot /></div>',
          },
          'el-select': { template: '<div><slot /></div>' },
          'el-option': { template: '<div><slot /></div>' },
          'el-tag': true,
          'el-input': true,
          'el-table': { template: '<div><slot /></div>' },
          'el-table-column': { template: '<div />' },
          'el-pagination': true,
          'el-dialog': { template: '<div><slot /></div>' },
        },
      },
    })
    const type = (wrapper.vm as unknown as { getComponentTagType: (component: string) => string }).getComponentTagType('APP')
    expect(type).toBe('info')
  })

  it('构建请求过滤条件时应携带 collector_id 与 run_id', () => {
    const wrapper = shallowMount(LogView, {
      global: {
        directives: {
          loading: () => {},
        },
        stubs: {
          'el-card': { template: '<div><slot name="header" /><slot /></div>' },
          'el-switch': true,
          'el-button': true,
          'el-form': { template: '<form><slot /></form>' },
          'el-form-item': {
            props: ['label'],
            template: '<div><span class="form-item-label">{{ label }}</span><slot /></div>',
          },
          'el-select': { template: '<div><slot /></div>' },
          'el-option': { template: '<div><slot /></div>' },
          'el-tag': true,
          'el-input': true,
          'el-table': { template: '<div><slot /></div>' },
          'el-table-column': { template: '<div />' },
          'el-pagination': true,
          'el-dialog': { template: '<div><slot /></div>' },
        },
      },
    })

    const vm = wrapper.vm as unknown as {
      filterForm: { collectorId?: string; runId?: string }
      buildRequestFilters: () => Record<string, any>
    }
    vm.filterForm.collectorId = 'collector-a'
    vm.filterForm.runId = 'run-1'
    const filters = vm.buildRequestFilters()

    expect(filters.collector_id).toBe('collector-a')
    expect(filters.run_id).toBe('run-1')
  })

  it('日志筛选项应使用自然语言文案但仍保留原始查询字段映射', () => {
    const wrapper = shallowMount(LogView, {
      global: {
        directives: {
          loading: () => {},
        },
        stubs: {
          'el-card': { template: '<div><slot name="header" /><slot /></div>' },
          'el-switch': true,
          'el-button': true,
          'el-form': { template: '<form><slot /></form>' },
          'el-form-item': {
            props: ['label'],
            template: '<div><span class="form-item-label">{{ label }}</span><slot /></div>',
          },
          'el-select': { template: '<div><slot /></div>' },
          'el-option': { template: '<div><slot /></div>' },
          'el-tag': true,
          'el-input': true,
          'el-table': { template: '<div><slot /></div>' },
          'el-table-column': { template: '<div />' },
          'el-pagination': true,
          'el-dialog': { template: '<div><slot /></div>' },
        },
      },
    })

    expect(wrapper.text()).toContain('收集器标识')
    expect(wrapper.text()).toContain('运行批次标识')
  })

  it('确认清空日志后应调用清空接口', async () => {
    const { clearLogs } = await import('@/api/apiClient')
    const wrapper = shallowMount(LogView, {
      global: {
        directives: {
          loading: () => {},
        },
        stubs: {
          'el-card': { template: '<div><slot name="header" /><slot /></div>' },
          'el-switch': true,
          'el-button': true,
          'el-form': { template: '<form><slot /></form>' },
          'el-form-item': {
            props: ['label'],
            template: '<div><span class="form-item-label">{{ label }}</span><slot /></div>',
          },
          'el-select': { template: '<div><slot /></div>' },
          'el-option': { template: '<div><slot /></div>' },
          'el-tag': true,
          'el-input': true,
          'el-table': { template: '<div><slot /></div>' },
          'el-table-column': { template: '<div />' },
          'el-pagination': true,
          'el-dialog': { template: '<div><slot /></div>' },
        },
      },
    })

    const vm = wrapper.vm as unknown as {
      confirmClearLogs: () => Promise<void>
    }
    await vm.confirmClearLogs()

    expect(mockConfirm).toHaveBeenCalled()
    expect(vi.mocked(clearLogs)).toHaveBeenCalledTimes(1)
    expect(mockSuccess).toHaveBeenCalled()
  })
})
