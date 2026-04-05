function stripTrailingSlash(input: string): string {
  return input.replace(/\/+$/, '')
}

export function buildRandomProxyUrl(apiBaseUrl: string, origin: string): string {
  const normalizedApiBase = stripTrailingSlash(apiBaseUrl.trim())
  if (/^https?:\/\//i.test(normalizedApiBase)) {
    return `${normalizedApiBase}/random`
  }

  const basePath = normalizedApiBase.startsWith('/') ? normalizedApiBase : `/${normalizedApiBase}`
  return `${stripTrailingSlash(origin)}${basePath}/random`
}

export function appendTokenToUrl(url: string, token: string): string {
  const separator = url.includes('?') ? '&' : '?'
  return `${url}${separator}token=${encodeURIComponent(token)}`
}
