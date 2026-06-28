import type { CommonStatus } from '../../../shared/contracts/common.contract'

export type BatchSummary = {
  batch_id: string
  status: CommonStatus
  total: number
  completed: number
  failed: number
  awaiting_approval: number
}
