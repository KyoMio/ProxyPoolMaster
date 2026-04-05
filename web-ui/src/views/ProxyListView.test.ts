import { shallowMount } from '@vue/test-utils'
import { h } from 'vue'
import { describe, expect, it, vi } from 'vitest'

import ProxyListView from './ProxyListView.vue'
import { getProxies } from '@/api/apiClient'

vi.mock('@/api/apiClient', () => ({
  getProxies: vi.fn(async () => ({
    data: [],
    total: 0,
  })),
}))

vi.mock('@/assets/country_code_to_zh.json', () => ({
  default: {},
}))

vi.mock('element-plus', () => ({
  ElMessage: {
    error: vi.fn(),
  },
}))

const flushPromises = async () => {
  await new Promise((resolve) => setTimeout(resolve, 0))
}

describe('ProxyListView', () => {
  it('应默认按 B 级及以上展示可用代理语义', async () => {
    const wrapper = shallowMount(ProxyListView, {
      global: {
        directives: {
          loading: () => {},
        },
        stubs: {
          'el-card': { template: '<div><slot name="header" /><slot /></div>' },
          'el-button': { template: '<button><slot /></button>' },
          'el-form': { template: '<form><slot /></form>' },
          'el-form-item': { props: ['label'], template: '<div><span class="label">{{ label }}</span><slot /></div>' },
          'el-row': { template: '<div><slot /></div>' },
          'el-col': { template: '<div><slot /></div>' },
          'el-select': { template: '<div><slot /></div>' },
          'el-option': { template: '<div><slot /></div>' },
          'el-tag': { template: '<span><slot /></span>' },
          'el-table': { template: '<div><slot /></div>' },
          'el-table-column': {
            render() {
              return h('div', {}, this.$slots.default?.({
                row: {
                  protocol: 'http',
                  grade: 'C',
                  country: 'US',
                  anonymity: 'elite',
                  responseTime: 0,
                  successCount: 0,
                  failCount: 0,
                  lastCheckTime: 'N/A',
                  fullProxyString: 'http://1.1.1.1:80',
                },
              }))
            },
          },
          'el-pagination': true,
        },
      },
    })

    await flushPromises()
    await flushPromises()

    expect(wrapper.text()).toContain('B级及以上')
    expect(wrapper.text()).toContain('低通过率 (1目标)')
    expect(wrapper.text()).not.toContain('可用 (1目标)')
    expect((getProxies as unknown as { mock: { calls: any[] } }).mock.calls[0][0]).toMatchObject({
      is_available: true,
    })
  })

  it('应将等级筛选直接透传给后端，避免当前页本地过滤', async () => {
    const wrapper = shallowMount(ProxyListView, {
      global: {
        directives: {
          loading: () => {},
        },
        stubs: {
          'el-card': { template: '<div><slot name="header" /><slot /></div>' },
          'el-button': { template: '<button><slot /></button>' },
          'el-form': { template: '<form><slot /></form>' },
          'el-form-item': { props: ['label'], template: '<div><span class="label">{{ label }}</span><slot /></div>' },
          'el-row': { template: '<div><slot /></div>' },
          'el-col': { template: '<div><slot /></div>' },
          'el-select': { template: '<div><slot /></div>' },
          'el-option': { template: '<div><slot /></div>' },
          'el-tag': { template: '<span><slot /></span>' },
          'el-table': { template: '<div><slot /></div>' },
          'el-table-column': true,
          'el-pagination': true,
        },
      },
    })

    await flushPromises()
    await flushPromises()

    const vm = wrapper.vm as unknown as {
      filterForm: { grade: string }
      applyFilter: () => void
    }
    vm.filterForm.grade = 'A'
    vm.applyFilter()
    await flushPromises()

    const calls = (getProxies as unknown as { mock: { calls: any[] } }).mock.calls
    expect(calls[calls.length - 1][0]).toMatchObject({
      grade: 'A',
    })
  })
})
