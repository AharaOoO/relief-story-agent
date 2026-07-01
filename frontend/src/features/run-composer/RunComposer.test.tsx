import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { RunComposer } from './RunComposer'
import { createRun, validateRun } from '../workbench/workbench.api'

vi.mock('../workbench/workbench.api', () => ({
  createBatch: vi.fn(),
  createRun: vi.fn().mockResolvedValue({ run_id: 'run-auto-detected' }),
  formatPreflightIssue: (issue: unknown) => typeof issue === 'string' ? issue : 'issue',
  validateRun: vi.fn(),
}))

function renderComposer() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <RunComposer />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('RunComposer input mode detection', () => {
  beforeEach(() => {
    window.localStorage.clear()
    window.reliefDesktop = undefined
  })

  it('recognizes pasted scripts without requiring the user to choose script mode', () => {
    renderComposer()

    fireEvent.change(screen.getByLabelText('故事灵感、剧本或创作要求'), {
      target: {
        value: '第1场 夜 内 便利店\n店员：你又加班到这个点？\n男人低头笑了一下，把热饮握在手心。',
      },
    })

    expect(screen.getByLabelText('输入类型')).toHaveValue('script')
  })

  it('recognizes creation requirements and short ideas from the merged input box', () => {
    renderComposer()
    const input = screen.getByLabelText('故事灵感、剧本或创作要求')

    fireEvent.change(input, {
      target: { value: '要求：低刺激、城市夜景、不要旁白，受众是下班后的年轻人。' },
    })
    expect(screen.getByLabelText('输入类型')).toHaveValue('requirements')

    fireEvent.change(input, {
      target: { value: '一个深夜下班的人，在便利店门口被一杯热饮安慰。' },
    })
    expect(screen.getByLabelText('输入类型')).toHaveValue('idea')
  })

  it('respects a manually selected mode after the user overrides detection', () => {
    renderComposer()

    fireEvent.change(screen.getByLabelText('输入类型'), { target: { value: 'idea' } })
    fireEvent.change(screen.getByLabelText('故事灵感、剧本或创作要求'), {
      target: {
        value: '第1场 夜 内 便利店\n店员：你又加班到这个点？\n男人低头笑了一下，把热饮握在手心。',
      },
    })

    expect(screen.getByLabelText('输入类型')).toHaveValue('idea')
  })

  it('sends the detected mode in the backend run request payload', async () => {
    renderComposer()

    fireEvent.change(screen.getByLabelText('故事灵感、剧本或创作要求'), {
      target: { value: '要求：低刺激、城市夜景、不要旁白，受众是下班后的年轻人。' },
    })
    fireEvent.click(screen.getByRole('button', { name: /一键开始生成/ }))

    await waitFor(() => expect(createRun).toHaveBeenCalled())
    expect(vi.mocked(createRun).mock.calls[0]?.[0].input_spec.mode).toBe('requirements')
  })

  it('treats a legacy passed preflight response as ready', async () => {
    vi.mocked(validateRun).mockResolvedValue({
      passed: true,
      blockers: [],
      warnings: [],
      checks: [{ name: 'model_environment', status: 'passed', message: 'ok' }],
    } as Awaited<ReturnType<typeof validateRun>>)
    renderComposer()

    fireEvent.click(screen.getByRole('button', { name: /预检/ }))

    expect(await screen.findByText(/预检通过/)).toBeInTheDocument()
    expect(screen.queryByText(/还需要处理/)).not.toBeInTheDocument()
  })
})
