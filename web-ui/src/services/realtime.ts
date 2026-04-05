import { ref, type Ref } from 'vue'

import { normalizeApiBaseUrl } from '@/api/baseUrl'

export type WsStatus = 'connected' | 'connecting' | 'disconnected'

type RealtimeHandler = (payload: any) => void

interface LogSubscribePayload {
  filters: {
    level?: string
    min_level?: string
    component?: string
    exclude_components?: string
    keyword?: string
    collector_id?: string
    run_id?: string
  }
  pageSize: number
}

function isAbsoluteHttpUrl(value: string): boolean {
  return value.startsWith('http://') || value.startsWith('https://')
}

function isAbsoluteWsUrl(value: string): boolean {
  return value.startsWith('ws://') || value.startsWith('wss://')
}

export function resolveWsEndpoint(rawWsUrl: string | undefined, rawApiBaseUrl: string | undefined, wsPath: string): string {
  const targetPath = wsPath.startsWith('/') ? wsPath : `/${wsPath}`
  const wsUrl = (rawWsUrl || '').trim()

  if (wsUrl) {
    if (isAbsoluteWsUrl(wsUrl)) {
      const parsed = new URL(wsUrl)
      return `${parsed.protocol}//${parsed.host}${targetPath}`
    }
    if (wsUrl.startsWith('/')) {
      return targetPath
    }
  }

  const apiBaseUrl = normalizeApiBaseUrl(rawApiBaseUrl)
  if (isAbsoluteHttpUrl(apiBaseUrl)) {
    const parsed = new URL(apiBaseUrl)
    const wsProtocol = parsed.protocol === 'https:' ? 'wss:' : 'ws:'
    return `${wsProtocol}//${parsed.host}${targetPath}`
  }

  return targetPath
}

function appendToken(url: string, token: string): string {
  if (!token) {
    return url
  }
  const separator = url.includes('?') ? '&' : '?'
  return `${url}${separator}token=${encodeURIComponent(token)}`
}

class BaseWsClient {
  protected ws: WebSocket | null = null
  protected reconnectTimer: number | null = null
  protected manualClose = false
  protected reconnectDelayMs = 1000
  protected readonly handlers = new Map<string, Set<RealtimeHandler>>()
  protected readonly wsPath: string
  protected readonly explicitWsUrl: string | undefined

  public readonly status: Ref<WsStatus> = ref('disconnected')

  constructor(wsPath: string) {
    this.wsPath = wsPath
    this.explicitWsUrl = import.meta.env.VITE_WS_URL
  }

  protected resolveUrl(): string {
    const apiBaseUrl = import.meta.env.VITE_API_BASE_URL
    return resolveWsEndpoint(this.explicitWsUrl, apiBaseUrl, this.wsPath)
  }

  protected onOpen(): void {
    // 子类按需重载
  }

  protected onClose(): void {
    // 子类按需重载
  }

  protected onMessage(_event: MessageEvent): void {
    // 子类按需重载
  }

  protected scheduleReconnect(): void {
    if (this.manualClose) {
      return
    }
    if (this.reconnectTimer) {
      return
    }
    this.reconnectTimer = window.setTimeout(() => {
      this.reconnectTimer = null
      this.connect()
    }, this.reconnectDelayMs)
    this.reconnectDelayMs = Math.min(this.reconnectDelayMs * 2, 10000)
  }

  public connect(force = false): void {
    if (this.ws && this.ws.readyState === WebSocket.OPEN && !force) {
      return
    }
    if (this.ws && this.ws.readyState === WebSocket.CONNECTING && !force) {
      return
    }

    const token = localStorage.getItem('api_token') || ''
    if (!token) {
      this.status.value = 'disconnected'
      return
    }

    if (force) {
      this.disconnect()
      this.manualClose = false
    }

    this.status.value = 'connecting'
    const wsUrl = appendToken(this.resolveUrl(), token)
    this.ws = new WebSocket(wsUrl)

    this.ws.onopen = () => {
      this.status.value = 'connected'
      this.reconnectDelayMs = 1000
      this.onOpen()
    }

    this.ws.onmessage = (event) => {
      this.onMessage(event)
    }

    this.ws.onerror = () => {
      this.status.value = 'disconnected'
    }

    this.ws.onclose = () => {
      this.status.value = 'disconnected'
      this.onClose()
      this.scheduleReconnect()
    }
  }

  public reconnect(): void {
    this.manualClose = false
    this.connect(true)
  }

  public disconnect(): void {
    this.manualClose = true
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer)
      this.reconnectTimer = null
    }
    if (this.ws) {
      this.ws.close()
      this.ws = null
    }
    this.status.value = 'disconnected'
  }

  public subscribe(eventType: string, handler: RealtimeHandler): () => void {
    if (!this.handlers.has(eventType)) {
      this.handlers.set(eventType, new Set())
    }
    const target = this.handlers.get(eventType)
    target?.add(handler)
    return () => {
      target?.delete(handler)
      if (target && target.size === 0) {
        this.handlers.delete(eventType)
      }
    }
  }

  protected emit(eventType: string, payload: any): void {
    this.handlers.get(eventType)?.forEach((handler) => handler(payload))
  }

  protected send(payload: Record<string, any>): void {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      return
    }
    this.ws.send(JSON.stringify(payload))
  }
}

class DashboardRealtimeClient extends BaseWsClient {
  private pingTimer: number | null = null

  constructor() {
    super('/ws/dashboard')
  }

  protected onOpen(): void {
    if (this.pingTimer) {
      clearInterval(this.pingTimer)
    }
    this.pingTimer = window.setInterval(() => {
      if (this.ws && this.ws.readyState === WebSocket.OPEN) {
        this.ws.send('ping')
      }
    }, 20000)
  }

  protected onClose(): void {
    if (this.pingTimer) {
      clearInterval(this.pingTimer)
      this.pingTimer = null
    }
  }

  protected onMessage(event: MessageEvent): void {
    if (typeof event.data !== 'string') {
      return
    }
    if (event.data === 'pong') {
      return
    }
    try {
      const message = JSON.parse(event.data)
      if (!message?.type) {
        return
      }
      this.emit(message.type, message)
    } catch {
      // 忽略无法解析的消息
    }
  }
}

class LogRealtimeClient extends BaseWsClient {
  private currentSubscription: LogSubscribePayload | null = null

  constructor() {
    super('/ws/logs')
  }

  protected onOpen(): void {
    if (this.currentSubscription) {
      this.send({
        type: 'subscribe',
        filters: this.currentSubscription.filters,
        pageSize: this.currentSubscription.pageSize,
      })
    }
  }

  protected onMessage(event: MessageEvent): void {
    if (typeof event.data !== 'string') {
      return
    }
    if (event.data === 'pong') {
      return
    }
    try {
      const message = JSON.parse(event.data)
      if (!message?.type) {
        return
      }
      this.emit(message.type, message)
    } catch {
      // 忽略无法解析的消息
    }
  }

  public subscribeLogs(payload: LogSubscribePayload): void {
    this.currentSubscription = payload
    this.connect()
    this.send({
      type: 'subscribe',
      filters: payload.filters,
      pageSize: payload.pageSize,
    })
  }

  public unsubscribeLogs(): void {
    this.currentSubscription = null
    this.send({ type: 'unsubscribe' })
    this.disconnect()
  }
}

export const dashboardRealtimeClient = new DashboardRealtimeClient()
export const logRealtimeClient = new LogRealtimeClient()
