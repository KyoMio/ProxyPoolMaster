import { describe, expect, it } from 'vitest'

import { resolveWsEndpoint } from './realtime'

describe('resolveWsEndpoint', () => {
  it('优先使用显式 WS URL', () => {
    expect(resolveWsEndpoint('ws://localhost:8000/ws/dashboard', 'http://localhost:8000/api/v1', '/ws/logs')).toBe('ws://localhost:8000/ws/logs')
  })

  it('从 HTTP API 地址推导 WS URL', () => {
    expect(resolveWsEndpoint('', 'http://localhost:8000/api/v1', '/ws/dashboard')).toBe('ws://localhost:8000/ws/dashboard')
    expect(resolveWsEndpoint('', 'https://example.com/api/v1', '/ws/dashboard')).toBe('wss://example.com/ws/dashboard')
  })

  it('相对 API 地址默认使用当前源', () => {
    expect(resolveWsEndpoint('', '/api/v1', '/ws/dashboard')).toBe('/ws/dashboard')
  })
})
