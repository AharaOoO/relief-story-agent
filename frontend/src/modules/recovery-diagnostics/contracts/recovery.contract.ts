export type RecoveryGroup =
  | 'publish_ready'
  | 'auto_recoverable'
  | 'manual_review_required'
  | 'wait_required'
  | 'blocked'

export type RecoveryTarget = {
  run_id: string
  failed_stage: string
  error_kind: string
  group: RecoveryGroup
}
