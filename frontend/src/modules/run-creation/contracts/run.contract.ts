import type { GenerationMode } from '../../../shared/contracts/common.contract'

export type RunRequest = {
  idea: string
  generation_mode: GenerationMode
  approval_mode: 'manual' | 'auto_after_audit_pass'
  duration_seconds: number
  dry_run: boolean
}

export type PreflightResult = {
  ready: boolean
  blockers: string[]
  warnings: string[]
}
