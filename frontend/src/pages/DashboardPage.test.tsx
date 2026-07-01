import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import DashboardPage from './DashboardPage'

vi.mock('../features/workbench/workbench.api', () => ({
  createBatch: vi.fn(),
  createRun: vi.fn(),
  formatPreflightIssue: (issue: unknown) => typeof issue === 'string' ? issue : 'issue',
  listRuns: vi.fn().mockResolvedValue({
    total: 1,
    limit: 100,
    items: [
      { run_id: 'run-live', idea: '夜班热饮', status: 'running', current_stage: 'gpt_prompt_audit' },
    ],
  }),
  validateRun: vi.fn(),
}))

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <DashboardPage />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('DashboardPage recent tasks', () => {
  beforeEach(() => {
    window.localStorage.clear()
    window.reliefDesktop = undefined
    window.location.hash = ''
  })

  it('shows recent run status and current stage in user-facing Chinese', async () => {
    renderPage()

    expect(await screen.findByRole('link', { name: /夜班热饮/ })).toHaveTextContent('调味 · 提示词审查')
    expect(screen.getByText('运行中')).toBeInTheDocument()
    expect(screen.queryByText('gpt_prompt_audit')).not.toBeInTheDocument()
  })

  it('scrolls to the creation panel without changing the hash route', () => {
    renderPage()
    const scrollIntoView = vi.fn()
    const panel = document.getElementById('new-production')
    panel!.scrollIntoView = scrollIntoView

    fireEvent.click(screen.getByRole('button', { name: /开始一部新短剧/ }))
    fireEvent.click(screen.getByRole('button', { name: /开始创作/ }))

    expect(scrollIntoView).toHaveBeenCalledTimes(2)
    expect(window.location.hash).toBe('')
    expect(screen.queryByRole('link', { name: /开始一部新短剧/ })).not.toBeInTheDocument()
  })
})
