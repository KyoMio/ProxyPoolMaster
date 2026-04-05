import { shallowMount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import ConfigView from './ConfigView.vue'
import { getConfig, saveGlobalConfig } from '@/api/apiClient'
import { ElMessage } from 'element-plus'

vi.mock('@/api/apiClient', () => ({
  getConfig: vi.fn(async () => ({
    global_config: {
      REDIS_HOST: 'redis',
      REDIS_PORT: 6379,
      REDIS_DB: 0,
      REDIS_PASSWORD: '',
      LOG_LEVEL: 'INFO',
      LOG_MAX_BYTES: 10485760,
      LOG_BACKUP_COUNT: 5,
      TIMEZONE: 'Asia/Shanghai',
      REQUEST_TIMEOUT: 0,
      COLLECT_INTERVAL_SECONDS: 0,
      TEST_INTERVAL_SECONDS: 0,
      MAX_FAIL_COUNT: 0,
      TESTER_LOG_EACH_PROXY: false,
      TEST_MAX_CONCURRENT: 0,
      TEST_TIMEOUT_PER_TARGET: 0,
      TEST_TARGETS: [],
      COLLECTOR_RUNTIME_MODE: 'v2',
      COLLECTOR_WORKER_ENABLED: 1,
      COLLECTOR_WORKER_ID: 'collector-worker-1',
      COLLECTOR_WORKER_TICK_SECONDS: 1,
      COLLECTOR_WORKER_MAX_CONCURRENT: 4,
      COLLECTOR_EXEC_TIMEOUT: 60,
      COLLECTOR_EXEC_MAX_MEMORY_MB: 256,
      COLLECTOR_EXEC_STDOUT_LIMIT_KB: 256,
      COLLECTOR_RUN_HISTORY_LIMIT: 200,
      API_TOKEN: '',
      RATE_LIMIT_PROXY_MINUTE: '0/minute',
      RATE_LIMIT_HEALTH_MINUTE: '0/minute',
    },
    collector_configs: [],
    config_sources: {
      from_env: [],
      from_file: [],
      using_defaults: [],
    },
  })),
  saveGlobalConfig: vi.fn(async () => ({})),
}))

vi.mock('element-plus', () => ({
  ElMessage: {
    error: vi.fn(),
    success: vi.fn(),
    warning: vi.fn(),
    info: vi.fn(),
  },
  ElMessageBox: {
    confirm: vi.fn(() => Promise.resolve()),
  },
}))

const flushPromises = async () => {
  await new Promise((resolve) => setTimeout(resolve, 0))
}

const configViewStubs = {
  'el-card': { template: '<div><slot name="header" /><slot /></div>' },
  'el-button': true,
  'el-tag': true,
  'el-skeleton': true,
  'el-form': { template: '<form><slot /></form>' },
  'el-form-item': {
    props: ['label'],
    template: '<div class="form-item"><span class="form-item-label">{{ label }}</span><slot /></div>',
  },
  'el-row': { template: '<div><slot /></div>' },
  'el-col': { template: '<div><slot /></div>' },
  'el-input-number': { template: '<div class="input-number-stub" />' },
  'el-input': { template: '<div class="input-stub" />' },
  'el-switch': { template: '<div class="switch-stub" />' },
  'el-select': { template: '<div class="select-stub"><slot /></div>' },
  'el-option': { template: '<div class="option-stub" />' },
  'el-slider': { template: '<div class="slider-stub" />' },
  'el-alert': { template: '<div><slot name="title" /></div>' },
  'el-icon': { template: '<span><slot /></span>' },
  'time-input-with-unit': { template: '<div class="time-input-stub" />' },
}

const mountConfigView = () =>
  shallowMount(ConfigView, {
    global: {
      directives: {
        loading: () => {},
      },
      stubs: configViewStubs,
    },
  })

type ConfigViewVm = {
  config: {
    collector: Record<string, unknown>
    tester: Record<string, unknown>
    testerAdvanced: Record<string, unknown>
    worker: Record<string, unknown>
    execution: Record<string, unknown>
    testTargets: string[]
  }
  saveAllConfig?: () => Promise<void>
  restoreDefaults?: () => void
  showAdvancedSettings?: boolean
}

describe('ConfigView fallback behavior', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('should preserve 0/false values from backend config', async () => {
    const wrapper = mountConfigView()

    await flushPromises()
    await flushPromises()

    const vm = wrapper.vm as unknown as ConfigViewVm
    expect(vm.config.collector.REQUEST_TIMEOUT).toBe(0)
    expect(vm.config.collector.COLLECT_INTERVAL_SECONDS).toBe(0)
    expect(vm.config.tester.TEST_INTERVAL_SECONDS).toBe(0)
    expect(vm.config.tester.MAX_FAIL_COUNT).toBe(0)
    expect(vm.config.tester.TESTER_LOG_EACH_PROXY).toBe(false)
    expect(vm.config.testerAdvanced.TEST_MAX_CONCURRENT).toBe(0)
    expect(vm.config.testerAdvanced.TEST_TIMEOUT_PER_TARGET).toBe(0)
  })

  it('should load new collector runtime and advanced config fields', async () => {
    const wrapper = mountConfigView()

    await flushPromises()
    await flushPromises()

    const vm = wrapper.vm as unknown as ConfigViewVm
    expect(vm.config.collector.COLLECTOR_RUNTIME_MODE).toBe('v2')
    expect(vm.config.worker.COLLECTOR_WORKER_ID).toBe('collector-worker-1')
    expect(vm.config.execution.COLLECTOR_EXEC_TIMEOUT).toBe(60)
  })

  it('should show restart hint when backend returns requires_restart', async () => {
    vi.mocked(getConfig).mockResolvedValueOnce({
      global_config: {
        REDIS_HOST: 'redis',
        REDIS_PORT: 6379,
        REDIS_DB: 0,
        REDIS_PASSWORD: '',
        LOG_LEVEL: 'INFO',
        LOG_MAX_BYTES: 10485760,
        LOG_BACKUP_COUNT: 5,
        TIMEZONE: 'Asia/Shanghai',
        REQUEST_TIMEOUT: 10,
        COLLECT_INTERVAL_SECONDS: 300,
        TEST_INTERVAL_SECONDS: 300,
        MAX_FAIL_COUNT: 5,
        TESTER_LOG_EACH_PROXY: false,
        TEST_MAX_CONCURRENT: 100,
        TEST_TIMEOUT_PER_TARGET: 5,
        TEST_TARGETS: ['http://example.com'],
        COLLECTOR_RUNTIME_MODE: 'v2',
        COLLECTOR_WORKER_ENABLED: 1,
        COLLECTOR_WORKER_ID: 'collector-worker-1',
        COLLECTOR_WORKER_TICK_SECONDS: 1,
        COLLECTOR_WORKER_MAX_CONCURRENT: 4,
        COLLECTOR_EXEC_TIMEOUT: 60,
        COLLECTOR_EXEC_MAX_MEMORY_MB: 256,
        COLLECTOR_EXEC_STDOUT_LIMIT_KB: 256,
        COLLECTOR_RUN_HISTORY_LIMIT: 200,
        API_TOKEN: '',
        RATE_LIMIT_PROXY_MINUTE: '60/minute',
        RATE_LIMIT_HEALTH_MINUTE: '30/minute',
      },
      collector_configs: [],
      config_sources: {
        from_env: [],
        from_file: [],
        using_defaults: [],
      },
    })
    vi.mocked(saveGlobalConfig).mockResolvedValueOnce({
      message: 'ok',
      updated_keys: [],
      file_saved: true,
      config_sources: { from_env: [], from_file: [], using_defaults: [] },
      requires_restart: ['API_HOST'],
    })

    const wrapper = mountConfigView()
    await flushPromises()
    await flushPromises()

    const vm = wrapper.vm as unknown as ConfigViewVm
    vm.config.testTargets = ['http://example.com']
    await vm.saveAllConfig?.()

    expect(vi.mocked(ElMessage.warning)).toHaveBeenCalled()
  })

  it('should include new runtime fields when saving', async () => {
    const wrapper = mountConfigView()
    await flushPromises()
    await flushPromises()

    const vm = wrapper.vm as unknown as ConfigViewVm
    vm.config.collector.COLLECTOR_RUNTIME_MODE = 'v2'
    vm.config.testTargets = ['http://example.com']
    vm.config.testerAdvanced.TEST_BATCH_SIZE = 321
    vm.config.testerAdvanced.TEST_IDLE_SLEEP_SECONDS = 7
    vm.config.testerAdvanced.TEST_SCHEDULE_ZSET_KEY = 'custom:test_schedule'
    vm.config.testerAdvanced.TEST_MIGRATION_BATCH_SIZE = 999

    await vm.saveAllConfig?.()

    expect(vi.mocked(saveGlobalConfig)).toHaveBeenCalledTimes(1)
    expect(vi.mocked(saveGlobalConfig)).toHaveBeenCalledWith(
      expect.objectContaining({
        config: expect.objectContaining({
          COLLECTOR_RUNTIME_MODE: 'v2',
          COLLECTOR_WORKER_ENABLED: expect.any(Number),
          COLLECTOR_EXEC_TIMEOUT: expect.any(Number),
          TEST_BATCH_SIZE: 321,
          TEST_IDLE_SLEEP_SECONDS: 7,
          TEST_SCHEDULE_ZSET_KEY: 'custom:test_schedule',
          TEST_MIGRATION_BATCH_SIZE: 999,
        }),
      }),
    )
    const savedPayload = vi.mocked(saveGlobalConfig).mock.calls[0]?.[0] as { config: Record<string, unknown> }
    expect(savedPayload.config.DISABLE_API_COLLECTOR).toBeUndefined()
    expect(savedPayload.config.API_HOST).toBeUndefined()
    expect(savedPayload.config.API_PORT).toBeUndefined()
    expect(savedPayload.config.DASHBOARD_WS_BROADCAST_INTERVAL_SECONDS).toBeUndefined()
    expect(savedPayload.config.SYSTEM_WS_BROADCAST_INTERVAL_SECONDS).toBeUndefined()
    expect(savedPayload.config.DISABLE_API_TESTER).toBeUndefined()
  })

  it('should load missing tester scheduling fields from backend config', async () => {
    vi.mocked(getConfig).mockResolvedValueOnce({
      global_config: {
        REDIS_HOST: 'redis',
        REDIS_PORT: 6379,
        REDIS_DB: 0,
        REDIS_PASSWORD: '',
        LOG_LEVEL: 'INFO',
        LOG_MAX_BYTES: 10485760,
        LOG_BACKUP_COUNT: 5,
        TIMEZONE: 'Asia/Shanghai',
        REQUEST_TIMEOUT: 10,
        COLLECT_INTERVAL_SECONDS: 300,
        TEST_INTERVAL_SECONDS: 300,
        MAX_FAIL_COUNT: 5,
        TESTER_LOG_EACH_PROXY: false,
        TEST_MAX_CONCURRENT: 100,
        TEST_TIMEOUT_PER_TARGET: 5,
        TEST_BATCH_SIZE: 200,
        TEST_IDLE_SLEEP_SECONDS: 2,
        TEST_SCHEDULE_ZSET_KEY: 'proxies:test_schedule',
        TEST_MIGRATION_BATCH_SIZE: 500,
        TEST_TARGETS: ['http://example.com'],
        COLLECTOR_RUNTIME_MODE: 'v2',
        COLLECTOR_WORKER_ENABLED: 1,
        COLLECTOR_WORKER_ID: 'collector-worker-1',
        COLLECTOR_WORKER_TICK_SECONDS: 1,
        COLLECTOR_WORKER_MAX_CONCURRENT: 4,
        COLLECTOR_EXEC_TIMEOUT: 60,
        COLLECTOR_EXEC_MAX_MEMORY_MB: 256,
        COLLECTOR_EXEC_STDOUT_LIMIT_KB: 256,
        COLLECTOR_RUN_HISTORY_LIMIT: 200,
        API_TOKEN: '',
        RATE_LIMIT_PROXY_MINUTE: '60/minute',
        RATE_LIMIT_HEALTH_MINUTE: '30/minute',
      },
      collector_configs: [],
      config_sources: {
        from_env: [],
        from_file: [],
        using_defaults: [],
      },
    })

    const wrapper = mountConfigView()

    await flushPromises()
    await flushPromises()

    const vm = wrapper.vm as unknown as ConfigViewVm
    expect(vm.config.testerAdvanced.TEST_BATCH_SIZE).toBe(200)
    expect(vm.config.testerAdvanced.TEST_IDLE_SLEEP_SECONDS).toBe(2)
    expect(vm.config.testerAdvanced.TEST_SCHEDULE_ZSET_KEY).toBe('proxies:test_schedule')
    expect(vm.config.testerAdvanced.TEST_MIGRATION_BATCH_SIZE).toBe(500)
  })

  it('should restore missing tester scheduling fields to defaults', async () => {
    const wrapper = mountConfigView()

    await flushPromises()
    await flushPromises()

    const vm = wrapper.vm as unknown as ConfigViewVm
    vm.config.testerAdvanced.TEST_BATCH_SIZE = 999
    vm.config.testerAdvanced.TEST_IDLE_SLEEP_SECONDS = 11
    vm.config.testerAdvanced.TEST_SCHEDULE_ZSET_KEY = 'custom:test_schedule'
    vm.config.testerAdvanced.TEST_MIGRATION_BATCH_SIZE = 777

    vm.restoreDefaults?.()
    await flushPromises()
    await flushPromises()

    expect(vm.config.testerAdvanced.TEST_BATCH_SIZE).toBe(200)
    expect(vm.config.testerAdvanced.TEST_IDLE_SLEEP_SECONDS).toBe(2)
    expect(vm.config.testerAdvanced.TEST_SCHEDULE_ZSET_KEY).toBe('proxies:test_schedule')
    expect(vm.config.testerAdvanced.TEST_MIGRATION_BATCH_SIZE).toBe(500)
  })

  it('should render missing tester scheduling fields in the advanced config panel', async () => {
    const wrapper = mountConfigView()

    await flushPromises()
    await flushPromises()

    const vm = wrapper.vm as unknown as ConfigViewVm
    vm.showAdvancedSettings = true
    await flushPromises()

    expect(wrapper.text()).toContain('单批测试数量')
    expect(wrapper.text()).toContain('空闲休眠秒数')
    expect(wrapper.text()).toContain('测试调度 Key')
    expect(wrapper.text()).toContain('迁移批次数量')
  })

  it('should not render env-only api runtime fields in advanced panel', async () => {
    const wrapper = mountConfigView()

    await flushPromises()
    await flushPromises()

    const vm = wrapper.vm as unknown as ConfigViewVm
    vm.showAdvancedSettings = true
    await flushPromises()

    expect(wrapper.text()).not.toContain('API 运行高级配置')
    expect(wrapper.text()).not.toContain('API Host')
    expect(wrapper.text()).not.toContain('API Port')
  })

  it('should include missing tester scheduling fields when saving', async () => {
    const wrapper = mountConfigView()
    await flushPromises()
    await flushPromises()

    const vm = wrapper.vm as unknown as ConfigViewVm
    vm.config.testTargets = ['http://example.com']
    await vm.saveAllConfig?.()

    expect(vi.mocked(saveGlobalConfig)).toHaveBeenCalledTimes(1)
    expect(vi.mocked(saveGlobalConfig)).toHaveBeenCalledWith(
      expect.objectContaining({
        config: expect.objectContaining({
          TEST_BATCH_SIZE: expect.any(Number),
          TEST_IDLE_SLEEP_SECONDS: expect.any(Number),
          TEST_SCHEDULE_ZSET_KEY: expect.any(String),
          TEST_MIGRATION_BATCH_SIZE: expect.any(Number),
        }),
      }),
    )
  })
})
