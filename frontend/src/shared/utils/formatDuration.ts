export function formatDuration(seconds?: number): string {
  if (seconds == null || Number.isNaN(seconds)) return '未估算'
  if (seconds < 60) return `${Math.round(seconds)} 秒`
  const minutes = Math.floor(seconds / 60)
  const remain = Math.round(seconds % 60)
  return `${minutes} 分 ${remain} 秒`
}
