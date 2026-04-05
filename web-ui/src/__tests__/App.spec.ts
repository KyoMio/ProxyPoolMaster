import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import App from '../App.vue'

vi.mock('vue-router', () => ({
  useRoute: () => ({ path: '/dashboard' }),
}))

describe('App', () => {
  it('mounts layout properly', () => {
    const wrapper = mount(App, {
      global: {
        stubs: {
          Sidebar: true,
          Header: true,
          RouterView: true,
        },
      },
    })
    expect(wrapper.find('.layout').exists()).toBe(true)
    expect(wrapper.find('.main-content').exists()).toBe(true)
  })
})
