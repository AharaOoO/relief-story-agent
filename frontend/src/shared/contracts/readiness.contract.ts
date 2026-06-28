export type ReadinessCheck = {
  name: string
  status: 'passed' | 'failed' | 'warning' | 'skipped' | 'unknown'
  detail?: string
}

export type ReadinessBlocker = {
  code: string
  title: string
  detail: string
  suggested_action?: string
}

export type ReadinessWarning = {
  code: string
  title: string
  detail: string
}

export type ReadinessStatus = {
  ready_for_configuration: boolean
  ready_for_real_runs: boolean
  ready_for_release: boolean
  summary?: {
    real_run_blocking_count?: number
    release_blocking_count?: number
    warning_count?: number
  }
  blockers: ReadinessBlocker[]
  warnings: ReadinessWarning[]
  checks: ReadinessCheck[]
}
