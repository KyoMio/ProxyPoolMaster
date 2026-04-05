export type CollectorMode = 'simple' | 'code'
export type CollectorLifecycle = 'draft' | 'published' | 'paused'
export type CollectorSource = 'api' | 'scrape'
export type CollectorRunStatus = 'success' | 'partial_success' | 'failed' | 'timeout'

export interface CollectorRunRecord {
  run_id: string
  collector_id: string
  trigger: 'schedule' | 'manual' | 'test'
  status: CollectorRunStatus
  started_at: string
  ended_at: string
  duration_ms: number
  metrics: {
    raw_count: number
    valid_count: number
    stored_count: number
    duplicate_count: number
    cooldown_blocked_count: number
  }
  error_summary?: string | null
  error_details?: string[]
}

export interface CollectorV2 {
  id: string
  name: string
  mode: CollectorMode
  source: CollectorSource
  enabled: boolean
  lifecycle: CollectorLifecycle
  interval_seconds: number
  spec: Record<string, any>
  code_ref?: Record<string, any> | null
  env_vars?: Record<string, { value: string; is_secret: boolean }>
  meta?: {
    created_at?: string
    updated_at?: string
    version?: number
  }
  runs?: CollectorRunRecord[]
}

export interface CollectorV2CreateRequest {
  id?: string
  name: string
  mode: CollectorMode
  source: CollectorSource
  enabled: boolean
  interval_seconds: number
  spec: Record<string, any>
  code_ref?: Record<string, any> | null
  env_vars?: Record<string, { value: string; is_secret: boolean }>
}

export interface CollectorV2UpdateRequest {
  name?: string
  enabled?: boolean
  interval_seconds?: number
  spec?: Record<string, any>
  code_ref?: Record<string, any> | null
  env_vars?: Record<string, { value: string; is_secret: boolean }>
}

export interface CollectorWorkerSummary {
  status: 'running' | 'degraded' | 'stopped' | 'unset'
  activeJobs: number
  queueBacklog: number
  lastHeartbeat: string
}

export interface CollectorOverviewSummary {
  total: number
  published: number
  paused: number
  draft: number
  recentStoredCount: number
  successRate: number
  cooldownPoolCount: number
}

export interface CollectorRealtimeItem extends Partial<CollectorV2> {
  id: string
  last_run?: CollectorRunRecord | null
  lastRun?: CollectorRunRecord | null
}

export interface CollectorRealtimeUpdatePayload {
  worker_summary?: CollectorWorkerSummary | null
  overview?: CollectorOverviewSummary | null
  collectors?: CollectorRealtimeItem[]
}
