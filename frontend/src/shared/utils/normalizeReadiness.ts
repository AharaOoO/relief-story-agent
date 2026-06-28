import type { ReadinessStatus } from '../contracts/readiness.contract'
import { sampleReadiness } from '../fixtures/sampleReadiness'

export function normalizeReadiness(
  value: Partial<ReadinessStatus> | undefined,
): ReadinessStatus {
  return {
    ready_for_configuration:
      value?.ready_for_configuration ??
      sampleReadiness.ready_for_configuration,
    ready_for_real_runs:
      value?.ready_for_real_runs ?? sampleReadiness.ready_for_real_runs,
    ready_for_release:
      value?.ready_for_release ?? sampleReadiness.ready_for_release,
    summary: value?.summary ?? sampleReadiness.summary,
    blockers: Array.isArray(value?.blockers)
      ? value.blockers
      : sampleReadiness.blockers,
    warnings: Array.isArray(value?.warnings)
      ? value.warnings
      : sampleReadiness.warnings,
    checks: Array.isArray(value?.checks) ? value.checks : sampleReadiness.checks,
  }
}
