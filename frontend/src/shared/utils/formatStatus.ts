import type { CommonStatus } from '../contracts/common.contract'

export type StatusTone = 'success' | 'warning' | 'danger' | 'info' | 'neutral'

const STATUS_LABELS: Record<CommonStatus, string> = {
  idle: '待命',
  checking: '检查中',
  ready: '就绪',
  blocked: '阻塞',
  warning: '警告',
  queued: '排队中',
  running: '运行中',
  paused: '已暂停',
  awaiting_approval: '待审查',
  completed: '已完成',
  failed: '失败',
  cancelled: '已取消',
  unknown: '未知',
}

const STATUS_TONES: Record<CommonStatus, StatusTone> = {
  idle: 'neutral',
  checking: 'info',
  ready: 'success',
  blocked: 'danger',
  warning: 'warning',
  queued: 'info',
  running: 'info',
  paused: 'neutral',
  awaiting_approval: 'warning',
  completed: 'success',
  failed: 'danger',
  cancelled: 'neutral',
  unknown: 'neutral',
}

const PIPELINE_STATUS_LABELS: Record<string, string> = {
  pending: '待命',
  waiting: '等待确认',
  skipped: '已跳过',
  succeeded: '已完成',
  partial_failed: '部分失败',
}

const PIPELINE_STATUS_TONES: Record<string, StatusTone> = {
  pending: 'neutral',
  waiting: 'warning',
  skipped: 'neutral',
  succeeded: 'success',
  partial_failed: 'danger',
}

function isKnownStatus(status: string): status is CommonStatus {
  return Object.hasOwn(STATUS_LABELS, status)
}

export function getStatusLabel(status: string): string {
  return isKnownStatus(status) ? STATUS_LABELS[status] : PIPELINE_STATUS_LABELS[status] ?? STATUS_LABELS.unknown
}

export function getStatusTone(status: string): StatusTone {
  return isKnownStatus(status) ? STATUS_TONES[status] : PIPELINE_STATUS_TONES[status] ?? STATUS_TONES.unknown
}
