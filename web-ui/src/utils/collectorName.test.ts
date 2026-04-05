import { describe, expect, it } from 'vitest'

import { validateCollectorName } from './collectorName'

describe('validateCollectorName', () => {
  it('应接受合法的收集器名称', () => {
    expect(validateCollectorName('zdaye_overseas_v2')).toBeNull()
  })

  it('应拒绝中文名称', () => {
    expect(validateCollectorName('站大爷海外代理')).toContain('仅允许')
  })

  it('应拒绝数字开头的名称', () => {
    expect(validateCollectorName('2collector')).toContain('字母开头')
  })

  it('应拒绝包含横线的名称', () => {
    expect(validateCollectorName('collector-test')).toContain('仅允许')
  })
})
