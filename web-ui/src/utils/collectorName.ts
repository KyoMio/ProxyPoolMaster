export const COLLECTOR_NAME_RULE_HINT = '名称需为 3-40 位，仅允许小写字母、数字、下划线，且必须以字母开头'

const COLLECTOR_NAME_PATTERN = /^[a-z][a-z0-9_]{2,39}$/

export const validateCollectorName = (name: string): string | null => {
  const trimmed = name.trim()
  if (!trimmed) {
    return '请输入收集器名称'
  }
  if (!/^[a-z0-9_]+$/.test(trimmed)) {
    return COLLECTOR_NAME_RULE_HINT
  }
  if (!/^[a-z]/.test(trimmed)) {
    return '名称必须以小写字母开头'
  }
  if (!COLLECTOR_NAME_PATTERN.test(trimmed)) {
    return COLLECTOR_NAME_RULE_HINT
  }
  return null
}
