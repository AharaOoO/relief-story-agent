export function getPollingInterval(status?: string): false | number {
  if (!status) return false
  if (status === 'queued' || status === 'running' || status === 'awaiting_approval') {
    return 3_000
  }
  if (status === 'paused') return 5_000
  return false
}
