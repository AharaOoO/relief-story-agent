import { describe, expect, it } from 'vitest'
import { normalizeReadiness } from './normalizeReadiness'

describe('normalizeReadiness', () => {
  it('fills missing list fields when backend returns a partial contract', () => {
    const readiness = normalizeReadiness({
      ready_for_configuration: true,
      ready_for_real_runs: false,
      ready_for_release: false,
    })

    expect(readiness.blockers.length).toBeGreaterThan(0)
    expect(readiness.warnings.length).toBeGreaterThan(0)
    expect(readiness.checks.length).toBeGreaterThan(0)
  })
})
