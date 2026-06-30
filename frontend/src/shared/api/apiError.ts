import type { UiApiError } from '../contracts/error.contract'
import { safeJson } from '../utils/safeJson'

export function redactSecretText(value: string): string {
  return value
    .replace(
      /\b([A-Z0-9_]*API_KEY)\s*=\s*([^\s,"']+)/g,
      (_match, name: string) => `${name}=<redacted>`,
    )
    .replace(/\b(sk-[A-Za-z0-9_-]{8,})\b/g, '<redacted-key>')
}

export function normalizeApiError(
  error: unknown,
  context: { endpoint?: string; statusCode?: number } = {},
): UiApiError {
  if (isUiApiError(error)) {
    return {
      ...error,
      endpoint: error.endpoint ?? context.endpoint,
      statusCode: error.statusCode ?? context.statusCode,
      message: redactSecretText(error.message),
    }
  }

  if (error instanceof TypeError) {
    return {
      kind: 'network_error',
      title: '本地后端未连接',
      message: '无法连接本地后端，服务可能仍在启动或已经退出。',
      endpoint: context.endpoint,
      suggestedAction: '在高级设置的“诊断”页重启本地后端后再试。',
      raw: redactSecretText(error.message),
    }
  }

  const backendMessage = extractBackendMessage(error)
  if (backendMessage) {
    return {
      kind: context.statusCode === 422 ? 'validation' : 'api_error',
      title: context.statusCode === 422 ? '请求配置有误' : '后端操作失败',
      message: redactSecretText(backendMessage),
      endpoint: context.endpoint,
      statusCode: context.statusCode,
      suggestedAction: '根据提示修正配置，或打开高级设置检查密钥和工作流。',
      raw: error,
    }
  }

  const message = error instanceof Error
    ? error.message
    : redactSecretText(safeJson(error))

  return {
    kind: 'unknown',
    title: '未知错误',
    message: redactSecretText(message),
    endpoint: context.endpoint,
    statusCode: context.statusCode,
    suggestedAction: '打开高级设置检查诊断信息和本地后端日志。',
    raw: error,
  }
}

function extractBackendMessage(value: unknown): string {
  if (typeof value !== 'object' || value === null) return ''
  if ('message' in value && typeof value.message === 'string') return value.message
  if (!('detail' in value)) return ''
  const detail = value.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    return detail
      .map((item) => {
        if (typeof item === 'string') return item
        if (
          typeof item === 'object' &&
          item !== null &&
          'msg' in item &&
          typeof item.msg === 'string'
        ) return item.msg
        return ''
      })
      .filter(Boolean)
      .join('；')
  }
  if (
    typeof detail === 'object' &&
    detail !== null &&
    'message' in detail &&
    typeof detail.message === 'string'
  ) return detail.message
  return ''
}

function isUiApiError(value: unknown): value is UiApiError {
  return (
    typeof value === 'object' &&
    value !== null &&
    'kind' in value &&
    'title' in value &&
    'message' in value
  )
}
