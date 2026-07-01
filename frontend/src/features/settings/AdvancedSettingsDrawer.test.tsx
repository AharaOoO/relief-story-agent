import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { AdvancedSettingsDrawer } from './AdvancedSettingsDrawer'
import { analyzeComfyWorkflow, connectComfyUI, diagnoseRunConfiguration } from '../workbench/workbench.api'

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
})
