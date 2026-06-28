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
      title: '后端未连接',
      message: '无法连接本地后端，可能是 API 服务尚未启动。',
      endpoint: context.endpoint,
      suggestedAction:
        '启动 start_relief_story_agent.bat 或运行 relief-story-agent serve 后重试。',
      raw: redactSecretText(error.message),
    }
  }

  const message =
    error instanceof Error ? error.message : redactSecretText(safeJson(error))

  return {
    kind: 'unknown',
    title: '未知错误',
    message: redactSecretText(message),
    endpoint: context.endpoint,
    statusCode: context.statusCode,
    suggestedAction: '复制诊断信息，检查后端日志或契约字段。',
    raw: error,
  }
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
