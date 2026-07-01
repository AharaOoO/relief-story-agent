import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { RunComposer } from './RunComposer'
import { createBatch, createRun, validateRun } from '../workbench/workbench.api'
import { WorkbenchContext } from '../../app/workbench/workbench.context'

vi.mock('../workbench/workbench.api', () => ({
  createBatch: vi.fn(),
  createRun: vi.fn().mockResolvedValue({ run_id: 'run-auto-detected' }),
  formatPreflightIssue: (issue: unknown) => typeof issue === 'string' ? issue : 'issue',
  validateRun: vi.fn(),
}))

function renderComposer(options: { openSettings?: () => void } = {}) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <WorkbenchContext.Provider value={{ openSettings: options.openSettings ?? vi.fn() }}>
          <RunComposer />
        </WorkbenchContext.Provider>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('RunComposer input mode detection', () => {
  beforeEach(() => {
    window.localStorage.clear()
    window.reliefDesktop = undefined
    vi.mocked(createRun).mockReset()
    vi.mocked(createRun).mockResolvedValue({ run_id: 'run-auto-detected', status: 'queued', current_stage: 'chief_screenwriter' })
    vi.mocked(createBatch).mockReset()
    vi.mocked(createBatch).mockResolvedValue({ batch_id: 'batch-auto-detected', status: 'queued' })
    vi.mocked(validateRun).mockReset()
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

  it('shows backend preflight blockers when create rejects with validation detail', async () => {
    vi.mocked(createRun).mockRejectedValueOnce({
      kind: 'api_error',
      title: '后端操作失败',
      message: 'preflight validation failed',
      raw: {
        detail: {
          message: 'preflight validation failed',
          validation: {
            passed: false,
            blockers: ['Missing model API key environment variable(s).'],
            warnings: [],
            checks: [],
          },
        },
      },
    })
    renderComposer()

    fireEvent.click(screen.getByRole('button', { name: /一键开始生成/ }))

    expect(await screen.findByText(/还需要处理/)).toBeInTheDocument()
    expect(screen.getByText('Missing model API key environment variable(s).')).toBeInTheDocument()
  })

  it('summarizes failed batch preflight items when batch create rejects with validation detail', async () => {
    vi.mocked(createBatch).mockRejectedValueOnce({
      kind: 'api_error',
      title: '后端操作失败',
      message: 'preflight validation failed',
      raw: {
        detail: {
          message: 'preflight validation failed',
          validation: {
            passed: false,
            summary: { total: 2, passed: 1, failed: 1 },
            items: [
              { index: 0, passed: true, checks: [] },
              {
                index: 1,
                passed: false,
                checks: [{ name: 'output_root', status: 'failed', message: 'output_root is not writable.' }],
              },
            ],
          },
        },
      },
    })
    renderComposer()

    fireEvent.click(screen.getByLabelText('增加任务'))
    fireEvent.click(screen.getByRole('button', { name: /批量开始 2 个任务/ }))

    expect(await screen.findByText(/还需要处理/)).toBeInTheDocument()
    expect(screen.getByText('任务 2：output_root is not writable.')).toBeInTheDocument()
  })

  it('shows suggested preflight actions and opens advanced settings from the blocker panel', async () => {
    const openSettings = vi.fn()
    vi.mocked(validateRun).mockResolvedValue({
      passed: false,
      blockers: [{ check: 'model_environment', message: 'Missing RunningHub API key.' }],
      warnings: [],
      suggested_actions: [
        {
          code: 'configure_model_environment',
          label: '配置模型密钥',
          description: '在高级设置里保存 RunningHub API key。',
        },
      ],
      checks: [],
    } as Awaited<ReturnType<typeof validateRun>>)
    renderComposer({ openSettings })

    fireEvent.click(screen.getByRole('button', { name: /预检/ }))

    expect(await screen.findByText('配置模型密钥')).toBeInTheDocument()
    expect(screen.getByText('在高级设置里保存 RunningHub API key。')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: '打开高级设置' }))
    expect(openSettings).toHaveBeenCalledTimes(1)
  })
})
