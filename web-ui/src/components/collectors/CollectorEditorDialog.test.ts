import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import CollectorEditorDialog from './CollectorEditorDialog.vue'

const buildSimpleFormFields = () => ({
  simpleRequestUrl: '',
  simpleRequestMethod: 'GET' as const,
  simpleRequestTimeoutSeconds: 10,
  simpleRequestParamsText: '',
  simpleRequestHeadersText: '',
  simpleRequestDataText: '',
  simpleRequestJsonText: '',
  simpleExtractType: 'jsonpath' as const,
  simpleExtractExpression: '',
  simpleIpField: '',
  simplePortField: '',
  simpleProtocolField: '',
  simpleCountryMode: 'none' as const,
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
})

describe('CollectorEditorDialog', () => {
  it('点击提交应触发 submit 事件，code 模式显示 CodeRef 输入', async () => {
    const wrapper = mount(CollectorEditorDialog, {
      props: {
        visible: true,
        title: '编辑收集器',
        loading: false,
        submitText: '保存',
        showId: true,
        form: {
          id: 'demo',
          name: 'Demo',
          mode: 'code',
          source: 'api',
          enabled: true,
          interval_seconds: 300,
          specText: '{}',
          codeRefText: '{"filename":"demo.py"}',
          ...buildSimpleFormFields(),
        },
      },
      global: {
        stubs: {
          'el-dialog': { template: '<div><slot /><slot name="footer" /></div>' },
          'el-form': { template: '<form><slot /></form>' },
          'el-form-item': { props: ['label'], template: '<div>{{ label }}<slot /></div>' },
          'el-input': { template: '<input />' },
          'el-radio-group': { template: '<div><slot /></div>' },
          'el-radio-button': { template: '<button><slot /></button>' },
          'el-switch': { template: '<input type="checkbox" />' },
          'el-input-number': { template: '<input type="number" />' },
          'el-select': { template: '<select><slot /></select>' },
          'el-option': { props: ['label', 'value'], template: '<option :value="value">{{ label }}</option>' },
          'el-button': { template: '<button @click="$emit(\'click\')"><slot /></button>' },
        },
      },
    })

    expect(wrapper.text()).toContain('CodeRef(JSON)')

    const saveButton = wrapper.findAll('button').find(btn => btn.text().includes('保存'))
    expect(saveButton).toBeTruthy()
    await saveButton!.trigger('click')

    expect(wrapper.emitted('submit')).toBeTruthy()
  })

  it('简单模式应显示结构化请求与字段映射表单', () => {
    const wrapper = mount(CollectorEditorDialog, {
      props: {
        visible: true,
        title: '新建收集器',
        loading: false,
        submitText: '创建',
        showModeSource: true,
        form: {
          name: 'simple_demo',
          mode: 'simple',
          source: 'api',
          enabled: true,
          interval_seconds: 300,
          specText: '{}',
          codeRefText: '{}',
          ...buildSimpleFormFields(),
        },
      },
      global: {
        stubs: {
          'el-dialog': { template: '<div><slot /><slot name="footer" /></div>' },
          'el-form': { template: '<form><slot /></form>' },
          'el-form-item': { props: ['label'], template: '<div>{{ label }}<slot /></div>' },
          'el-input': { template: '<input />' },
          'el-radio-group': { template: '<div><slot /></div>' },
          'el-radio-button': { template: '<button><slot /></button>' },
          'el-switch': { template: '<input type="checkbox" />' },
          'el-input-number': { template: '<input type="number" />' },
          'el-select': { template: '<select><slot /></select>' },
          'el-option': { props: ['label', 'value'], template: '<option :value="value">{{ label }}</option>' },
          'el-button': { template: '<button><slot /></button>' },
        },
      },
    })

    expect(wrapper.text()).toContain('请求 URL')
    expect(wrapper.text()).toContain('请求方法')
    expect(wrapper.text()).toContain('提取类型')
    expect(wrapper.text()).toContain('提取表达式')
    expect(wrapper.text()).toContain('国家代码')
  })

  it('简单模式 + Scrape 应显示分页控件，API 来源不应显示分页控件', () => {
    const scrapeWrapper = mount(CollectorEditorDialog, {
      props: {
        visible: true,
        title: '新建收集器',
        loading: false,
        submitText: '创建',
        showModeSource: true,
        form: {
          name: 'scrape_demo',
          mode: 'simple',
          source: 'scrape',
          enabled: true,
          interval_seconds: 300,
          specText: '{}',
          codeRefText: '{}',
          ...buildSimpleFormFields(),
          simplePaginationEnabled: false,
          simplePaginationPageParam: 'page',
          simplePaginationStartPage: 1,
          simplePaginationMaxPages: 20,
          simplePaginationStopWhenEmpty: true,
        } as any,
      },
      global: {
        stubs: {
          'el-dialog': { template: '<div><slot /><slot name="footer" /></div>' },
          'el-form': { template: '<form><slot /></form>' },
          'el-form-item': { props: ['label'], template: '<div>{{ label }}<slot /></div>' },
          'el-input': { template: '<input />' },
          'el-radio-group': { template: '<div><slot /></div>' },
          'el-radio-button': { template: '<button><slot /></button>' },
          'el-switch': { template: '<input type="checkbox" />' },
          'el-input-number': { template: '<input type="number" />' },
          'el-select': { template: '<select><slot /></select>' },
          'el-option': { props: ['label', 'value'], template: '<option :value="value">{{ label }}</option>' },
          'el-button': { template: '<button><slot /></button>' },
        },
      },
    })

    expect(scrapeWrapper.text()).toContain('启用分页')
    expect(scrapeWrapper.text()).toContain('页码参数名')
    expect(scrapeWrapper.text()).toContain('起始页')
    expect(scrapeWrapper.text()).toContain('最大页数')
    expect(scrapeWrapper.text()).toContain('遇到空页即停止')

    const apiWrapper = mount(CollectorEditorDialog, {
      props: {
        visible: true,
        title: '新建收集器',
        loading: false,
        submitText: '创建',
        showModeSource: true,
        form: {
          name: 'api_demo',
          mode: 'simple',
          source: 'api',
          enabled: true,
          interval_seconds: 300,
          specText: '{}',
          codeRefText: '{}',
          ...buildSimpleFormFields(),
        },
      },
      global: {
        stubs: {
          'el-dialog': { template: '<div><slot /><slot name="footer" /></div>' },
          'el-form': { template: '<form><slot /></form>' },
          'el-form-item': { props: ['label'], template: '<div>{{ label }}<slot /></div>' },
          'el-input': { template: '<input />' },
          'el-radio-group': { template: '<div><slot /></div>' },
          'el-radio-button': { template: '<button><slot /></button>' },
          'el-switch': { template: '<input type="checkbox" />' },
          'el-input-number': { template: '<input type="number" />' },
          'el-select': { template: '<select><slot /></select>' },
          'el-option': { props: ['label', 'value'], template: '<option :value="value">{{ label }}</option>' },
          'el-button': { template: '<button><slot /></button>' },
        },
      },
    })

    expect(apiWrapper.text()).not.toContain('启用分页')
    expect(apiWrapper.text()).not.toContain('页码参数名')
    expect(apiWrapper.text()).not.toContain('起始页')
    expect(apiWrapper.text()).not.toContain('最大页数')
    expect(apiWrapper.text()).not.toContain('遇到空页即停止')
  })

  it('专家模式应显示 JSON 校验错误并禁用提交', () => {
    const wrapper = mount(CollectorEditorDialog, {
      props: {
        visible: true,
        title: '新建收集器',
        loading: false,
        submitText: '创建',
        submitDisabled: true,
        specError: 'Spec JSON 解析失败: Unexpected token }',
        codeRefError: 'CodeRef JSON 解析失败: Unexpected token }',
        showModeSource: true,
        form: {
          name: 'expert_demo',
          mode: 'code',
          source: 'api',
          enabled: true,
          interval_seconds: 300,
          specText: '{"request": }',
          codeRefText: '{"filename": }',
          ...buildSimpleFormFields(),
        },
      },
      global: {
        stubs: {
          'el-dialog': { template: '<div><slot /><slot name="footer" /></div>' },
          'el-form': { template: '<form><slot /></form>' },
          'el-form-item': {
            props: ['label', 'error'],
            template: '<div>{{ label }}{{ error }}<slot /></div>',
          },
          'el-input': { template: '<input />' },
          'el-radio-group': { template: '<div><slot /></div>' },
          'el-radio-button': { template: '<button><slot /></button>' },
          'el-switch': { template: '<input type="checkbox" />' },
          'el-input-number': { template: '<input type="number" />' },
          'el-select': { template: '<select><slot /></select>' },
          'el-option': { props: ['label', 'value'], template: '<option :value="value">{{ label }}</option>' },
          'el-button': {
            props: ['disabled'],
            template: '<button :disabled="disabled" @click="$emit(\'click\')"><slot /></button>',
          },
        },
      },
    })

    expect(wrapper.text()).toContain('专家模式')
    expect(wrapper.text()).toContain('Spec JSON 解析失败')
    expect(wrapper.text()).toContain('CodeRef JSON 解析失败')

    const submitButton = wrapper.findAll('button').find(btn => btn.text().includes('创建'))
    expect(submitButton?.attributes('disabled')).toBeDefined()
  })
})
