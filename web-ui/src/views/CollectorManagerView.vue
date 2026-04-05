<template>
  <div class="collector-manager">
    <section v-if="showDashboard" class="collector-overview" aria-label="收集器仪表盘">
      <div
        v-for="card in dashboardCards"
        :key="card.key"
        :class="['overview-card', `overview-card--${card.key}`]"
        :data-testid="`overview-card-${card.key}`"
      >
        <div class="overview-card__label">{{ card.title }}</div>
        <div class="overview-card__value">{{ card.value }}</div>
        <div v-if="card.subtitle" class="overview-card__subtitle">{{ card.subtitle }}</div>
        <div v-if="card.details?.length" class="overview-card__details">
          <span v-for="detail in card.details" :key="detail" class="overview-card__detail">{{ detail }}</span>
        </div>
        <div v-if="card.metrics?.length" class="overview-card__metrics">
          <span v-for="metric in card.metrics" :key="metric" class="overview-card__metric">{{ metric }}</span>
        </div>
      </div>
    </section>

    <CollectorToolbar :worker-summary="workerSummary" :overview-summary="overviewSummary" @create="openCreateDialog" />

    <el-skeleton v-if="loading" :rows="5" animated />

    <CollectorTable
      v-else
      :collectors="collectors"
      @edit="openEditDialog"
      @test-run="handleTestRun"
      @show-runs="openRunHistory"
      @publish="handlePublish"
      @pause="handlePause"
      @resume="handleResume"
      @delete="handleDelete"
    />

    <CollectorEditorDialog
      v-model:visible="createDialogVisible"
      title="新建收集器"
      :loading="creating"
      submit-text="创建"
      :name-hint="collectorNameHint"
      :name-error="createNameError"
      :spec-error="createSpecError"
      :code-ref-error="createCodeRefError"
      :submit-disabled="Boolean(createNameError || createSpecError || createCodeRefError)"
      :show-mode-source="true"
      :show-enabled="false"
      :form="createForm"
      @submit="handleCreate"
    />

    <CollectorEditorDialog
      v-model:visible="editDialogVisible"
      title="编辑收集器"
      :loading="saving"
      submit-text="保存"
      :name-hint="collectorNameHint"
      :name-error="editNameError"
      :spec-error="editSpecError"
      :code-ref-error="editCodeRefError"
      :submit-disabled="Boolean(editNameError || editSpecError || editCodeRefError)"
      :show-id="true"
      :show-mode-source="false"
      :show-enabled="true"
      :form="editForm"
      @submit="handleSave"
    />

    <el-dialog v-model="reportDialogVisible" title="测试运行结果" width="680px">
      <div v-if="currentRunRecord">
        <p>
          状态：
          <el-tag :type="runTagType(currentRunRecord.status)">{{ runText(currentRunRecord.status) }}</el-tag>
        </p>
        <p>开始时间：{{ formatTime(currentRunRecord.started_at) }}</p>
        <p>结束时间：{{ formatTime(currentRunRecord.ended_at) }}</p>
        <p>耗时：{{ currentRunRecord.duration_ms }}ms</p>

        <el-divider />
        <p>raw: {{ currentRunRecord.metrics.raw_count }}</p>
        <p>valid: {{ currentRunRecord.metrics.valid_count }}</p>
        <p>stored: {{ currentRunRecord.metrics.stored_count }}</p>
        <p>duplicate: {{ currentRunRecord.metrics.duplicate_count }}</p>
        <p>冷却阻断: {{ currentRunRecord.metrics.cooldown_blocked_count ?? 0 }}</p>

        <template v-if="currentRunRecord.error_details?.length">
          <el-divider />
          <h4>错误详情</h4>
          <el-scrollbar max-height="180px">
            <ul class="error-list">
              <li v-for="(err, index) in currentRunRecord.error_details" :key="index">{{ err }}</li>
            </ul>
          </el-scrollbar>
        </template>
        <el-divider />
        <el-button type="primary" @click="goToLogView(currentRunRecord.collector_id, currentRunRecord.run_id)">
          查看该次运行日志
        </el-button>
      </div>
    </el-dialog>

    <CollectorRunHistoryDrawer
      v-model:visible="runHistoryDrawerVisible"
      :loading="runHistoryLoading"
      :collector-name="currentHistoryCollectorName"
      :runs="runHistory"
      @view-log="goToLogView"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useRouter } from 'vue-router'
import { collectorApi, getModuleStatus } from '../api/apiClient'
import CollectorRunHistoryDrawer from '../components/collectors/CollectorRunHistoryDrawer.vue'
import CollectorTable from '../components/collectors/CollectorTable.vue'
import CollectorEditorDialog from '../components/collectors/CollectorEditorDialog.vue'
import CollectorToolbar from '../components/collectors/CollectorToolbar.vue'
import { dashboardRealtimeClient } from '@/services/realtime'
import { COLLECTOR_NAME_RULE_HINT, validateCollectorName } from '../utils/collectorName'
import type {
  CollectorRunRecord,
  CollectorRunStatus,
  CollectorOverviewSummary,
  CollectorRealtimeItem,
  CollectorRealtimeUpdatePayload,
  CollectorV2,
  CollectorWorkerSummary,
} from '../types/collector'

interface CollectorRow extends CollectorV2 {
  actionLoading?: boolean
  lastRun?: CollectorRunRecord | null
}

type CollectorModeForm = 'simple' | 'code'
type CollectorSourceForm = 'api' | 'scrape'
type SimpleExtractType = 'jsonpath' | 'css' | 'xpath'
type SimpleCountryMode = 'none' | 'const' | 'field' | 'transform'

interface SimpleFormState {
  simpleRequestUrl: string
  simpleRequestMethod: 'GET' | 'POST'
  simpleRequestTimeoutSeconds: number
  simpleRequestParamsText: string
  simpleRequestHeadersText: string
  simpleRequestDataText: string
  simpleRequestJsonText: string
  simpleExtractType: SimpleExtractType
  simpleExtractExpression: string
  simpleIpField: string
  simplePortField: string
  simpleProtocolField: string
  simpleCountryMode: SimpleCountryMode
  simpleCountryValue: string
  simpleCountryDefault: string
  simpleAnonymityField: string
  simplePaginationEnabled: boolean
  simplePaginationPageParam: string
  simplePaginationStartPage: number
  simplePaginationMaxPages: number
  simplePaginationStopWhenEmpty: boolean
  simpleExtraSpec: Record<string, any>
  simpleExtraRequest: Record<string, any>
  simpleExtraExtract: Record<string, any>
  simpleExtraFieldMapping: Record<string, any>
  simpleExtraPagination: Record<string, any>
}

type CollectorEditorFormState = {
  id?: string
  name: string
  mode: CollectorModeForm
  source: CollectorSourceForm
  enabled: boolean
  interval_seconds: number
  specText: string
  codeRefText: string
} & SimpleFormState

const SIMPLE_SPEC_TEMPLATE = '{\n  "request": {},\n  "extract": {},\n  "field_mapping": {}\n}'

const buildDefaultSimpleFormState = (): SimpleFormState => ({
  simpleRequestUrl: '',
  simpleRequestMethod: 'GET',
  simpleRequestTimeoutSeconds: 10,
  simpleRequestParamsText: '',
  simpleRequestHeadersText: '',
  simpleRequestDataText: '',
  simpleRequestJsonText: '',
  simpleExtractType: 'jsonpath',
  simpleExtractExpression: '',
  simpleIpField: '',
  simplePortField: '',
  simpleProtocolField: '',
  simpleCountryMode: 'none',
  simpleCountryValue: '',
  simpleCountryDefault: '',
  simpleAnonymityField: '',
  simplePaginationEnabled: false,
  simplePaginationPageParam: 'page',
  simplePaginationStartPage: 1,
  simplePaginationMaxPages: 5,
  simplePaginationStopWhenEmpty: false,
  simpleExtraSpec: {},
  simpleExtraRequest: {},
  simpleExtraExtract: {},
  simpleExtraFieldMapping: {},
  simpleExtraPagination: {},
})

const buildCreateFormState = (): CollectorEditorFormState => ({
  name: '',
  mode: 'simple',
  source: 'api',
  enabled: true,
  interval_seconds: 300,
  specText: SIMPLE_SPEC_TEMPLATE,
  codeRefText: '{\n  "filename": "custom_collector.py"\n}',
  ...buildDefaultSimpleFormState(),
})

const buildEditFormState = (): CollectorEditorFormState => ({
  id: '',
  name: '',
  mode: 'simple',
  source: 'api',
  enabled: true,
  interval_seconds: 300,
  specText: '{}',
  codeRefText: '{}',
  ...buildDefaultSimpleFormState(),
})

const loading = ref(false)
const collectors = ref<CollectorRow[]>([])
const workerSummary = ref<CollectorWorkerSummary | null>(null)
const overviewSummary = ref<CollectorOverviewSummary | null>(null)
const router = useRouter()

const createDialogVisible = ref(false)
const creating = ref(false)
const createForm = reactive<CollectorEditorFormState>(buildCreateFormState())

const editDialogVisible = ref(false)
const saving = ref(false)
const editForm = reactive<CollectorEditorFormState>(buildEditFormState())

const reportDialogVisible = ref(false)
const currentRunRecord = ref<CollectorRunRecord | null>(null)
const runHistoryDrawerVisible = ref(false)
const runHistoryLoading = ref(false)
const runHistory = ref<CollectorRunRecord[]>([])
const currentHistoryCollectorName = ref('')
const collectorNameHint = COLLECTOR_NAME_RULE_HINT
const createNameError = computed(() => validateCollectorName(createForm.name))
const editNameError = computed(() => validateCollectorName(editForm.name))
const showDashboard = computed(() => !loading.value || collectors.value.length > 0 || Boolean(workerSummary.value) || Boolean(overviewSummary.value))

const parseJsonText = (value: string, fieldName: string): Record<string, any> => {
  try {
    if (!value.trim()) return {}
    const parsed = JSON.parse(value)
    if (parsed && typeof parsed === 'object') {
      return parsed as Record<string, any>
    }
    throw new Error(`${fieldName} 必须是对象`) 
  } catch (error: any) {
    throw new Error(`${fieldName} JSON 解析失败: ${error.message}`)
  }
}

const parseOptionalJsonText = (value: string, fieldName: string): Record<string, any> | undefined => {
  if (!value.trim()) {
    return undefined
  }
  return parseJsonText(value, fieldName)
}

const validateJsonObjectText = (value: string, fieldName: string): string | null => {
  try {
    parseJsonText(value, fieldName)
    return null
  } catch (error: any) {
    return error.message
  }
}

const serializeJsonText = (value: unknown): string => {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return ''
  }
  return JSON.stringify(value, null, 2)
}

const resolveMappingExpression = (rule: unknown): string => {
  if (typeof rule === 'string') {
    return rule
  }
  if (rule && typeof rule === 'object') {
    const candidate = (rule as Record<string, any>).expression ?? (rule as Record<string, any>).path ?? (rule as Record<string, any>).selector ?? ''
    return String(candidate || '')
  }
  return ''
}

const applySimpleSpecToForm = (target: CollectorEditorFormState, spec: Record<string, any>) => {
  const defaultState = buildDefaultSimpleFormState()
  const requestSpec = spec?.request && typeof spec.request === 'object' && !Array.isArray(spec.request) ? { ...spec.request } : {}
  const extractSpec = spec?.extract && typeof spec.extract === 'object' && !Array.isArray(spec.extract) ? { ...spec.extract } : {}
  const fieldMapping = spec?.field_mapping && typeof spec.field_mapping === 'object' && !Array.isArray(spec.field_mapping) ? { ...spec.field_mapping } : {}
  const paginationSpec = spec?.pagination && typeof spec.pagination === 'object' && !Array.isArray(spec.pagination) ? { ...spec.pagination } : {}
  const extraSpec = { ...(spec || {}) }

  delete extraSpec.request
  delete extraSpec.extract
  delete extraSpec.field_mapping
  delete extraSpec.pagination

  target.simpleRequestUrl = String(requestSpec.url || defaultState.simpleRequestUrl)
  target.simpleRequestMethod = String(requestSpec.method || defaultState.simpleRequestMethod).toUpperCase() === 'POST' ? 'POST' : 'GET'
  target.simpleRequestTimeoutSeconds = Number(requestSpec.timeout_seconds || defaultState.simpleRequestTimeoutSeconds)
  target.simpleRequestParamsText = serializeJsonText(requestSpec.params)
  target.simpleRequestHeadersText = serializeJsonText(requestSpec.headers)
  target.simpleRequestDataText = serializeJsonText(requestSpec.data)
  target.simpleRequestJsonText = serializeJsonText(requestSpec.json)

  delete requestSpec.url
  delete requestSpec.method
  delete requestSpec.timeout_seconds
  delete requestSpec.params
  delete requestSpec.headers
  delete requestSpec.data
  delete requestSpec.json
  target.simpleExtraRequest = requestSpec

  target.simpleExtractType = String(extractSpec.type || defaultState.simpleExtractType).toLowerCase() === 'css'
    ? 'css'
    : String(extractSpec.type || defaultState.simpleExtractType).toLowerCase() === 'xpath'
      ? 'xpath'
      : 'jsonpath'
  target.simpleExtractExpression = String(extractSpec.expression || extractSpec.selector || extractSpec.path || defaultState.simpleExtractExpression)

  delete extractSpec.type
  delete extractSpec.expression
  delete extractSpec.selector
  delete extractSpec.path
  target.simpleExtraExtract = extractSpec

  target.simpleIpField = resolveMappingExpression(fieldMapping.ip)
  target.simplePortField = resolveMappingExpression(fieldMapping.port)
  target.simpleProtocolField = resolveMappingExpression(fieldMapping.protocol)
  target.simpleAnonymityField = resolveMappingExpression(fieldMapping.anonymity_level ?? fieldMapping.anonymity)

  const countryRule = fieldMapping.country_code ?? fieldMapping.country
  if (typeof countryRule === 'string') {
    if (countryRule.startsWith('const:')) {
      target.simpleCountryMode = 'const'
      target.simpleCountryValue = countryRule.slice('const:'.length)
      target.simpleCountryDefault = ''
    } else if (countryRule.trim()) {
      target.simpleCountryMode = 'field'
      target.simpleCountryValue = countryRule
      target.simpleCountryDefault = ''
    }
  } else if (countryRule && typeof countryRule === 'object') {
    const normalizedCountryRule = countryRule as Record<string, any>
    target.simpleCountryMode = normalizedCountryRule.transform === 'country_text_to_code' ? 'transform' : 'field'
    target.simpleCountryValue = String(normalizedCountryRule.expression || normalizedCountryRule.path || normalizedCountryRule.selector || '')
    target.simpleCountryDefault = String(normalizedCountryRule.default || '')
  }

  delete fieldMapping.ip
  delete fieldMapping.port
  delete fieldMapping.protocol
  delete fieldMapping.country_code
  delete fieldMapping.country
  delete fieldMapping.anonymity_level
  delete fieldMapping.anonymity
  target.simpleExtraFieldMapping = fieldMapping

  target.simplePaginationEnabled = Object.keys(paginationSpec).length > 0
  target.simplePaginationPageParam = String(paginationSpec.page_param || defaultState.simplePaginationPageParam)
  target.simplePaginationStartPage = Number(paginationSpec.start_page || defaultState.simplePaginationStartPage)
  target.simplePaginationMaxPages = Number(paginationSpec.max_pages || defaultState.simplePaginationMaxPages)
  target.simplePaginationStopWhenEmpty = Boolean(paginationSpec.stop_when_empty)

  delete paginationSpec.page_param
  delete paginationSpec.start_page
  delete paginationSpec.max_pages
  delete paginationSpec.stop_when_empty
  target.simpleExtraPagination = paginationSpec
  target.simpleExtraSpec = extraSpec
}

const buildSimpleCountryRule = (form: CollectorEditorFormState): string | Record<string, any> | null => {
  const value = form.simpleCountryValue.trim()
  const defaultValue = form.simpleCountryDefault.trim()

  if (form.simpleCountryMode === 'none' || !value) {
    return null
  }
  if (form.simpleCountryMode === 'const') {
    return `const:${value}`
  }
  if (form.simpleCountryMode === 'field') {
    return value
  }

  return {
    expression: value,
    transform: 'country_text_to_code',
    ...(defaultValue ? { default: defaultValue } : {}),
  }
}

const buildSimpleSpec = (form: CollectorEditorFormState): Record<string, any> => {
  const request: Record<string, any> = {
    ...form.simpleExtraRequest,
    url: form.simpleRequestUrl.trim(),
    method: form.simpleRequestMethod,
    timeout_seconds: Number(form.simpleRequestTimeoutSeconds || 10),
  }

  const params = parseOptionalJsonText(form.simpleRequestParamsText, '请求参数')
  const headers = parseOptionalJsonText(form.simpleRequestHeadersText, '请求头')
  const data = parseOptionalJsonText(form.simpleRequestDataText, '表单体')
  const jsonBody = parseOptionalJsonText(form.simpleRequestJsonText, 'JSON Body')

  if (params) request.params = params
  else delete request.params
  if (headers) request.headers = headers
  else delete request.headers
  if (data) request.data = data
  else delete request.data
  if (jsonBody) request.json = jsonBody
  else delete request.json

  const extract: Record<string, any> = {
    ...form.simpleExtraExtract,
    type: form.simpleExtractType,
    expression: form.simpleExtractExpression.trim(),
  }

  delete extract.selector
  delete extract.path

  const fieldMapping: Record<string, any> = {
    ...form.simpleExtraFieldMapping,
  }

  const ipField = form.simpleIpField.trim()
  const portField = form.simplePortField.trim()
  const protocolField = form.simpleProtocolField.trim()
  const anonymityField = form.simpleAnonymityField.trim()
  const countryRule = buildSimpleCountryRule(form)

  if (ipField) fieldMapping.ip = ipField
  else delete fieldMapping.ip
  if (portField) fieldMapping.port = portField
  else delete fieldMapping.port
  if (protocolField) fieldMapping.protocol = protocolField
  else delete fieldMapping.protocol
  if (anonymityField) fieldMapping.anonymity_level = anonymityField
  else delete fieldMapping.anonymity_level
  if (countryRule) fieldMapping.country_code = countryRule
  else delete fieldMapping.country_code

  const spec: Record<string, any> = {
    ...form.simpleExtraSpec,
    request,
    extract,
    field_mapping: fieldMapping,
  }

  if (form.source === 'scrape' && form.simplePaginationEnabled) {
    spec.pagination = {
      ...form.simpleExtraPagination,
      page_param: form.simplePaginationPageParam.trim() || 'page',
      start_page: Number(form.simplePaginationStartPage || 1),
      max_pages: Number(form.simplePaginationMaxPages || 1),
      stop_when_empty: Boolean(form.simplePaginationStopWhenEmpty),
    }
  } else {
    delete spec.pagination
  }

  return spec
}

const getCollectorSpecFromForm = (form: CollectorEditorFormState, fieldName: string): Record<string, any> => {
  if (form.mode === 'simple') {
    return buildSimpleSpec(form)
  }
  return parseJsonText(form.specText, fieldName)
}

const createSpecError = computed(() => createForm.mode === 'code' ? validateJsonObjectText(createForm.specText, 'Spec') : null)
const createCodeRefError = computed(() => createForm.mode === 'code' ? validateJsonObjectText(createForm.codeRefText, 'CodeRef') : null)
const editSpecError = computed(() => editForm.mode === 'code' ? validateJsonObjectText(editForm.specText, 'Spec') : null)
const editCodeRefError = computed(() => editForm.mode === 'code' ? validateJsonObjectText(editForm.codeRefText, 'CodeRef') : null)

const formatTime = (time: string): string => {
  const d = new Date(time)
  return isNaN(d.getTime()) ? time : d.toLocaleString('zh-CN')
}

const formatOptionalTime = (time: string): string => {
  if (!time) return 'N/A'
  return formatTime(time)
}

const formatCount = (value: number): string => Number(value || 0).toLocaleString('zh-CN')

const formatSuccessRate = (rate: number): string => {
  if (!Number.isFinite(rate)) return '0%'
  return `${Math.round(rate * 100)}%`
}

const runTagType = (status: CollectorRunStatus): 'success' | 'warning' | 'danger' => {
  if (status === 'success') return 'success'
  if (status === 'partial_success') return 'warning'
  return 'danger'
}

const runText = (status: CollectorRunStatus): string => {
  if (status === 'success') return '成功'
  if (status === 'partial_success') return '部分成功'
  if (status === 'timeout') return '超时'
  return '失败'
}

const workerStatusText = (status: CollectorWorkerSummary['status']): string => {
  if (status === 'running') return '运行中'
  if (status === 'degraded') return '降级'
  if (status === 'unset') return '未设置'
  return '离线'
}

const normalizeWorkerStatus = (status: string): CollectorWorkerSummary['status'] => {
  const normalized = status.trim().toLowerCase()
  if (normalized === 'running') return 'running'
  if (normalized === 'degraded') return 'degraded'
  if (normalized === 'unset') return 'unset'
  return 'stopped'
}

const buildOverviewSummary = (rows: CollectorRow[], cooldownPoolCount = 0): CollectorOverviewSummary => {
  const summary = rows.reduce(
    (acc, row) => {
      acc.total += 1
      if (row.lifecycle === 'published') acc.published += 1
      if (row.lifecycle === 'paused') acc.paused += 1
      if (row.lifecycle === 'draft') acc.draft += 1

      const storedCount = Number(row.lastRun?.metrics?.stored_count ?? 0)
      acc.recentStoredCount += storedCount

      if (row.lastRun) {
        acc.rated += 1
        if (row.lastRun.status === 'success' || row.lastRun.status === 'partial_success') {
          acc.success += 1
        }
      }
      return acc
    },
    {
      total: 0,
      published: 0,
      paused: 0,
      draft: 0,
      recentStoredCount: 0,
      success: 0,
      rated: 0,
      cooldownPoolCount,
    },
  )

  return {
    total: summary.total,
    published: summary.published,
    paused: summary.paused,
    draft: summary.draft,
    recentStoredCount: summary.recentStoredCount,
    successRate: summary.rated > 0 ? Number((summary.success / summary.rated).toFixed(2)) : 0,
    cooldownPoolCount: summary.cooldownPoolCount,
  }
}

const buildLatestRunSummary = (rows: CollectorRow[]) => {
  const latest = rows
    .filter(row => Boolean(row.lastRun))
    .sort((a, b) => new Date(String(b.lastRun?.ended_at || 0)).getTime() - new Date(String(a.lastRun?.ended_at || 0)).getTime())[0]

  if (!latest?.lastRun) {
    return null
  }

  return {
    collectorName: latest.name,
    status: latest.lastRun.status,
    statusText: runText(latest.lastRun.status),
    endedAt: latest.lastRun.ended_at,
    metrics: latest.lastRun.metrics,
  }
}

const latestRunSummary = computed(() => buildLatestRunSummary(collectors.value))

const dashboardCards = computed(() => {
  const summary = overviewSummary.value ?? buildOverviewSummary(collectors.value)
  const latestRun = latestRunSummary.value
  const worker = workerSummary.value
  const enabledCount = collectors.value.filter(row => row.enabled).length

  return [
    {
      key: 'summary',
      title: '收集器概览',
      value: formatCount(summary.total),
      subtitle: `已发布 ${summary.published} · 已暂停 ${summary.paused} · 草稿 ${summary.draft}`,
      details: [
        `最近入库 ${formatCount(summary.recentStoredCount)}`,
        `成功率 ${formatSuccessRate(summary.successRate)}`,
        `冷却池 ${formatCount(summary.cooldownPoolCount)}`,
      ],
      metrics: [],
    },
    {
      key: 'run',
      title: '最近运行',
      value: latestRun ? latestRun.statusText : '暂无记录',
      subtitle: latestRun ? `${latestRun.collectorName} · ${formatTime(latestRun.endedAt)}` : '等待首次测试运行',
      details: latestRun ? [`raw ${latestRun.metrics.raw_count}`, `valid ${latestRun.metrics.valid_count}`] : [],
      metrics: latestRun
        ? [
            `stored ${latestRun.metrics.stored_count}`,
            `duplicate ${latestRun.metrics.duplicate_count}`,
            `冷却阻断 ${latestRun.metrics.cooldown_blocked_count ?? 0}`,
          ]
        : [],
    },
    {
      key: 'output',
      title: '最近入库',
      value: formatCount(summary.recentStoredCount),
      subtitle: `成功率 ${formatSuccessRate(summary.successRate)}`,
      details: [`总收集器 ${summary.total}`, `已启用 ${enabledCount}`],
      metrics: [],
    },
    {
      key: 'worker',
      title: 'Worker 状态',
      value: worker ? workerStatusText(worker.status) : '未连接',
      subtitle: worker ? `执行中 ${worker.activeJobs} · 待执行 ${worker.queueBacklog}` : '当前未获取到 Worker 摘要',
      details: worker ? [`最近心跳 ${formatOptionalTime(worker.lastHeartbeat)}`] : [],
      metrics: worker && (worker.status === 'stopped' || worker.status === 'unset') ? ['当前状态下指标仅供参考'] : [],
    },
  ]
})

const createCollectorRowFromRealtimeItem = (item: CollectorRealtimeItem): CollectorRow => ({
  id: item.id,
  name: item.name || item.id,
  mode: item.mode || 'simple',
  source: item.source || 'api',
  enabled: item.enabled ?? true,
  lifecycle: item.lifecycle || 'draft',
  interval_seconds: item.interval_seconds || 0,
  spec: item.spec || {},
  code_ref: item.code_ref ?? null,
  env_vars: item.env_vars,
  meta: item.meta,
  runs: item.runs,
  actionLoading: false,
  lastRun: item.last_run ?? item.lastRun ?? null,
})

const buildSnapshotRows = (items: CollectorRealtimeItem[], currentRows: CollectorRow[]): CollectorRow[] => {
  const actionLoadingMap = new Map(currentRows.map(row => [row.id, Boolean(row.actionLoading)]))

  return items.map((item) => ({
    ...createCollectorRowFromRealtimeItem(item),
    actionLoading: actionLoadingMap.get(item.id) ?? false,
  }))
}

const syncOverviewSummary = (rows: CollectorRow[]) => {
  overviewSummary.value = buildOverviewSummary(rows, overviewSummary.value?.cooldownPoolCount ?? 0)
}

const applyCollectorUpdatePayload = (payload: CollectorRealtimeUpdatePayload) => {
  if (payload.worker_summary) {
    workerSummary.value = payload.worker_summary
  }

  if (payload.collectors !== undefined) {
    collectors.value = buildSnapshotRows(Array.isArray(payload.collectors) ? payload.collectors : [], collectors.value)
  }

  if (payload.overview) {
    overviewSummary.value = {
      ...payload.overview,
      cooldownPoolCount: payload.overview.cooldownPoolCount ?? 0,
    }
    return
  }

  syncOverviewSummary(collectors.value)
}

const loadWorkerSummary = async () => {
  try {
    const modules = await getModuleStatus()
    const moduleList = Array.isArray(modules) ? modules : []
    const collectorWorker = moduleList.find(module => (
      module?.moduleName === 'Collector' || module?.moduleName === 'Collector Worker'
    ))
    if (!collectorWorker) {
      workerSummary.value = null
      return
    }

    const performance = (collectorWorker.performance || {}) as Record<string, any>
    workerSummary.value = {
      status: normalizeWorkerStatus(String(collectorWorker.status || 'stopped')),
      activeJobs: Number(performance.active_jobs || 0),
      queueBacklog: Number(performance.queue_backlog || 0),
      lastHeartbeat: String(collectorWorker.lastHeartbeat || ''),
    }
  } catch {
    workerSummary.value = null
  }
}

const loadCollectors = async () => {
  loading.value = true
  try {
    const response = await collectorApi.getCollectors()
    const data = (response.data?.collectors || []) as CollectorV2[]

    const runPromises = data.map(async collector => {
      try {
        const runResp = await collectorApi.getCollectorRuns(collector.id, 1)
        const latest = (runResp.data?.runs || [])[0] as CollectorRunRecord | undefined
        return {
          ...collector,
          actionLoading: false,
          lastRun: latest || null,
        } as CollectorRow
      } catch {
        return {
          ...collector,
          actionLoading: false,
          lastRun: null,
        } as CollectorRow
      }
    })

    collectors.value = await Promise.all(runPromises)
    syncOverviewSummary(collectors.value)
    await loadWorkerSummary()
  } catch (error) {
    ElMessage.error('加载收集器失败')
    console.error(error)
    workerSummary.value = null
  } finally {
    loading.value = false
  }
}

let unsubscribeCollectorUpdate: (() => void) | null = null

const handleCollectorUpdate = (message: { data?: CollectorRealtimeUpdatePayload }) => {
  if (!message?.data) {
    return
  }
  applyCollectorUpdatePayload(message.data)
}

const openCreateDialog = () => {
  Object.assign(createForm, buildCreateFormState())
  createDialogVisible.value = true
}

const openEditDialog = (row: CollectorRow) => {
  Object.assign(editForm, buildEditFormState(), {
    id: row.id,
    name: row.name,
    mode: row.mode,
    source: row.source,
    enabled: row.enabled,
    interval_seconds: row.interval_seconds,
    specText: JSON.stringify(row.spec || {}, null, 2),
    codeRefText: JSON.stringify(row.code_ref || {}, null, 2),
  })
  if (row.mode === 'simple') {
    applySimpleSpecToForm(editForm, row.spec || {})
  }
  editDialogVisible.value = true
}

const handleCreate = async () => {
  const nameError = validateCollectorName(createForm.name)
  if (nameError) {
    ElMessage.warning(nameError)
    return
  }
  if (createSpecError.value || createCodeRefError.value) {
    ElMessage.warning(createSpecError.value || createCodeRefError.value || 'JSON 配置校验失败')
    return
  }

  creating.value = true
  try {
    const spec = getCollectorSpecFromForm(createForm, 'Spec')
    const codeRef = createForm.mode === 'code' ? parseJsonText(createForm.codeRefText, 'CodeRef') : null
    await collectorApi.createCollector({
      name: createForm.name.trim(),
      mode: createForm.mode,
      source: createForm.source,
      enabled: createForm.enabled,
      interval_seconds: createForm.interval_seconds,
      spec,
      code_ref: codeRef,
      env_vars: {},
    })
    ElMessage.success('创建成功')
    createDialogVisible.value = false
    await loadCollectors()
  } catch (error: any) {
    ElMessage.error(error?.message || '创建失败')
  } finally {
    creating.value = false
  }
}

const handleSave = async () => {
  const nameError = validateCollectorName(editForm.name)
  if (nameError) {
    ElMessage.warning(nameError)
    return
  }
  if (editSpecError.value || editCodeRefError.value) {
    ElMessage.warning(editSpecError.value || editCodeRefError.value || 'JSON 配置校验失败')
    return
  }

  saving.value = true
  try {
    if (!editForm.id) {
      throw new Error('收集器 ID 缺失，无法保存')
    }
    const spec = getCollectorSpecFromForm(editForm, 'Spec')
    const codeRef = editForm.mode === 'code' ? parseJsonText(editForm.codeRefText, 'CodeRef') : null
    await collectorApi.updateCollector(editForm.id, {
      name: editForm.name.trim(),
      enabled: editForm.enabled,
      interval_seconds: editForm.interval_seconds,
      spec,
      code_ref: codeRef,
      env_vars: {},
    })
    ElMessage.success('保存成功')
    editDialogVisible.value = false
    await loadCollectors()
  } catch (error: any) {
    ElMessage.error(error?.message || '保存失败')
  } finally {
    saving.value = false
  }
}

const withActionLoading = async (row: CollectorRow, action: () => Promise<void>) => {
  const setActionLoading = (loading: boolean) => {
    collectors.value = collectors.value.map(currentRow => (
      currentRow.id === row.id
        ? { ...currentRow, actionLoading: loading }
        : currentRow
    ))
  }

  setActionLoading(true)
  try {
    await action()
  } finally {
    setActionLoading(false)
  }
}

const handleTestRun = async (row: CollectorRow) => {
  await withActionLoading(row, async () => {
    try {
      const response = await collectorApi.testRunCollector(row.id, 'test')
      currentRunRecord.value = response.data as CollectorRunRecord
      reportDialogVisible.value = true
      ElMessage.success('测试运行完成')
      await loadCollectors()
    } catch (error: any) {
      ElMessage.error(error?.response?.data?.detail || '测试运行失败')
    }
  })
}

const handlePublish = async (row: CollectorRow) => {
  await withActionLoading(row, async () => {
    try {
      await collectorApi.publishCollector(row.id, false)
      ElMessage.success('发布成功')
      await loadCollectors()
    } catch (error: any) {
      ElMessage.error(error?.response?.data?.detail || '发布失败')
    }
  })
}

const handlePause = async (row: CollectorRow) => {
  await withActionLoading(row, async () => {
    try {
      await collectorApi.pauseCollector(row.id)
      ElMessage.success('已暂停')
      await loadCollectors()
    } catch (error: any) {
      ElMessage.error(error?.response?.data?.detail || '暂停失败')
    }
  })
}

const handleResume = async (row: CollectorRow) => {
  await withActionLoading(row, async () => {
    try {
      await collectorApi.resumeCollector(row.id)
      ElMessage.success('已恢复')
      await loadCollectors()
    } catch (error: any) {
      ElMessage.error(error?.response?.data?.detail || '恢复失败')
    }
  })
}

const handleDelete = async (row: CollectorRow) => {
  try {
    await ElMessageBox.confirm(`确认删除收集器 ${row.name} 吗？`, '删除确认', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
  } catch {
    return
  }

  await withActionLoading(row, async () => {
    try {
      await collectorApi.deleteCollector(row.id)
      ElMessage.success('删除成功')
      await loadCollectors()
    } catch (error: any) {
      ElMessage.error(error?.response?.data?.detail || '删除失败')
    }
  })
}

const openRunHistory = async (row: CollectorRow) => {
  runHistoryDrawerVisible.value = true
  runHistoryLoading.value = true
  currentHistoryCollectorName.value = row.name
  try {
    const response = await collectorApi.getCollectorRuns(row.id, 50)
    runHistory.value = (response.data?.runs || []) as CollectorRunRecord[]
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || '加载运行记录失败')
    runHistory.value = []
  } finally {
    runHistoryLoading.value = false
  }
}

const goToLogView = (collectorId: string, runId: string) => {
  router.push({
    path: '/logs',
    query: {
      collector_id: collectorId,
      run_id: runId,
    },
  })
}

onMounted(async () => {
  await loadCollectors()
  unsubscribeCollectorUpdate = dashboardRealtimeClient.subscribe('collector_update', handleCollectorUpdate)
  dashboardRealtimeClient.connect()
})

onUnmounted(() => {
  unsubscribeCollectorUpdate?.()
  unsubscribeCollectorUpdate = null
})
</script>

<style scoped>
.collector-manager {
  padding: 20px;
}

.collector-overview {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 16px;
  margin-bottom: 20px;
}

.overview-card {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 18px;
  border-radius: 16px;
  border: 1px solid var(--el-border-color-light);
  background: linear-gradient(180deg, var(--el-bg-color) 0%, var(--el-fill-color-lighter) 100%);
  box-shadow: 0 10px 24px rgba(15, 23, 42, 0.04);
}

.overview-card--summary {
  border-color: rgba(64, 158, 255, 0.18);
}

.overview-card--run {
  border-color: rgba(103, 194, 58, 0.18);
}

.overview-card--output {
  border-color: rgba(230, 162, 60, 0.18);
}

.overview-card--worker {
  border-color: rgba(245, 108, 108, 0.18);
}

.overview-card__label {
  color: var(--el-text-color-secondary);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}

.overview-card__value {
  color: var(--el-text-color-primary);
  font-size: 28px;
  font-weight: 700;
  line-height: 1.1;
}

.overview-card__subtitle {
  color: var(--el-text-color-secondary);
  font-size: 13px;
}

.overview-card__details,
.overview-card__metrics {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.overview-card__detail,
.overview-card__metric {
  padding: 4px 10px;
  border-radius: 999px;
  background: var(--bg-secondary, #f5f7fa);
  color: var(--text-secondary, var(--el-text-color-secondary));
  font-size: 13px;
  font-weight: 500;
}

.error-list {
  margin: 0;
  padding-left: 20px;
}

@media (max-width: 768px) {
  .collector-manager {
    padding: 16px;
  }

  .collector-overview {
    gap: 12px;
    margin-bottom: 16px;
  }

  .overview-card {
    padding: 16px;
    border-radius: 14px;
  }

  .overview-card__value {
    font-size: 24px;
  }
}
</style>
