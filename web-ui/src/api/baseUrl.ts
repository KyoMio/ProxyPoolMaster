const DEFAULT_API_BASE_URL = '/api/v1'

export function normalizeApiBaseUrl(rawBaseUrl?: string): string {
  const trimmed = (rawBaseUrl ?? '').trim()
  if (!trimmed) {
    return DEFAULT_API_BASE_URL
  }

  const normalized = trimmed.replace(/\/+$/, '')

  if (normalized.endsWith('/api/v1')) {
    return normalized
  }

  if (normalized.endsWith('/api')) {
    return `${normalized}/v1`
  }

  return `${normalized}/api/v1`
}
