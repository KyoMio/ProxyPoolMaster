<template>
  <el-dialog
    :model-value="visible"
    :title="title"
    width="640px"
    :close-on-click-modal="false"
    @update:model-value="$emit('update:visible', $event)"
  >
    <el-form :model="form" label-width="110px">
      <el-form-item v-if="showId" label="ID">
        <el-input v-model="form.id" disabled />
      </el-form-item>

      <el-form-item label="名称" :error="nameError || undefined">
        <el-input v-model="form.name" placeholder="请输入收集器名称" />
        <div class="field-hint">{{ nameHint }}</div>
      </el-form-item>

      <el-form-item v-if="showModeSource" label="模式">
        <el-radio-group v-model="form.mode">
          <el-radio-button value="simple">简单模式</el-radio-button>
          <el-radio-button value="code">专家模式</el-radio-button>
        </el-radio-group>
      </el-form-item>

      <el-form-item v-if="showModeSource" label="来源">
        <el-radio-group v-model="form.source">
          <el-radio-button value="api">API</el-radio-button>
          <el-radio-button value="scrape">Scrape</el-radio-button>
        </el-radio-group>
      </el-form-item>

      <el-form-item v-if="showEnabled" label="启用状态">
        <el-switch v-model="form.enabled" />
      </el-form-item>

      <el-form-item label="执行间隔(秒)">
        <el-input-number v-model="form.interval_seconds" :min="60" :step="60" style="width: 200px" />
      </el-form-item>

      <template v-if="form.mode === 'simple'">
        <el-form-item label="请求 URL">
          <el-input v-model="form.simpleRequestUrl" placeholder="https://example.com/api/proxies" />
        </el-form-item>

        <el-form-item label="请求方法">
          <el-select v-model="form.simpleRequestMethod" style="width: 200px">
            <el-option label="GET" value="GET" />
            <el-option label="POST" value="POST" />
          </el-select>
        </el-form-item>

        <el-form-item label="请求超时(秒)">
          <el-input-number v-model="form.simpleRequestTimeoutSeconds" :min="1" :step="1" style="width: 200px" />
        </el-form-item>

        <el-form-item label="请求参数(JSON)">
          <el-input v-model="form.simpleRequestParamsText" type="textarea" :rows="3" placeholder='{"page": 1}' />
        </el-form-item>

        <el-form-item label="请求头(JSON)">
          <el-input v-model="form.simpleRequestHeadersText" type="textarea" :rows="3" placeholder='{"User-Agent": "..."}' />
        </el-form-item>

        <el-form-item label="表单体(JSON)">
          <el-input v-model="form.simpleRequestDataText" type="textarea" :rows="3" placeholder='{"token": "..."}' />
        </el-form-item>

        <el-form-item label="JSON Body(JSON)">
          <el-input v-model="form.simpleRequestJsonText" type="textarea" :rows="3" placeholder='{"count": 100}' />
        </el-form-item>

        <el-form-item label="提取类型">
          <el-select v-model="form.simpleExtractType" style="width: 200px">
            <el-option label="jsonpath" value="jsonpath" />
            <el-option label="css" value="css" />
            <el-option label="xpath" value="xpath" />
          </el-select>
        </el-form-item>

        <el-form-item label="提取表达式">
          <el-input v-model="form.simpleExtractExpression" placeholder="$.data.proxy_list[*]" />
        </el-form-item>

        <el-form-item label="IP 字段">
          <el-input v-model="form.simpleIpField" placeholder="ip" />
        </el-form-item>

        <el-form-item label="端口字段">
          <el-input v-model="form.simplePortField" placeholder="port" />
        </el-form-item>

        <el-form-item label="协议字段">
          <el-input v-model="form.simpleProtocolField" placeholder="protocol 或 const:http" />
        </el-form-item>

        <el-form-item label="国家代码">
          <div class="country-field-grid">
            <el-select v-model="form.simpleCountryMode">
              <el-option label="不设置" value="none" />
              <el-option label="固定值" value="const" />
              <el-option label="直接字段" value="field" />
              <el-option label="文本转代码" value="transform" />
            </el-select>
            <el-input
              v-model="form.simpleCountryValue"
              :placeholder="form.simpleCountryMode === 'const' ? 'CN' : 'adr / country_code'"
            />
            <el-input
              v-model="form.simpleCountryDefault"
              placeholder="转换失败默认值，可留空"
            />
          </div>
        </el-form-item>

        <el-form-item label="匿名度字段">
          <el-input v-model="form.simpleAnonymityField" placeholder="level" />
        </el-form-item>

        <template v-if="form.source === 'scrape'">
          <el-form-item label="启用分页">
            <el-switch v-model="form.simplePaginationEnabled" />
          </el-form-item>

          <el-form-item label="页码参数名">
            <el-input
              v-model="form.simplePaginationPageParam"
              :disabled="!form.simplePaginationEnabled"
              placeholder="page"
            />
          </el-form-item>

          <el-form-item label="起始页">
            <el-input-number
              v-model="form.simplePaginationStartPage"
              :disabled="!form.simplePaginationEnabled"
              :min="1"
              :step="1"
              style="width: 200px"
            />
          </el-form-item>

          <el-form-item label="最大页数">
            <el-input-number
              v-model="form.simplePaginationMaxPages"
              :disabled="!form.simplePaginationEnabled"
              :min="1"
              :step="1"
              style="width: 200px"
            />
          </el-form-item>

          <el-form-item label="遇到空页即停止">
            <el-switch v-model="form.simplePaginationStopWhenEmpty" :disabled="!form.simplePaginationEnabled" />
          </el-form-item>
        </template>
      </template>

      <template v-else>
        <div class="field-hint expert-hint">
          专家模式适合需要手动维护底层 spec 与 code_ref 的高级场景。提交前会做基础 JSON 校验。
        </div>
        <el-form-item label="Spec(JSON)" :error="specError || undefined">
          <el-input v-model="form.specText" type="textarea" :rows="8" />
        </el-form-item>
      </template>

      <el-form-item v-if="form.mode === 'code'" label="CodeRef(JSON)" :error="codeRefError || undefined">
        <el-input v-model="form.codeRefText" type="textarea" :rows="6" />
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button @click="$emit('update:visible', false)">取消</el-button>
      <el-button type="primary" :loading="loading" :disabled="submitDisabled" @click="$emit('submit')">{{ submitText }}</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
interface CollectorEditorForm {
  id?: string
  name: string
  mode: 'simple' | 'code'
  source: 'api' | 'scrape'
  enabled: boolean
  interval_seconds: number
  specText: string
  codeRefText: string
  simpleRequestUrl: string
  simpleRequestMethod: 'GET' | 'POST'
  simpleRequestTimeoutSeconds: number
  simpleRequestParamsText: string
  simpleRequestHeadersText: string
  simpleRequestDataText: string
  simpleRequestJsonText: string
  simpleExtractType: 'jsonpath' | 'css' | 'xpath'
  simpleExtractExpression: string
  simpleIpField: string
  simplePortField: string
  simpleProtocolField: string
  simpleCountryMode: 'none' | 'const' | 'field' | 'transform'
  simpleCountryValue: string
  simpleCountryDefault: string
  simpleAnonymityField: string
  simplePaginationEnabled: boolean
  simplePaginationPageParam: string
  simplePaginationStartPage: number
  simplePaginationMaxPages: number
  simplePaginationStopWhenEmpty: boolean
  simpleExtraSpec?: Record<string, any>
  simpleExtraRequest?: Record<string, any>
  simpleExtraExtract?: Record<string, any>
  simpleExtraFieldMapping?: Record<string, any>
  simpleExtraPagination?: Record<string, any>
}

defineProps<{
  visible: boolean
  title: string
  loading: boolean
  submitText: string
  nameHint?: string
  nameError?: string | null
  specError?: string | null
  codeRefError?: string | null
  submitDisabled?: boolean
  showId?: boolean
  showModeSource?: boolean
  showEnabled?: boolean
  form: CollectorEditorForm
}>()

defineEmits<{
  (e: 'update:visible', value: boolean): void
  (e: 'submit'): void
}>()
</script>

<style scoped>
.field-hint {
  margin-top: 6px;
  color: var(--text-tertiary);
  font-size: 12px;
  line-height: 1.4;
}

.expert-hint {
  margin-bottom: 12px;
}

.country-field-grid {
  width: 100%;
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}

@media (max-width: 768px) {
  .country-field-grid {
    grid-template-columns: 1fr;
  }
}
</style>
