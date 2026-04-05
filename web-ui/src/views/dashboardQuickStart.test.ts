import { describe, expect, it } from 'vitest'
import { buildRandomProxyUrl, appendTokenToUrl } from './dashboardQuickStart'

describe('dashboardQuickStart helpers', () => {
  it('相对 API Base URL 会拼接当前站点 origin', () => {
    expect(buildRandomProxyUrl('/api/v1', 'http://localhost:8080')).toBe('http://localhost:8080/api/v1/random')
  })

  it('绝对 API Base URL 直接拼接 random 路径', () => {
    expect(buildRandomProxyUrl('https://api.example.com/api/v1', 'http://localhost:8080')).toBe('https://api.example.com/api/v1/random')
  })

  it('为 URL 自动附加 token 查询参数', () => {
    expect(appendTokenToUrl('http://localhost:8080/api/v1/random', 'abc123')).toBe(
      'http://localhost:8080/api/v1/random?token=abc123',
    )
  })

  it('为已有查询参数的 URL 附加 token 查询参数', () => {
    expect(appendTokenToUrl('http://localhost:8080/api/v1/random?protocol=https', 'abc123')).toBe(
      'http://localhost:8080/api/v1/random?protocol=https&token=abc123',
    )
  })
})
