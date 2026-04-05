import { mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'

import Layout from './Layout.vue'

vi.mock('vue-router', () => ({
  useRoute: () => ({
    path: '/dashboard',
  }),
}))

vi.mock('element-plus', () => ({
  ElMessage: {
    success: vi.fn(),
    warning: vi.fn(),
    info: vi.fn(),
  },
}))

vi.stubGlobal('localStorage', {
  getItem: vi.fn(() => null),
  setItem: vi.fn(),
  removeItem: vi.fn(),
  clear: vi.fn(),
})

describe('Layout branding', () => {
  it('should render ProxyPoolMaster branding and avoid emoji-only collapsed logo', async () => {
    const wrapper = mount(Layout, {
      global: {
        stubs: {
          'el-container': { template: '<div><slot /></div>' },
          'el-aside': { template: '<aside><slot /></aside>' },
          'el-menu': { template: '<nav><slot /></nav>' },
          'el-menu-item': { template: '<div><slot name="title" /></div>' },
          'el-header': { template: '<header><slot /></header>' },
          'el-main': { template: '<main><slot /></main>' },
          'el-dialog': { template: '<div><slot /></div>' },
          'el-form': { template: '<form><slot /></form>' },
          'el-form-item': { template: '<div><slot /></div>' },
          'el-input': { template: '<input />' },
          'el-alert': { template: '<div><slot /></div>' },
          'el-button': { template: '<button><slot /></button>' },
          'el-icon': { template: '<span @click="$emit(\'click\')"><slot /></span>' },
          'router-view': { template: '<div />' },
          DataLine: true,
          Connection: true,
          Document: true,
          Setting: true,
          Monitor: true,
          Fold: true,
          Expand: true,
          Lock: true,
        },
      },
    })

    expect(wrapper.find('.logo-text').text()).toBe('ProxyPoolMaster')

    await wrapper.get('.collapse-btn').trigger('click')

    expect(wrapper.find('.logo-icon').text()).not.toContain('📊')
  })
})
