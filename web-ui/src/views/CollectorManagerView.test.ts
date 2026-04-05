import { shallowMount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import CollectorManagerView from './CollectorManagerView.vue'
import { collectorApi } from '../api/apiClient'
import { ElMessage } from 'element-plus'

let collectorUpdateHandler: ((payload: any) => void) | null = null

vi.mock('../api/apiClient', () => ({
  collectorApi: {
    getCollectors: vi.fn(async () => ({ data: { collectors: [] } })),
    getCollectorRuns: vi.fn(async () => ({ data: { runs: [] } })),
    createCollector: vi.fn(),
    updateCollector: vi.fn(),
    deleteCollector: vi.fn(),
    testRunCollector: vi.fn(),
    publishCollector: vi.fn(),
    pauseCollector: vi.fn(),
    resumeCollector: vi.fn(),
  },
  getModuleStatus: vi.fn(async () => ([
    {
      moduleName: 'Collector Worker',
      status: 'Running',
      lastHeartbeat: '2026-03-09T18:12:00',
      performance: {
        active_jobs: 3,
        queue_backlog: 8,
      },
    },
  ])),
}))

vi.mock('@/services/realtime', () => ({
  dashboardRealtimeClient: {
    subscribe: vi.fn((eventType: string, handler: (payload: any) => void) => {
      if (eventType === 'collector_update') {
        collectorUpdateHandler = handler
      }
      return () => {}
    }),
    connect: vi.fn(),
    disconnect: vi.fn(),
  },
}))

vi.mock('vue-router', () => ({
  useRouter: () => ({
    push: vi.fn(),
  }),
}))

vi.mock('element-plus', () => ({
  ElMessage: {
    success: vi.fn(),
    error: vi.fn(),
    warning: vi.fn(),
  },
  ElMessageBox: {
    confirm: vi.fn(() => Promise.resolve()),
  },
}))

const flushPromises = async () => {
  await new Promise((resolve) => setTimeout(resolve, 0))
}

const createDeferred = <T>() => {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((res) => {
    resolve = res
  })
  return { promise, resolve }
}

const createControlledPromise = <T>() => {
  let resolve!: (value: T | PromiseLike<T>) => void
  let reject!: (reason?: any) => void
  const promise = new Promise<T>((res, rej) => {
    resolve = res
    reject = rej
  })
  return { promise, resolve, reject }
}

describe('CollectorManagerView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    collectorUpdateHandler = null
  })

  it('应将 worker 状态摘要传递给顶部 CollectorToolbar', async () => {
    const wrapper = shallowMount(CollectorManagerView, {
      global: {
        stubs: {
          CollectorToolbar: {
            props: ['workerSummary', 'overviewSummary'],
            template: '<div data-testid="toolbar">{{ workerSummary ? `${workerSummary.status}|${workerSummary.activeJobs}|${workerSummary.queueBacklog}` : "none" }}|{{ overviewSummary ? `${overviewSummary.total}|${overviewSummary.published}|${overviewSummary.paused}|${overviewSummary.draft}|${overviewSummary.recentStoredCount}` : "no-overview" }}</div>',
          },
          CollectorTable: {
            props: ['collectors'],
            template: '<div data-testid="collector-table">{{ collectors.length }}|{{ collectors.map((row) => row.lastRun?.metrics?.stored_count ?? 0).join(",") }}</div>',
          },
          CollectorEditorDialog: true,
          CollectorRunHistoryDrawer: true,
          'el-skeleton': true,
          'el-dialog': { template: '<div><slot /></div>' },
          'el-tag': { template: '<span><slot /></span>' },
          'el-divider': true,
          'el-scrollbar': { template: '<div><slot /></div>' },
          'el-button': { template: '<button><slot /></button>' },
        },
      },
    })

    await flushPromises()
    await flushPromises()

    expect(wrapper.get('[data-testid="toolbar"]').text()).toContain('running|3|8')
    expect(wrapper.get('[data-testid="overview-card-summary"]').text()).toContain('收集器概览')
  })

  it('应渲染收集器概览摘要卡片并显示统计信息', async () => {
    vi.mocked(collectorApi.getCollectors).mockResolvedValueOnce({
      data: {
        collectors: [
          {
            id: 'collector-a',
            name: 'Alpha',
            mode: 'simple',
            source: 'api',
            enabled: true,
            lifecycle: 'published',
            interval_seconds: 300,
            spec: {},
            code_ref: null,
          },
          {
            id: 'collector-b',
            name: 'Beta',
            mode: 'code',
            source: 'scrape',
            enabled: true,
            lifecycle: 'paused',
            interval_seconds: 600,
            spec: {},
            code_ref: null,
          },
          {
            id: 'collector-c',
            name: 'Gamma',
            mode: 'simple',
            source: 'api',
            enabled: false,
            lifecycle: 'draft',
            interval_seconds: 900,
            spec: {},
            code_ref: null,
          },
        ],
      },
    } as any)
    vi.mocked(collectorApi.getCollectorRuns)
      .mockResolvedValueOnce({
        data: {
          runs: [
            {
              run_id: 'run-a',
              collector_id: 'collector-a',
              trigger: 'test',
              status: 'success',
              started_at: '2026-03-19T10:00:00',
              ended_at: '2026-03-19T10:01:00',
              duration_ms: 60000,
              metrics: {
                raw_count: 10,
                valid_count: 8,
                stored_count: 6,
                duplicate_count: 2,
              },
            },
          ],
        },
      } as any)
      .mockResolvedValueOnce({
        data: {
          runs: [
            {
              run_id: 'run-b',
              collector_id: 'collector-b',
              trigger: 'schedule',
              status: 'partial_success',
              started_at: '2026-03-19T10:00:00',
              ended_at: '2026-03-19T10:02:00',
              duration_ms: 120000,
              metrics: {
                raw_count: 12,
                valid_count: 11,
                stored_count: 10,
                duplicate_count: 1,
              },
            },
          ],
        },
      } as any)
      .mockResolvedValueOnce({
        data: {
          runs: [
            {
              run_id: 'run-c',
              collector_id: 'collector-c',
              trigger: 'manual',
              status: 'failed',
              started_at: '2026-03-19T10:00:00',
              ended_at: '2026-03-19T10:03:00',
              duration_ms: 180000,
              metrics: {
                raw_count: 9,
                valid_count: 0,
                stored_count: 0,
                duplicate_count: 0,
              },
            },
          ],
        },
      } as any)

    const wrapper = shallowMount(CollectorManagerView, {
      global: {
        stubs: {
          CollectorToolbar: {
            props: ['workerSummary', 'overviewSummary'],
            template: '<div data-testid="toolbar">{{ workerSummary ? `${workerSummary.status}|${workerSummary.activeJobs}|${workerSummary.queueBacklog}` : "none" }}|{{ overviewSummary ? `${overviewSummary.total}|${overviewSummary.published}|${overviewSummary.paused}|${overviewSummary.draft}|${overviewSummary.recentStoredCount}` : "no-overview" }}</div>',
          },
          CollectorTable: {
            props: ['collectors'],
            template: '<div data-testid="collector-table">{{ collectors.length }}|{{ collectors.map((row) => row.lastRun?.metrics?.stored_count ?? 0).join(",") }}</div>',
          },
          CollectorEditorDialog: true,
          CollectorRunHistoryDrawer: true,
          'el-skeleton': true,
          'el-dialog': { template: '<div><slot /></div>' },
          'el-tag': { template: '<span><slot /></span>' },
          'el-divider': true,
          'el-scrollbar': { template: '<div><slot /></div>' },
          'el-button': { template: '<button><slot /></button>' },
        },
      },
    })

    await flushPromises()
    await flushPromises()
    await flushPromises()

    expect(wrapper.get('[data-testid="toolbar"]').text()).toContain('3|1|1|1|16')
    expect(wrapper.get('[data-testid="collector-table"]').text()).toContain('3|6,10,0')
    expect(wrapper.get('[data-testid="overview-card-summary"]').text()).toContain('已发布 1')
    expect(wrapper.get('[data-testid="overview-card-summary"]').text()).toContain('草稿 1')
    expect(wrapper.get('[data-testid="overview-card-summary"]').text()).toContain('冷却池 0')
    expect(wrapper.get('[data-testid="overview-card-run"]').text()).toContain('Gamma')
    expect(wrapper.get('[data-testid="overview-card-run"]').text()).toContain('失败')
    expect(wrapper.get('[data-testid="overview-card-run"]').text()).toContain('raw 9')
    expect(wrapper.get('[data-testid="overview-card-run"]').text()).toContain('duplicate 0')
    expect(wrapper.get('[data-testid="overview-card-worker"]').text()).toContain('运行中')
    expect(wrapper.get('[data-testid="overview-card-worker"]').text()).toContain('最近心跳')
  })

  it('应在概览中展示冷却池与冷却阻断指标', async () => {
    vi.mocked(collectorApi.getCollectors).mockResolvedValueOnce({
      data: {
        collectors: [
          {
            id: 'collector-a',
            name: 'Alpha',
            mode: 'simple',
            source: 'api',
            enabled: true,
            lifecycle: 'published',
            interval_seconds: 300,
            spec: {},
            code_ref: null,
          },
        ],
      },
    } as any)
    vi.mocked(collectorApi.getCollectorRuns).mockResolvedValueOnce({
      data: {
        runs: [
          {
            run_id: 'run-a',
            collector_id: 'collector-a',
            trigger: 'test',
            status: 'success',
            started_at: '2026-03-19T10:00:00',
            ended_at: '2026-03-19T10:01:00',
            duration_ms: 60000,
            metrics: {
              raw_count: 10,
              valid_count: 8,
              stored_count: 6,
              duplicate_count: 2,
              cooldown_blocked_count: 2,
            },
          },
        ],
      },
    } as any)

    const wrapper = shallowMount(CollectorManagerView, {
      global: {
        stubs: {
          CollectorToolbar: {
            props: ['workerSummary', 'overviewSummary'],
            template: '<div data-testid="cooldown-summary">cooldown-pool={{ overviewSummary ? (overviewSummary.cooldownPoolCount ?? 0) : "no-overview" }}</div>',
          },
          CollectorTable: {
            props: ['collectors'],
            template: '<div data-testid="collector-table">cooldown-blocked={{ collectors.map((row) => row.lastRun?.metrics?.cooldown_blocked_count ?? 0).join(",") }}</div>',
          },
          CollectorEditorDialog: true,
          CollectorRunHistoryDrawer: true,
          'el-skeleton': true,
          'el-dialog': { template: '<div><slot /></div>' },
          'el-tag': { template: '<span><slot /></span>' },
          'el-divider': true,
          'el-scrollbar': { template: '<div><slot /></div>' },
          'el-button': { template: '<button><slot /></button>' },
        },
      },
    })

    await flushPromises()
    await flushPromises()

    expect(wrapper.get('[data-testid="cooldown-summary"]').text()).toBe('cooldown-pool=0')

    collectorUpdateHandler?.({
      type: 'collector_update',
      data: {
        worker_summary: {
          status: 'running',
          activeJobs: 1,
          queueBacklog: 0,
          lastHeartbeat: '2026-03-19T10:05:00',
        },
        overview: {
          total: 1,
          published: 1,
          paused: 0,
          draft: 0,
          recentStoredCount: 6,
          successRate: 1,
          cooldownPoolCount: 1,
        },
        collectors: [
          {
            id: 'collector-a',
            last_run: {
              run_id: 'run-a',
              collector_id: 'collector-a',
              trigger: 'test',
              status: 'success',
              started_at: '2026-03-19T10:00:00',
              ended_at: '2026-03-19T10:01:00',
              duration_ms: 60000,
              metrics: {
                raw_count: 10,
                valid_count: 8,
                stored_count: 6,
                duplicate_count: 2,
                cooldown_blocked_count: 2,
              },
            },
          },
        ],
      },
    })

    await flushPromises()

    expect(wrapper.get('[data-testid="cooldown-summary"]').text()).toBe('cooldown-pool=1')
    expect(wrapper.get('[data-testid="collector-table"]').text()).toBe('cooldown-blocked=2')
    expect(wrapper.get('[data-testid="overview-card-summary"]').text()).toContain('冷却池 1')
  })

  it('应在初始加载完成后再订阅 collector_update 以避免旧快照覆盖新状态', async () => {
    const collectorsDeferred = createDeferred<any>()
    const runsDeferred = createDeferred<any>()

    vi.mocked(collectorApi.getCollectors).mockReturnValueOnce(collectorsDeferred.promise as any)
    vi.mocked(collectorApi.getCollectorRuns).mockReturnValueOnce(runsDeferred.promise as any)

    shallowMount(CollectorManagerView, {
      global: {
        stubs: {
          CollectorToolbar: true,
          CollectorTable: true,
          CollectorEditorDialog: true,
          CollectorRunHistoryDrawer: true,
          'el-skeleton': true,
          'el-dialog': { template: '<div><slot /></div>' },
          'el-tag': { template: '<span><slot /></span>' },
          'el-divider': true,
          'el-scrollbar': { template: '<div><slot /></div>' },
          'el-button': { template: '<button><slot /></button>' },
        },
      },
    })

    await flushPromises()

    const { dashboardRealtimeClient } = await import('@/services/realtime')
    expect(vi.mocked(dashboardRealtimeClient.subscribe)).not.toHaveBeenCalled()

    collectorsDeferred.resolve({
      data: {
        collectors: [
          {
            id: 'collector-a',
            name: 'Alpha',
            mode: 'simple',
            source: 'api',
            enabled: true,
            lifecycle: 'published',
            interval_seconds: 300,
            spec: {},
            code_ref: null,
          },
        ],
      },
    })
    await flushPromises()
    expect(vi.mocked(dashboardRealtimeClient.subscribe)).not.toHaveBeenCalled()

    runsDeferred.resolve({
      data: {
        runs: [],
      },
    })
    await flushPromises()

    expect(vi.mocked(dashboardRealtimeClient.subscribe)).toHaveBeenCalledWith(
      'collector_update',
      expect.any(Function),
    )
  })

  it('应以完整快照替换收集器列表并移除已删除项', async () => {
    const { dashboardRealtimeClient } = await import('@/services/realtime')

    const wrapper = shallowMount(CollectorManagerView, {
      global: {
        stubs: {
          CollectorToolbar: {
            props: ['workerSummary', 'overviewSummary'],
            template: '<div data-testid="toolbar">{{ workerSummary ? `${workerSummary.status}|${workerSummary.activeJobs}|${workerSummary.queueBacklog}` : "none" }}|{{ overviewSummary ? `${overviewSummary.total}|${overviewSummary.published}|${overviewSummary.paused}|${overviewSummary.draft}|${overviewSummary.recentStoredCount}` : "no-overview" }}</div>',
          },
          CollectorTable: {
            props: ['collectors'],
            template: '<div data-testid="collector-table">{{ collectors.length }}|{{ collectors.map((row) => row.id).join(",") }}|{{ collectors.map((row) => row.lastRun?.status ?? "none").join(",") }}</div>',
          },
          CollectorEditorDialog: true,
          CollectorRunHistoryDrawer: true,
          'el-skeleton': true,
          'el-dialog': { template: '<div><slot /></div>' },
          'el-tag': { template: '<span><slot /></span>' },
          'el-divider': true,
          'el-scrollbar': { template: '<div><slot /></div>' },
          'el-button': { template: '<button><slot /></button>' },
        },
      },
    })

    await flushPromises()
    await flushPromises()

    expect(vi.mocked(dashboardRealtimeClient.subscribe)).toHaveBeenCalledWith(
      'collector_update',
      expect.any(Function),
    )
    expect(collectorUpdateHandler).not.toBeNull()

    collectorUpdateHandler?.({
      type: 'collector_update',
      data: {
        worker_summary: {
          status: 'running',
          activeJobs: 2,
          queueBacklog: 4,
          lastHeartbeat: '2026-03-19T10:00:00',
        },
        overview: {
          total: 2,
          published: 1,
          paused: 1,
          draft: 0,
          recentStoredCount: 10,
          successRate: 0.5,
        },
        collectors: [
          {
            id: 'collector-a',
            last_run: {
              run_id: 'run-a',
              collector_id: 'collector-a',
              trigger: 'test',
              status: 'success',
              started_at: '2026-03-19T10:00:00',
              ended_at: '2026-03-19T10:01:00',
              duration_ms: 60000,
              metrics: {
                raw_count: 10,
                valid_count: 8,
                stored_count: 6,
                duplicate_count: 2,
              },
            },
          },
          {
            id: 'collector-b',
            last_run: {
              run_id: 'run-b',
              collector_id: 'collector-b',
              trigger: 'schedule',
              status: 'partial_success',
              started_at: '2026-03-19T10:00:00',
              ended_at: '2026-03-19T10:02:00',
              duration_ms: 120000,
              metrics: {
                raw_count: 12,
                valid_count: 11,
                stored_count: 4,
                duplicate_count: 1,
              },
            },
          },
        ],
      },
    })

    await flushPromises()

    expect(wrapper.get('[data-testid="toolbar"]').text()).toContain('running|2|4')
    expect(wrapper.get('[data-testid="toolbar"]').text()).toContain('2|1|1|0|10')
    expect(wrapper.get('[data-testid="collector-table"]').text()).toContain('2|collector-a,collector-b|success,partial_success')

    collectorUpdateHandler?.({
      type: 'collector_update',
      data: {
        worker_summary: {
          status: 'running',
          activeJobs: 1,
          queueBacklog: 2,
          lastHeartbeat: '2026-03-19T10:05:00',
        },
        overview: {
          total: 1,
          published: 1,
          paused: 0,
          draft: 0,
          recentStoredCount: 4,
          successRate: 1,
        },
        collectors: [
          {
            id: 'collector-b',
            last_run: {
              run_id: 'run-b2',
              collector_id: 'collector-b',
              trigger: 'schedule',
              status: 'success',
              started_at: '2026-03-19T10:05:00',
              ended_at: '2026-03-19T10:06:00',
              duration_ms: 60000,
              metrics: {
                raw_count: 8,
                valid_count: 7,
                stored_count: 4,
                duplicate_count: 1,
              },
            },
          },
        ],
      },
    })

    await flushPromises()

    expect(wrapper.get('[data-testid="collector-table"]').text()).toContain('1|collector-b|success')
    expect(wrapper.get('[data-testid="collector-table"]').text()).not.toContain('collector-a')
  })

  it('应在操作失败且期间收到实时快照时正确清理按钮 loading 状态', async () => {
    const testRunDeferred = createControlledPromise<any>()

    vi.mocked(collectorApi.getCollectors).mockResolvedValueOnce({
      data: {
        collectors: [
          {
            id: 'collector-a',
            name: 'Alpha',
            mode: 'simple',
            source: 'api',
            enabled: true,
            lifecycle: 'published',
            interval_seconds: 300,
            spec: {},
            code_ref: null,
          },
        ],
      },
    } as any)
    vi.mocked(collectorApi.getCollectorRuns).mockResolvedValueOnce({
      data: {
        runs: [],
      },
    } as any)
    vi.mocked(collectorApi.testRunCollector).mockReturnValueOnce(testRunDeferred.promise as any)

    const wrapper = shallowMount(CollectorManagerView, {
      global: {
        stubs: {
          CollectorToolbar: true,
          CollectorTable: {
            props: ['collectors'],
            template: `
              <div>
                <button data-testid="trigger-test-run" @click="$emit('test-run', collectors[0])">test</button>
                <div data-testid="loading-state">{{ collectors[0]?.actionLoading ? 'loading' : 'idle' }}</div>
              </div>
            `,
          },
          CollectorEditorDialog: true,
          CollectorRunHistoryDrawer: true,
          'el-skeleton': true,
          'el-dialog': { template: '<div><slot /></div>' },
          'el-tag': { template: '<span><slot /></span>' },
          'el-divider': true,
          'el-scrollbar': { template: '<div><slot /></div>' },
          'el-button': { template: '<button><slot /></button>' },
        },
      },
    })

    await flushPromises()
    await flushPromises()

    await wrapper.get('[data-testid="trigger-test-run"]').trigger('click')
    await flushPromises()
    expect(wrapper.get('[data-testid="loading-state"]').text()).toBe('loading')

    collectorUpdateHandler?.({
      type: 'collector_update',
      data: {
        worker_summary: {
          status: 'running',
          activeJobs: 1,
          queueBacklog: 0,
          lastHeartbeat: '2026-03-19T12:00:00',
        },
        overview: {
          total: 1,
          published: 1,
          paused: 0,
          draft: 0,
          recentStoredCount: 0,
          successRate: 0,
        },
        collectors: [
          {
            id: 'collector-a',
            name: 'Alpha',
            mode: 'simple',
            source: 'api',
            enabled: true,
            lifecycle: 'published',
            interval_seconds: 300,
            spec: {},
            code_ref: null,
            last_run: null,
          },
        ],
      },
    })
    await flushPromises()
    expect(wrapper.get('[data-testid="loading-state"]').text()).toBe('loading')

    testRunDeferred.reject({ response: { data: { detail: 'boom' } } })
    await flushPromises()
    await flushPromises()

    expect(vi.mocked(ElMessage.error)).toHaveBeenCalled()
    expect(wrapper.get('[data-testid="loading-state"]').text()).toBe('idle')
  })

  it('worker 心跳为空时应在仪表盘卡片中显示 N/A', async () => {
    const wrapper = shallowMount(CollectorManagerView, {
      global: {
        stubs: {
          CollectorToolbar: true,
          CollectorTable: true,
          CollectorEditorDialog: true,
          CollectorRunHistoryDrawer: true,
          'el-skeleton': true,
          'el-dialog': { template: '<div><slot /></div>' },
          'el-tag': { template: '<span><slot /></span>' },
          'el-divider': true,
          'el-scrollbar': { template: '<div><slot /></div>' },
          'el-button': { template: '<button><slot /></button>' },
        },
      },
    })

    await flushPromises()
    await flushPromises()

    collectorUpdateHandler?.({
      type: 'collector_update',
      data: {
        worker_summary: {
          status: 'running',
          activeJobs: 0,
          queueBacklog: 0,
          lastHeartbeat: '',
        },
        overview: {
          total: 0,
          published: 0,
          paused: 0,
          draft: 0,
          recentStoredCount: 0,
          successRate: 0,
        },
        collectors: [],
      },
    })

    await flushPromises()

    expect(wrapper.get('[data-testid="overview-card-worker"]').text()).toContain('最近心跳 N/A')
  })

  it('测试运行结果弹窗应展示冷却阻断指标', async () => {
    vi.mocked(collectorApi.getCollectors).mockResolvedValueOnce({
      data: {
        collectors: [
          {
            id: 'collector-a',
            name: 'Alpha',
            mode: 'simple',
            source: 'api',
            enabled: true,
            lifecycle: 'published',
            interval_seconds: 300,
            spec: {},
            code_ref: null,
          },
        ],
      },
    } as any)
    vi.mocked(collectorApi.getCollectorRuns).mockResolvedValueOnce({
      data: { runs: [] },
    } as any)
    vi.mocked(collectorApi.testRunCollector).mockResolvedValueOnce({
      data: {
        run_id: 'run-a',
        collector_id: 'collector-a',
        trigger: 'test',
        status: 'success',
        started_at: '2026-03-19T10:00:00',
        ended_at: '2026-03-19T10:01:00',
        duration_ms: 60000,
        metrics: {
          raw_count: 10,
          valid_count: 8,
          stored_count: 0,
          duplicate_count: 2,
          cooldown_blocked_count: 3,
        },
        error_details: [],
      },
    } as any)
    vi.mocked(collectorApi.getCollectors).mockResolvedValueOnce({
      data: {
        collectors: [
          {
            id: 'collector-a',
            name: 'Alpha',
            mode: 'simple',
            source: 'api',
            enabled: true,
            lifecycle: 'published',
            interval_seconds: 300,
            spec: {},
            code_ref: null,
          },
        ],
      },
    } as any)
    vi.mocked(collectorApi.getCollectorRuns).mockResolvedValueOnce({
      data: { runs: [] },
    } as any)

    const wrapper = shallowMount(CollectorManagerView, {
      global: {
        stubs: {
          CollectorToolbar: true,
          CollectorTable: {
            props: ['collectors'],
            template: '<button data-testid="trigger-test-run" @click="$emit(\'test-run\', collectors[0])">test</button>',
          },
          CollectorEditorDialog: true,
          CollectorRunHistoryDrawer: true,
          'el-skeleton': true,
          'el-dialog': { template: '<div><slot /></div>' },
          'el-tag': { template: '<span><slot /></span>' },
          'el-divider': true,
          'el-scrollbar': { template: '<div><slot /></div>' },
          'el-button': { template: '<button @click="$emit(\'click\')"><slot /></button>' },
        },
      },
    })

    await flushPromises()
    await flushPromises()

    await wrapper.get('[data-testid="trigger-test-run"]').trigger('click')
    await flushPromises()
    await flushPromises()

    expect(wrapper.text()).toContain('冷却阻断')
    expect(wrapper.text()).toContain('3')
  })

  it('本地刷新收集器列表时应保留已有的冷却池计数', async () => {
    vi.mocked(collectorApi.getCollectors).mockResolvedValueOnce({
      data: {
        collectors: [
          {
            id: 'collector-a',
            name: 'Alpha',
            mode: 'simple',
            source: 'api',
            enabled: true,
            lifecycle: 'published',
            interval_seconds: 300,
            spec: {},
            code_ref: null,
          },
        ],
      },
    } as any)
    vi.mocked(collectorApi.getCollectorRuns).mockResolvedValueOnce({
      data: {
        runs: [
          {
            run_id: 'run-a0',
            collector_id: 'collector-a',
            trigger: 'schedule',
            status: 'success',
            started_at: '2026-03-19T09:00:00',
            ended_at: '2026-03-19T09:01:00',
            duration_ms: 60000,
            metrics: {
              raw_count: 5,
              valid_count: 5,
              stored_count: 2,
              duplicate_count: 1,
              cooldown_blocked_count: 0,
            },
          },
        ],
      },
    } as any)
    vi.mocked(collectorApi.testRunCollector).mockResolvedValueOnce({
      data: {
        run_id: 'run-a1',
        collector_id: 'collector-a',
        trigger: 'test',
        status: 'success',
        started_at: '2026-03-19T10:00:00',
        ended_at: '2026-03-19T10:01:00',
        duration_ms: 60000,
        metrics: {
          raw_count: 6,
          valid_count: 6,
          stored_count: 3,
          duplicate_count: 0,
          cooldown_blocked_count: 0,
        },
        error_details: [],
      },
    } as any)
    vi.mocked(collectorApi.getCollectors).mockResolvedValueOnce({
      data: {
        collectors: [
          {
            id: 'collector-a',
            name: 'Alpha',
            mode: 'simple',
            source: 'api',
            enabled: true,
            lifecycle: 'published',
            interval_seconds: 300,
            spec: {},
            code_ref: null,
          },
        ],
      },
    } as any)
    vi.mocked(collectorApi.getCollectorRuns).mockResolvedValueOnce({
      data: {
        runs: [
          {
            run_id: 'run-a1',
            collector_id: 'collector-a',
            trigger: 'test',
            status: 'success',
            started_at: '2026-03-19T10:00:00',
            ended_at: '2026-03-19T10:01:00',
            duration_ms: 60000,
            metrics: {
              raw_count: 6,
              valid_count: 6,
              stored_count: 3,
              duplicate_count: 0,
              cooldown_blocked_count: 0,
            },
          },
        ],
      },
    } as any)

    const wrapper = shallowMount(CollectorManagerView, {
      global: {
        stubs: {
          CollectorToolbar: {
            props: ['overviewSummary'],
            template: '<div data-testid="cooldown-summary">{{ overviewSummary ? overviewSummary.cooldownPoolCount : "no-overview" }}</div>',
          },
          CollectorTable: {
            props: ['collectors'],
            template: '<button data-testid="trigger-test-run" @click="$emit(\'test-run\', collectors[0])">test</button>',
          },
          CollectorEditorDialog: true,
          CollectorRunHistoryDrawer: true,
          'el-skeleton': true,
          'el-dialog': { template: '<div><slot /></div>' },
          'el-tag': { template: '<span><slot /></span>' },
          'el-divider': true,
          'el-scrollbar': { template: '<div><slot /></div>' },
          'el-button': { template: '<button @click="$emit(\'click\')"><slot /></button>' },
        },
      },
    })

    await flushPromises()
    await flushPromises()

    collectorUpdateHandler?.({
      type: 'collector_update',
      data: {
        worker_summary: {
          status: 'running',
          activeJobs: 0,
          queueBacklog: 0,
          lastHeartbeat: '2026-03-19T10:05:00',
        },
        overview: {
          total: 1,
          published: 1,
          paused: 0,
          draft: 0,
          recentStoredCount: 2,
          successRate: 1,
          cooldownPoolCount: 5,
        },
        collectors: [
          {
            id: 'collector-a',
            name: 'Alpha',
            mode: 'simple',
            source: 'api',
            enabled: true,
            lifecycle: 'published',
            interval_seconds: 300,
            spec: {},
            code_ref: null,
            last_run: {
              run_id: 'run-a0',
              collector_id: 'collector-a',
              trigger: 'schedule',
              status: 'success',
              started_at: '2026-03-19T09:00:00',
              ended_at: '2026-03-19T09:01:00',
              duration_ms: 60000,
              metrics: {
                raw_count: 5,
                valid_count: 5,
                stored_count: 2,
                duplicate_count: 1,
                cooldown_blocked_count: 0,
              },
            },
          },
        ],
      },
    })
    await flushPromises()
    expect(wrapper.get('[data-testid="cooldown-summary"]').text()).toBe('5')

    await wrapper.get('[data-testid="trigger-test-run"]').trigger('click')
    await flushPromises()
    await flushPromises()

    expect(wrapper.get('[data-testid="cooldown-summary"]').text()).toBe('5')
  })

  it('应保留 worker 的 unset 状态而不是降级为 stopped', async () => {
    const { getModuleStatus } = await import('../api/apiClient')
    vi.mocked(getModuleStatus).mockResolvedValueOnce([
      {
        moduleName: 'Collector Worker',
        status: 'Unset',
        lastHeartbeat: '2026-03-09T18:12:00',
        performance: {
          active_jobs: 0,
          queue_backlog: 0,
        },
      },
    ] as any)

    const wrapper = shallowMount(CollectorManagerView, {
      global: {
        stubs: {
          CollectorToolbar: {
            props: ['workerSummary'],
            template: '<div data-testid="toolbar">{{ workerSummary ? workerSummary.status : "none" }}</div>',
          },
          CollectorTable: true,
          CollectorEditorDialog: true,
          CollectorRunHistoryDrawer: true,
          'el-skeleton': true,
          'el-dialog': { template: '<div><slot /></div>' },
          'el-tag': { template: '<span><slot /></span>' },
          'el-divider': true,
          'el-scrollbar': { template: '<div><slot /></div>' },
          'el-button': { template: '<button><slot /></button>' },
        },
      },
    })

    await flushPromises()
    await flushPromises()

    expect(wrapper.get('[data-testid="toolbar"]').text()).toContain('unset')
  })

  it('应在创建时拦截非法格式的收集器名称', async () => {
    const wrapper = shallowMount(CollectorManagerView, {
      global: {
        stubs: {
          CollectorToolbar: true,
          CollectorTable: true,
          CollectorEditorDialog: {
            props: ['form', 'submitDisabled', 'nameError'],
            template: `
              <div>
                <input data-testid="name-input" v-model="form.name" />
                <div data-testid="name-error">{{ nameError }}</div>
                <button data-testid="submit-button" :disabled="submitDisabled" @click="$emit('submit')">submit</button>
                <button data-testid="force-submit-button" @click="$emit('submit')">force-submit</button>
              </div>
            `,
          },
          CollectorRunHistoryDrawer: true,
          'el-skeleton': true,
          'el-dialog': { template: '<div><slot /></div>' },
          'el-tag': { template: '<span><slot /></span>' },
          'el-divider': true,
          'el-scrollbar': { template: '<div><slot /></div>' },
          'el-button': { template: '<button><slot /></button>' },
        },
      },
    })

    await flushPromises()
    await wrapper.get('[data-testid="name-input"]').setValue('站大爷海外代理')
    expect(wrapper.get('[data-testid="name-error"]').text()).toContain('仅允许')
    expect(wrapper.get('[data-testid="submit-button"]').attributes('disabled')).toBeDefined()

    await wrapper.get('[data-testid="force-submit-button"]').trigger('click')
    expect(vi.mocked(collectorApi.createCollector)).not.toHaveBeenCalled()
    expect(vi.mocked(ElMessage.warning)).toHaveBeenCalled()
  })

  it('应将简单模式结构化表单转换为 spec 后再创建收集器', async () => {
    vi.mocked(collectorApi.createCollector).mockResolvedValueOnce({
      data: {
        id: 'simple_demo',
      },
    } as any)

    const wrapper = shallowMount(CollectorManagerView, {
      global: {
        stubs: {
          CollectorToolbar: true,
          CollectorTable: true,
          CollectorEditorDialog: {
            props: ['title', 'form'],
            template: `
              <div v-if="title === '新建收集器'">
                <input data-testid="name-input" v-model="form.name" />
                <input data-testid="request-url-input" v-model="form.simpleRequestUrl" />
                <input data-testid="extract-expression-input" v-model="form.simpleExtractExpression" />
                <input data-testid="ip-mapping-input" v-model="form.simpleIpField" />
                <input data-testid="port-mapping-input" v-model="form.simplePortField" />
                <input data-testid="protocol-mapping-input" v-model="form.simpleProtocolField" />
                <input data-testid="country-value-input" v-model="form.simpleCountryValue" />
                <input data-testid="country-default-input" v-model="form.simpleCountryDefault" />
                <input data-testid="anonymity-mapping-input" v-model="form.simpleAnonymityField" />
                <select data-testid="request-method-select" v-model="form.simpleRequestMethod">
                  <option value="GET">GET</option>
                  <option value="POST">POST</option>
                </select>
                <select data-testid="extract-type-select" v-model="form.simpleExtractType">
                  <option value="jsonpath">jsonpath</option>
                  <option value="css">css</option>
                </select>
                <select data-testid="country-mode-select" v-model="form.simpleCountryMode">
                  <option value="transform">transform</option>
                  <option value="const">const</option>
                  <option value="field">field</option>
                </select>
                <button data-testid="submit-button" @click="$emit('submit')">submit</button>
              </div>
            `,
          },
          CollectorRunHistoryDrawer: true,
          'el-skeleton': true,
          'el-dialog': { template: '<div><slot /></div>' },
          'el-tag': { template: '<span><slot /></span>' },
          'el-divider': true,
          'el-scrollbar': { template: '<div><slot /></div>' },
          'el-button': { template: '<button><slot /></button>' },
        },
      },
    })

    await flushPromises()
    await flushPromises()

    await wrapper.get('[data-testid="name-input"]').setValue('simple_demo')
    await wrapper.get('[data-testid="request-url-input"]').setValue('https://example.com/api/proxies')
    await wrapper.get('[data-testid="request-method-select"]').setValue('POST')
    await wrapper.get('[data-testid="extract-type-select"]').setValue('jsonpath')
    await wrapper.get('[data-testid="extract-expression-input"]').setValue('$.data.proxy_list[*]')
    await wrapper.get('[data-testid="ip-mapping-input"]').setValue('ip')
    await wrapper.get('[data-testid="port-mapping-input"]').setValue('port')
    await wrapper.get('[data-testid="protocol-mapping-input"]').setValue('protocol')
    await wrapper.get('[data-testid="country-mode-select"]').setValue('transform')
    await wrapper.get('[data-testid="country-value-input"]').setValue('adr')
    await wrapper.get('[data-testid="country-default-input"]').setValue('Unknown')
    await wrapper.get('[data-testid="anonymity-mapping-input"]').setValue('level')
    await wrapper.get('[data-testid="submit-button"]').trigger('click')

    expect(vi.mocked(collectorApi.createCollector)).toHaveBeenCalledWith({
      name: 'simple_demo',
      mode: 'simple',
      source: 'api',
      enabled: true,
      interval_seconds: 300,
      spec: {
        request: {
          url: 'https://example.com/api/proxies',
          method: 'POST',
          timeout_seconds: 10,
        },
        extract: {
          type: 'jsonpath',
          expression: '$.data.proxy_list[*]',
        },
        field_mapping: {
          ip: 'ip',
          port: 'port',
          protocol: 'protocol',
          country_code: {
            expression: 'adr',
            transform: 'country_text_to_code',
            default: 'Unknown',
          },
          anonymity_level: 'level',
        },
      },
      code_ref: null,
      env_vars: {},
    })
  })

  it('应为简单模式的 scrape 收集器生成 pagination 配置', async () => {
    vi.mocked(collectorApi.createCollector).mockResolvedValueOnce({
      data: {
        id: 'scrape_demo',
      },
    } as any)

    const wrapper = shallowMount(CollectorManagerView, {
      global: {
        stubs: {
          CollectorToolbar: true,
          CollectorTable: true,
          CollectorEditorDialog: {
            props: ['title', 'form'],
            template: `
              <div v-if="title === '新建收集器'">
                <input data-testid="name-input" v-model="form.name" />
                <select data-testid="source-select" v-model="form.source">
                  <option value="api">api</option>
                  <option value="scrape">scrape</option>
                </select>
                <input data-testid="request-url-input" v-model="form.simpleRequestUrl" />
                <select data-testid="extract-type-select" v-model="form.simpleExtractType">
                  <option value="css">css</option>
                  <option value="xpath">xpath</option>
                </select>
                <input data-testid="extract-expression-input" v-model="form.simpleExtractExpression" />
                <input data-testid="ip-mapping-input" v-model="form.simpleIpField" />
                <input data-testid="port-mapping-input" v-model="form.simplePortField" />
                <input data-testid="pagination-enabled-input" type="checkbox" v-model="form.simplePaginationEnabled" />
                <input data-testid="pagination-page-param-input" v-model="form.simplePaginationPageParam" />
                <input data-testid="pagination-start-page-input" v-model="form.simplePaginationStartPage" />
                <input data-testid="pagination-max-pages-input" v-model="form.simplePaginationMaxPages" />
                <input data-testid="pagination-stop-when-empty-input" type="checkbox" v-model="form.simplePaginationStopWhenEmpty" />
                <button data-testid="submit-button" @click="$emit('submit')">submit</button>
              </div>
            `,
          },
          CollectorRunHistoryDrawer: true,
          'el-skeleton': true,
          'el-dialog': { template: '<div><slot /></div>' },
          'el-tag': { template: '<span><slot /></span>' },
          'el-divider': true,
          'el-scrollbar': { template: '<div><slot /></div>' },
          'el-button': { template: '<button><slot /></button>' },
        },
      },
    })

    await flushPromises()
    await flushPromises()

    await wrapper.get('[data-testid="name-input"]').setValue('scrape_demo')
    await wrapper.get('[data-testid="source-select"]').setValue('scrape')
    await wrapper.get('[data-testid="request-url-input"]').setValue('https://example.com/list')
    await wrapper.get('[data-testid="extract-type-select"]').setValue('css')
    await wrapper.get('[data-testid="extract-expression-input"]').setValue('.proxy-row')
    await wrapper.get('[data-testid="ip-mapping-input"]').setValue('.ip::text')
    await wrapper.get('[data-testid="port-mapping-input"]').setValue('.port::text')
    await wrapper.get('[data-testid="pagination-enabled-input"]').setValue(true)
    await wrapper.get('[data-testid="pagination-page-param-input"]').setValue('page')
    await wrapper.get('[data-testid="pagination-start-page-input"]').setValue('2')
    await wrapper.get('[data-testid="pagination-max-pages-input"]').setValue('8')
    await wrapper.get('[data-testid="pagination-stop-when-empty-input"]').setValue(true)
    await wrapper.get('[data-testid="submit-button"]').trigger('click')

    expect(vi.mocked(collectorApi.createCollector)).toHaveBeenCalledWith({
      name: 'scrape_demo',
      mode: 'simple',
      source: 'scrape',
      enabled: true,
      interval_seconds: 300,
      spec: {
        request: {
          url: 'https://example.com/list',
          method: 'GET',
          timeout_seconds: 10,
        },
        extract: {
          type: 'css',
          expression: '.proxy-row',
        },
        field_mapping: {
          ip: '.ip::text',
          port: '.port::text',
        },
        pagination: {
          page_param: 'page',
          start_page: 2,
          max_pages: 8,
          stop_when_empty: true,
        },
      },
      code_ref: null,
      env_vars: {},
    })
  })

  it('编辑已有 scrape simple 收集器时应回填 pagination 表单字段', async () => {
    vi.mocked(collectorApi.getCollectors).mockResolvedValueOnce({
      data: {
        collectors: [
          {
            id: 'scrape_demo',
            name: 'Scrape Demo',
            mode: 'simple',
            source: 'scrape',
            enabled: true,
            lifecycle: 'draft',
            interval_seconds: 300,
            spec: {
              request: {
                url: 'https://example.com/list',
                method: 'GET',
                timeout_seconds: 10,
              },
              extract: {
                type: 'css',
                expression: '.proxy-row',
              },
              field_mapping: {
                ip: '.ip::text',
                port: '.port::text',
              },
              pagination: {
                page_param: 'page',
                start_page: 2,
                max_pages: 8,
                stop_when_empty: true,
              },
            },
            code_ref: null,
          },
        ],
      },
    } as any)
    vi.mocked(collectorApi.getCollectorRuns).mockResolvedValueOnce({
      data: { runs: [] },
    } as any)

    const wrapper = shallowMount(CollectorManagerView, {
      global: {
        stubs: {
          CollectorToolbar: true,
          CollectorTable: {
            props: ['collectors'],
            template: '<button data-testid="edit-button" @click="$emit(\'edit\', collectors[0])">edit</button>',
          },
          CollectorEditorDialog: {
            props: ['title', 'form'],
            template: `
              <div v-if="title === '编辑收集器'">
                <div data-testid="pagination-enabled">{{ form.simplePaginationEnabled ? 'yes' : 'no' }}</div>
                <div data-testid="pagination-page-param">{{ form.simplePaginationPageParam }}</div>
                <div data-testid="pagination-start-page">{{ form.simplePaginationStartPage }}</div>
                <div data-testid="pagination-max-pages">{{ form.simplePaginationMaxPages }}</div>
                <div data-testid="pagination-stop-when-empty">{{ form.simplePaginationStopWhenEmpty ? 'yes' : 'no' }}</div>
              </div>
            `,
          },
          CollectorRunHistoryDrawer: true,
          'el-skeleton': true,
          'el-dialog': { template: '<div><slot /></div>' },
          'el-tag': { template: '<span><slot /></span>' },
          'el-divider': true,
          'el-scrollbar': { template: '<div><slot /></div>' },
          'el-button': { template: '<button><slot /></button>' },
        },
      },
    })

    await flushPromises()
    await flushPromises()

    await wrapper.get('[data-testid="edit-button"]').trigger('click')

    expect(wrapper.get('[data-testid="pagination-enabled"]').text()).toBe('yes')
    expect(wrapper.get('[data-testid="pagination-page-param"]').text()).toBe('page')
    expect(wrapper.get('[data-testid="pagination-start-page"]').text()).toBe('2')
    expect(wrapper.get('[data-testid="pagination-max-pages"]').text()).toBe('8')
    expect(wrapper.get('[data-testid="pagination-stop-when-empty"]').text()).toBe('yes')
  })

  it('专家模式 JSON 非法时应禁用提交并阻止创建', async () => {
    const wrapper = shallowMount(CollectorManagerView, {
      global: {
        stubs: {
          CollectorToolbar: true,
          CollectorTable: true,
          CollectorEditorDialog: {
            props: ['title', 'form', 'submitDisabled', 'specError', 'codeRefError'],
            template: `
              <div v-if="title === '新建收集器'">
                <input data-testid="name-input" v-model="form.name" />
                <textarea data-testid="spec-input" v-model="form.specText"></textarea>
                <textarea data-testid="code-ref-input" v-model="form.codeRefText"></textarea>
                <div data-testid="spec-error">{{ specError }}</div>
                <div data-testid="code-ref-error">{{ codeRefError }}</div>
                <div data-testid="submit-disabled">{{ submitDisabled ? 'yes' : 'no' }}</div>
                <button data-testid="submit-button" @click="$emit('submit')">submit</button>
              </div>
            `,
          },
          CollectorRunHistoryDrawer: true,
          'el-skeleton': true,
          'el-dialog': { template: '<div><slot /></div>' },
          'el-tag': { template: '<span><slot /></span>' },
          'el-divider': true,
          'el-scrollbar': { template: '<div><slot /></div>' },
          'el-button': { template: '<button><slot /></button>' },
        },
      },
    })

    await flushPromises()
    await flushPromises()

    await wrapper.get('[data-testid="name-input"]').setValue('expert_demo')
    ;(wrapper.vm as any).createForm.mode = 'code'
    await wrapper.get('[data-testid="spec-input"]').setValue('{"request": }')
    await wrapper.get('[data-testid="code-ref-input"]').setValue('{"filename": }')
    await flushPromises()

    expect(wrapper.get('[data-testid="spec-error"]').text()).toContain('Spec JSON 解析失败')
    expect(wrapper.get('[data-testid="code-ref-error"]').text()).toContain('CodeRef JSON 解析失败')
    expect(wrapper.get('[data-testid="submit-disabled"]').text()).toBe('yes')

    await wrapper.get('[data-testid="submit-button"]').trigger('click')
    expect(vi.mocked(collectorApi.createCollector)).not.toHaveBeenCalled()
  })
})
