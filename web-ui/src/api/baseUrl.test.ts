import { describe, expect, it } from 'vitest'
import { normalizeApiBaseUrl } from './baseUrl'

describe('normalizeApiBaseUrl', () => {
  it('在未配置时使用默认 /api/v1', () => {
    expect(normalizeApiBaseUrl(undefined)).toBe('/api/v1')
    expect(normalizeApiBaseUrl('')).toBe('/api/v1')
  })

  it('保留已包含 /api/v1 的地址', () => {
    expect(normalizeApiBaseUrl('/api/v1')).toBe('/api/v1')
    expect(normalizeApiBaseUrl('http://localhost:8000/api/v1')).toBe('http://localhost:8000/api/v1')
  })

  it('去掉尾部斜杠', () => {
    expect(normalizeApiBaseUrl('/api/v1/')).toBe('/api/v1')
    expect(normalizeApiBaseUrl('http://localhost:8000/api/v1/')).toBe('http://localhost:8000/api/v1')
  })

  it('自动补齐缺失的 /api/v1 前缀', () => {
    expect(normalizeApiBaseUrl('http://localhost:8000')).toBe('http://localhost:8000/api/v1')
    expect(normalizeApiBaseUrl('http://localhost:8000/')).toBe('http://localhost:8000/api/v1')
    expect(normalizeApiBaseUrl('/api')).toBe('/api/v1')
    expect(normalizeApiBaseUrl('http://localhost:8000/api')).toBe('http://localhost:8000/api/v1')
  })
})
