import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { AdvancedSettingsDrawer } from './AdvancedSettingsDrawer'
import { analyzeComfyWorkflow, connectComfyUI, diagnoseRunConfiguration } from '../workbench/workbench.api'
import { useRunDraft } from '../run-composer/runDraft.store'

vi.mock('../../shared/hooks/useBackendHealth', () => ({
  useBackendHealth: () => ({ isSuccess: true, isLoading: false, refetch: vi.fn() }),
}))

vi.mock('../workbench/workbench.api', async (importOriginal) => {
  const original = await importOriginal<typeof import('../workbench/workbench.api')>()
  return {
    ...original,
    analyzeComfyWorkflow: vi.fn().mockResolvedValue({ workflow_format: 'litegraph', node_count: 60, adapter_mode: 'litegraph_ltx_auto_injection' }),
    connectComfyUI: vi.fn().mockResolvedValue({ connected: true, ready: true, queue: { running: 0, pending: 0 } }),
    diagnoseRunConfiguration: vi.fn().mockResolvedValue({ ready: true, summary: { passed: 8, warning: 1, failed: 0 }, suggested_actions: [] }),
    listPromptProfiles: vi.fn().mockResolvedValue({ items: [] }),
  }
})

describe('AdvancedSettingsDrawer', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    window.localStorage.clear()
    useRunDraft.getState().resetDraft()
    window.reliefDesktop = {
      platform: 'win32',
      shell: 'electron',
      getRuntimeConfig: vi.fn().mockResolvedValue({ comfyui_endpoint: 'http://127.0.0.1:8188', workflow_path: 'D:/workflow.json' }),
      saveRuntimeConfig: vi.fn().mockResolvedValue({ config: {}, handshake: {} }),
      getSecretStatus: vi.fn().mockResolvedValue({}),
      saveSecret: vi.fn(),
      deleteSecret: vi.fn(),
      pickWorkflow: vi.fn(),
      pickScript: vi.fn(),
      pickDirectory: vi.fn(),
      getPathForFile: vi.fn(),
      openPath: vi.fn(),
      restartBackend: vi.fn(),
      getHandshake: vi.fn(),
    } as unknown as typeof window.reliefDesktop
  })

  it('offers all six advanced groups and verifies the selected workflow', async () => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(<QueryClientProvider client={client}><AdvancedSettingsDrawer open onClose={vi.fn()} /></QueryClientProvider>)

    for (const name of ['模型与密钥', '提示词模板', 'ComfyUI', '图像生成', '执行与存储', '诊断']) {
      expect(screen.getByRole('tab', { name: new RegExp(name) })).toBeInTheDocument()
    }

    fireEvent.click(screen.getByRole('tab', { name: /ComfyUI/ }))
    fireEvent.click(await screen.findByRole('button', { name: '分析并测试连接' }))

    await waitFor(() => expect(analyzeComfyWorkflow).toHaveBeenCalledWith('http://127.0.0.1:8188', 'D:/workflow.json'))
    expect(connectComfyUI).toHaveBeenCalledWith('http://127.0.0.1:8188', 'D:/workflow.json')
    expect((await screen.findAllByText(/工作流可用/)).length).toBeGreaterThan(0)
  })

  it('runs deep configuration diagnosis from the diagnostics tab', async () => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(<QueryClientProvider client={client}><AdvancedSettingsDrawer open onClose={vi.fn()} /></QueryClientProvider>)

    fireEvent.click(screen.getByRole('tab', { name: /诊断/ }))
    fireEvent.click(await screen.findByRole('button', { name: '运行深度诊断' }))

    await waitFor(() => expect(diagnoseRunConfiguration).toHaveBeenCalledTimes(1))
    expect(await screen.findByText('深度诊断通过')).toBeInTheDocument()
    expect(screen.getByText('通过 8 · 警告 1 · 失败 0')).toBeInTheDocument()
  })

  it('opens directly on the requested settings group', () => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(<QueryClientProvider client={client}><AdvancedSettingsDrawer open initialTab="comfyui" onClose={vi.fn()} /></QueryClientProvider>)

    expect(screen.getByRole('tab', { name: /ComfyUI/ })).toHaveAttribute('aria-selected', 'true')
    expect(screen.getByRole('button', { name: '分析并测试连接' })).toBeInTheDocument()
  })

  it('changes only the dedicated G2 image site from image settings', () => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(<QueryClientProvider client={client}><AdvancedSettingsDrawer open initialTab="image" onClose={vi.fn()} /></QueryClientProvider>)

    fireEvent.click(screen.getByRole('button', { name: '国际站 .ai' }))

    expect(useRunDraft.getState().draft.gridImageSite).toBe('ai')
    expect(useRunDraft.getState().draft.runninghubSite).toBe('ai')
  })

  it('accepts exactly one workflow JSON file from drag and drop', async () => {
    window.reliefDesktop = {
      ...window.reliefDesktop,
      getRuntimeConfig: vi.fn().mockResolvedValue({ comfyui_endpoint: 'http://127.0.0.1:8188', workflow_path: '' }),
      getPathForFile: vi.fn().mockReturnValue('D:/ComfyUI/workflows/ltx23.json'),
    } as unknown as typeof window.reliefDesktop
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(<QueryClientProvider client={client}><AdvancedSettingsDrawer open initialTab="comfyui" onClose={vi.fn()} /></QueryClientProvider>)

    const dropZone = await screen.findByText('拖入工作流 JSON，或点击上方文件按钮')
    fireEvent.drop(dropZone, {
      dataTransfer: {
        files: [new File(['{}'], 'ltx23.json', { type: 'application/json' })],
      },
    })

    expect(screen.getByDisplayValue('D:/ComfyUI/workflows/ltx23.json')).toBeInTheDocument()
  })

  it('rejects multiple workflow files instead of silently choosing one', async () => {
    window.reliefDesktop = {
      ...window.reliefDesktop,
      getRuntimeConfig: vi.fn().mockResolvedValue({ comfyui_endpoint: 'http://127.0.0.1:8188', workflow_path: '' }),
      getPathForFile: vi.fn().mockReturnValue('D:/ComfyUI/workflows/first.json'),
    } as unknown as typeof window.reliefDesktop
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(<QueryClientProvider client={client}><AdvancedSettingsDrawer open initialTab="comfyui" onClose={vi.fn()} /></QueryClientProvider>)

    const dropZone = await screen.findByText('拖入工作流 JSON，或点击上方文件按钮')
    fireEvent.drop(dropZone, {
      dataTransfer: {
        files: [
          new File(['{}'], 'first.json', { type: 'application/json' }),
          new File(['{}'], 'second.json', { type: 'application/json' }),
        ],
      },
    })

    expect(await screen.findByRole('status')).toHaveTextContent('一次只能拖入一个工作流 JSON 文件。')
    expect(screen.queryByDisplayValue('D:/ComfyUI/workflows/first.json')).not.toBeInTheDocument()
  })
})
