import { shallowMount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import TimeInputWithUnit from './TimeInputWithUnit.vue'

describe('TimeInputWithUnit', () => {
  it('disabled=true 时应将禁用状态透传给输入框与单位选择器', () => {
    const wrapper = shallowMount(TimeInputWithUnit, {
      props: {
        modelValue: 300,
        disabled: true,
      },
      global: {
        stubs: {
          'el-input-number': {
            template: '<div class="num-stub" :data-disabled="String($attrs.disabled)" />',
          },
          'el-select': {
            template: '<div class="select-stub" :data-disabled="String($attrs.disabled)"><slot /></div>',
          },
          'el-option': {
            template: '<div />',
          },
        },
      },
    })

    expect(wrapper.find('.num-stub').attributes('data-disabled')).toBe('true')
    expect(wrapper.find('.select-stub').attributes('data-disabled')).toBe('true')
  })
})

