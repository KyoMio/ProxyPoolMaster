import { mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const mockPush = vi.fn()
const mockGetRuntimeInfo = vi.fn()

vi.mock('vue-router', () => ({
  useRoute: () => ({
    path: '/dashboard',
  }),
  useRouter: () => ({
    push: mockPush,
  }),
}))

vi.mock('@/composables/useBreakpoint', () => ({
  useBreakpoint: () => ({
    isMobile: { value: false },
  }),
}))

vi.mock('@/api/apiClient', () => ({
  getRuntimeInfo: (...args: unknown[]) => mockGetRuntimeInfo(...args),
}))

const flushPromises = async () => {
  await Promise.resolve()
  await Promise.resolve()
}

const mountSidebar = async (buildLabel: string, runtimeLabel?: string | null) => {
  vi.resetModules()
  mockGetRuntimeInfo.mockReset()
  if (runtimeLabel) {
    mockGetRuntimeInfo.mockResolvedValue({ label: runtimeLabel })
  } else {
    mockGetRuntimeInfo.mockResolvedValue({ label: '' })
  }
  vi.doMock('@/config/buildInfo', () => ({
    appBuildLabel: buildLabel,
  }))

  const { default: Sidebar } = await import('./Sidebar.vue')
  const wrapper = mount(Sidebar, {
    props: {
      collapsed: false,
    },
  })
  await flushPromises()
  return wrapper
}

describe('Sidebar build info', () => {
  beforeEach(() => {
    mockPush.mockReset()
  })

  it('应展示 ProxyPoolMaster 品牌名称', async () => {
    const wrapper = await mountSidebar('7074ed5')

    expect(wrapper.get('.logo-text').text()).toBe('ProxyPoolMaster')
  })

  it('源码运行时应只显示最新 commit hash', async () => {
    const wrapper = await mountSidebar('7074ed5')

    expect(wrapper.get('.sidebar-footer').text()).toContain('7074ed5')
    expect(wrapper.get('.sidebar-footer').text()).not.toContain('运行正常')
    expect(wrapper.get('.sidebar-footer').text()).not.toContain('v')
  })

  it('发布版本存在时应显示版本号与 commit hash', async () => {
    const wrapper = await mountSidebar('v1.2.0 (7074ed5)')

    expect(wrapper.get('.sidebar-footer').text()).toContain('v1.2.0 (7074ed5)')
  })

  it('运行时镜像标签存在时应优先展示镜像标签', async () => {
    const wrapper = await mountSidebar('v1.2.0 (7074ed5)', 'ghcr.io/example/proxypoolmaster:v1.2.0')

    expect(wrapper.get('.sidebar-footer').text()).toContain('ghcr.io/example/proxypoolmaster:v1.2.0')
    expect(wrapper.get('.sidebar-footer').text()).not.toContain('7074ed5')
  })
})
