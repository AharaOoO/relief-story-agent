export type UiErrorKind =
  | 'network_error'
  | 'api_error'
  | 'invalid_request'
  | 'configuration'
  | 'validation'
  | 'contract'
  | 'external'
  | 'permission'
  | 'cancelled'
  | 'unknown'

export type UiApiError = {
  kind: UiErrorKind
  title: string
  message: string
  statusCode?: number
  endpoint?: string
  requestId?: string
  raw?: unknown
  suggestedAction?: string
}
