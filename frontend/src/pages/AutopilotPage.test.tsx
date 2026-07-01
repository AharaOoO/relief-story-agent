import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import AutopilotPage from './AutopilotPage'
import { fetchRun, fetchRunArtifacts, retryRun } from '../features/workbench/workbench.api'
import type { RunRequestPayload } from '../features/run-composer/runRequest.builder'

vi.mock('../features/workbench/workbench.api', () => ({
  approveRun: vi.fn(),
  cancelRun: vi.fn(),
  fetchProviderCatalog: vi.fn().mockResolvedValue({
    runninghub: {
      cn: { base_url: 'https://llm.runninghub.cn/v1', api_key_env: 'RUNNINGHUB_CN_SHARED_API_KEY', stages: {} },
      ai: { base_url: 'https://llm.runninghub.ai/v1', api_key_env: 'RUNNINGHUB_AI_SHARED_API_KEY', stages: {} },
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

function renderSetupPage() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={['/autopilot']}>
        <Routes>
          <Route path="/autopilot" element={<AutopilotPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

function makeRun(overrides: Partial<Awaited<ReturnType<typeof fetchRun>>> = {}): Awaited<ReturnType<typeof fetchRun>> {
  return {
    run_id: 'run-one',
    status: 'completed',
    current_stage: 'chief_screenwriter',
    idea: 'beach convenience store',
    request: {
      idea: 'beach convenience store',
      model_configs: {},
      prompt_profile: { stage_overrides: {} },
    } as unknown as RunRequestPayload,
    ...overrides,
  }
}

describe('AutopilotPage', () => {
  const openPath = vi.fn().mockResolvedValue({ opened: true })

  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(fetchRun).mockResolvedValue(makeRun())
    vi.mocked(fetchRunArtifacts).mockResolvedValue([
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
    ])
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

  it('switches the setup workspace between configurable G2 and later automatic stages', async () => {
    const { container } = renderSetupPage()

    await waitFor(() => expect(container.querySelector('.stage-big-number')).toHaveTextContent('01'))
    const stageButtons = Array.from(container.querySelectorAll<HTMLButtonElement>('.stage-rail button'))
    expect(stageButtons).toHaveLength(10)

    fireEvent.click(stageButtons[7])
    expect(container.querySelector('.stage-big-number')).toHaveTextContent('08')
    expect(screen.getByRole('button', { name: '国内站 .cn' })).toBeInTheDocument()
    expect(container.querySelector('.stage-automatic-panel')).not.toBeInTheDocument()

    fireEvent.click(stageButtons[8])
    expect(container.querySelector('.stage-big-number')).toHaveTextContent('09')
    expect(container.querySelector('.stage-automatic-panel')).toBeInTheDocument()

    fireEvent.click(stageButtons[9])
    expect(container.querySelector('.stage-big-number')).toHaveTextContent('10')
  })

  it('opens a live run focused on the backend current stage', async () => {
    vi.mocked(fetchRun).mockResolvedValue(makeRun({
      status: 'running',
      current_stage: 'gpt_prompt_audit',
    }))
    vi.mocked(fetchRunArtifacts).mockResolvedValue([
      {
        id: 'chief-script',
        kind: 'json',
        name: 'script',
        path: 'D:/relief/runs/run-one/01_script.json',
      },
      {
        id: 'audit-report',
        kind: 'prompt_audit',
        name: 'audit.json',
        path: 'D:/relief/runs/run-one/05_audit.json',
      },
    ])

    renderPage()

    expect(await screen.findByText('audit.json')).toBeInTheDocument()
    expect(screen.getAllByText('运行中').length).toBeGreaterThan(0)
    expect(screen.getByText('调味 · 提示词审查')).toBeInTheDocument()
    expect(screen.queryByText('script')).not.toBeInTheDocument()
  })

  it('lets the user return to the live current stage after inspecting another stage', async () => {
    vi.mocked(fetchRun).mockResolvedValue(makeRun({
      status: 'running',
      current_stage: 'gpt_prompt_audit',
    }))
    vi.mocked(fetchRunArtifacts).mockResolvedValue([
      {
        id: 'chief-script',
        kind: 'json',
        name: 'script',
        path: 'D:/relief/runs/run-one/01_script.json',
      },
      {
        id: 'audit-report',
        kind: 'prompt_audit',
        name: 'audit.json',
        path: 'D:/relief/runs/run-one/05_audit.json',
      },
    ])

    renderPage()

    expect(await screen.findByText('audit.json')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /备料/ }))
    expect(await screen.findByText('script')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: '回到当前工序' }))

    expect(await screen.findByText('audit.json')).toBeInTheDocument()
    expect(screen.queryByText('script')).not.toBeInTheDocument()
  })

  it('edits the failed G2 stage and retries with the recovery override', async () => {
    vi.mocked(fetchRun).mockResolvedValue(makeRun({
      status: 'failed',
      current_stage: 'failed',
      failed_stage: 'four_grid_asset',
      request: {
        idea: 'failed grid',
        model_configs: {},
        prompt_profile: { stage_overrides: {} },
        comfyui: {
          grid_image: {
            provider: 'runninghub_image_task',
            runninghub_site: 'ai',
            model: 'rhart-image-g-2',
            aspect_ratio: '16:9',
            resolution: '2k',
            quality: 'high',
          },
        },
      } as unknown as RunRequestPayload,
    }))

    renderPage()

    expect(await screen.findByRole('heading', { name: '四宫格参考图' })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: '国内站 .cn' }))
    fireEvent.click(screen.getByRole('button', { name: '应用修改并重试本工序' }))

    await waitFor(() => expect(retryRun).toHaveBeenCalledWith('run-one', {
      from_stage: 'four_grid_asset',
      grid_image_override: {
        runninghub_site: 'cn',
        aspect_ratio: '16:9',
        resolution: '2k',
      },
    }))
  })

  it('can retry the failed G2 stage with its original frozen configuration', async () => {
    vi.mocked(fetchRun).mockResolvedValue(makeRun({
      status: 'failed',
      current_stage: 'failed',
      failed_stage: 'four_grid_asset',
      request: {
        idea: 'failed grid',
        model_configs: {},
        prompt_profile: { stage_overrides: {} },
        comfyui: {
          grid_image: {
            provider: 'runninghub_image_task',
            runninghub_site: 'ai',
            model: 'rhart-image-g-2',
            aspect_ratio: '9:16',
            resolution: '1k',
            quality: 'high',
          },
        },
      } as unknown as RunRequestPayload,
    }))

    renderPage()
    fireEvent.click(await screen.findByRole('button', { name: '按原配置重试' }))

    await waitFor(() => expect(retryRun).toHaveBeenCalledWith('run-one', {
      from_stage: 'four_grid_asset',
    }))
  })
})
