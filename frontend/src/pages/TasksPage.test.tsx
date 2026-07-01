import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import TasksPage from './TasksPage'
import { cancelBatch, pauseBatch, resumeBatch, retryBatch } from '../features/workbench/workbench.api'

let pauseBatchResult: Promise<unknown>

vi.mock('../features/workbench/workbench.api', () => ({
  listRuns: vi.fn().mockResolvedValue({ total: 0, limit: 100, items: [] }),
  listBatches: vi.fn().mockResolvedValue({
    total: 2,
    limit: 100,
    items: [
      { batch_id: 'batch-running', status: 'running', paused: false, item_count: 3, summary: { completed: 1, failed: 0 } },
      { batch_id: 'batch-paused', status: 'paused', paused: true, item_count: 3, summary: { completed: 1, failed: 1 } },
    ],
  }),
  pauseBatch: vi.fn(() => pauseBatchResult),
  resumeBatch: vi.fn().mockResolvedValue({ batch_id: 'batch-paused', status: 'running' }),
  cancelBatch: vi.fn().mockResolvedValue({ batch_id: 'batch-running', status: 'cancelled' }),
  retryBatch: vi.fn().mockResolvedValue({ batch_id: 'batch-paused', status: 'queued' }),
}))

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  return render(
    <MemoryRouter>
      <QueryClientProvider client={client}><TasksPage /></QueryClientProvider>
    </MemoryRouter>,
  )
}

describe('TasksPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    pauseBatchResult = Promise.resolve({ batch_id: 'batch-running', status: 'paused' })
  })

  it('controls running and paused batches through backend mutations', async () => {
    renderPage()

    fireEvent.click(await screen.findByRole('button', { name: '暂停 batch-running' }))
    await waitFor(() => expect(pauseBatch).toHaveBeenCalledWith('batch-running'))
    fireEvent.click(screen.getByRole('button', { name: '继续 batch-paused' }))
    await waitFor(() => expect(resumeBatch).toHaveBeenCalledWith('batch-paused'))
    fireEvent.click(screen.getByRole('button', { name: '重试 batch-paused' }))
    fireEvent.click(screen.getByRole('button', { name: '取消 batch-running' }))

    await waitFor(() => expect(retryBatch).toHaveBeenCalledWith('batch-paused'))
    await waitFor(() => expect(cancelBatch).toHaveBeenCalledWith('batch-running'))
  })

  it('shows the exact batch action while a control request is pending', async () => {
    pauseBatchResult = new Promise(() => undefined)
    renderPage()

    fireEvent.click(await screen.findByRole('button', { name: '暂停 batch-running' }))

    expect(await screen.findByRole('status')).toHaveTextContent('正在暂停 batch-running')
    expect(screen.getByRole('button', { name: '暂停 batch-running' })).toBeDisabled()
  })
})
