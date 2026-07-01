import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import AutopilotPage from './AutopilotPage'
import { fetchRunArtifacts } from '../features/workbench/workbench.api'

vi.mock('../features/workbench/workbench.api', () => ({
  approveRun: vi.fn(),
  cancelRun: vi.fn(),
  fetchProviderCatalog: vi.fn().mockResolvedValue({
    runninghub: {
      cn: { base_url: 'https://llm.runninghub.cn/v1', api_key_env: 'RUNNINGHUB_CN_API_KEY', stages: {} },
      ai: { base_url: 'https://llm.runninghub.ai/v1', api_key_env: 'RUNNINGHUB_AI_API_KEY', stages: {} },
    },
  }),
  fetchRun: vi.fn().mockResolvedValue({
    run_id: 'run-one',
    status: 'completed',
    current_stage: 'chief_screenwriter',
    idea: '海边便利店',
    request: {
      idea: '海边便利店',
      model_configs: {},
      prompt_profile: { stage_overrides: {} },
    },
  }),
  fetchRunArtifacts: vi.fn().mockResolvedValue([
    {
      id: 'chief-script',
      kind: 'json',
      name: 'script',
      path: 'D:/relief/runs/run-one/01_script.json',
    },
    {
      id: 'chief-preview',
      kind: 'image',
      name: 'chief_screenwriter_preview.png',
      path: 'https://example.com/preview.png',
    },
  ]),
  fetchRunEvents: vi.fn().mockResolvedValue({ run_id: 'run-one', after: 0, next_cursor: 0, is_terminal: true, events: [] }),
  fetchTimeline: vi.fn().mockResolvedValue([
    { stage_id: 'chief_screenwriter', status: 'completed' },
  ]),
  refreshRunComfyUI: vi.fn(),
  retryRun: vi.fn(),
}))

function renderPage() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={['/run/run-one']}>
        <Routes>
          <Route path="/run/:runId" element={<AutopilotPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('AutopilotPage', () => {
  const openPath = vi.fn().mockResolvedValue({ opened: true })

  beforeEach(() => {
    vi.clearAllMocks()
    window.reliefDesktop = {
      platform: 'win32',
      shell: 'electron',
      getRuntimeConfig: vi.fn().mockResolvedValue({}),
      openPath,
    } as unknown as typeof window.reliefDesktop
  })

  it('opens local stage artifacts and their containing folder from the live run page', async () => {
    renderPage()

    expect(await screen.findByText('script')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: '打开文件 script' }))
    fireEvent.click(screen.getByRole('button', { name: '打开所在目录 script' }))

    await waitFor(() => expect(openPath).toHaveBeenCalledWith('D:/relief/runs/run-one/01_script.json'))
    expect(openPath).toHaveBeenCalledWith('D:/relief/runs/run-one')
  })

  it('keeps remote stage artifact URLs reachable from the live run page', async () => {
    renderPage()

    const link = await screen.findByRole('link', { name: '打开链接 chief_screenwriter_preview.png' })
    expect(link).toHaveAttribute('href', 'https://example.com/preview.png')
    expect(link).toHaveAttribute('target', '_blank')
  })

  it('requests run artifacts for the selected run', async () => {
    renderPage()

    await waitFor(() => expect(fetchRunArtifacts).toHaveBeenCalledWith('run-one'))
  })
})
