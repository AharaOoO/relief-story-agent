import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { ReadinessPanel } from './ReadinessPanel'

vi.mock('../../../shared/hooks/useBackendHealth', () => ({
  useLocalReadiness: () => ({
    data: {
      ready_for_configuration: true,
      ready_for_real_runs: false,
      ready_for_release: false,
      summary: {
        real_run_blocking_count: 0,
        release_blocking_count: 1,
        warning_count: 1,
      },
      blockers: [],
      warnings: [
        {
          code: 'state_not_persistent',
          title: 'State directory is temporary',
          detail: 'Restart recovery evidence is weaker without a persistent state directory.',
        },
      ],
      checks: [],
    },
  }),
}))

describe('ReadinessPanel', () => {
  it('shows readiness warnings even when there are no blockers', () => {
    render(<ReadinessPanel />)

    expect(screen.getByText('State directory is temporary')).toBeInTheDocument()
    expect(
      screen.getByText(
        'Restart recovery evidence is weaker without a persistent state directory.',
      ),
    ).toBeInTheDocument()
  })
})
