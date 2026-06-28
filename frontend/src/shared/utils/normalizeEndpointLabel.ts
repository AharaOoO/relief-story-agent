export function normalizeEndpointLabel(endpoint?: string): string {
  if (!endpoint) return '未配置'
  return endpoint.replace(/^https?:\/\//, '').replace(/\/$/, '')
}
