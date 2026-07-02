import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import type { ComponentProps } from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { StageWorkspace } from './StageWorkspace'
import { useRunDraft } from '../run-composer/runDraft.store'
import type { RunRequestPayload } from '../run-composer/runRequest.builder'
import { fetchProviderCatalog, type ProviderCatalog } from '../workbench/workbench.api'
import type { RecoveryDraft } from './recoveryDraft'

vi.mock('../workbench/workbench.api', () => ({ fetchProviderCatalog: vi.fn() }))

const catalog: ProviderCatalog = {
  runninghub: {
    cn: {
      base_url: 'https://llm.runninghub.cn/v1',
      api_key_env: 'RUNNINGHUB_CN_SHARED_API_KEY',
      models: ['glm-5.2', 'qwen/qwen3.7-plus', 'deepseek/deepseek-v4-pro'],
      recommended_by_stage: { chief_screenwriter: ['qwen/qwen3.7-plus'], quality_gate: ['glm-5.2'] },
      source_url: 'https://www.runninghub.cn/call-api/llm/models',
      snapshot_date: '2026-07-02',
    },
    ai: {
      base_url: 'https://llm.runninghub.ai/v1',
      api_key_env: 'RUNNINGHUB_AI_SHARED_API_KEY',
      models: ['google/gemini-3.5-flash', 'openai/gpt-5.5', 'anthropic/claude-sonnet-5'],
      recommended_by_stage: { chief_screenwriter: ['google/gemini-3.5-flash'], quality_gate: ['openai/gpt-5.5'] },
      source_url: 'https://www.runninghub.ai/call-api/llm/models',
      snapshot_date: '2026-07-02',
    },
  },
}

function renderWorkspace(stageId: string, props: Partial<ComponentProps<typeof StageWorkspace>> = {}) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(<QueryClientProvider client={client}><StageWorkspace stageId={stageId} {...props} /></QueryClientProvider>)
}

function clickRunningHubMode() {
  fireEvent.click(screen.getByRole('button', { name: 'RunningHub 企业模型 API' }))
}

function recoveryDraft(): RecoveryDraft {
  return {
    stageModels: {
      chief_screenwriter: { provider_mode: 'runninghub', runninghub_site: 'cn', model: 'qwen/qwen3.7-plus' },
    },
    stagePrompts: { chief_screenwriter: '恢复提示词' },
    gridImage: { runninghub_site: 'ai', aspect_ratio: '9:16', resolution: '1k' },
    comfyui: {
      endpoint: 'http://127.0.0.1:8188',
      workflow_api_path: 'D:/workflow.json',
      output_timeout_seconds: 600,
    },
  }
}

beforeEach(() => {
  window.localStorage.clear()
  window.reliefDesktop = undefined
  useRunDraft.getState().resetDraft()
  vi.mocked(fetchProviderCatalog).mockResolvedValue(catalog)
})

describe('StageWorkspace run snapshot', () => {
  it('lets stage 8 select the domestic G2 site independently', () => {
    renderWorkspace('four_grid_asset')

    expect(screen.getByRole('button', { name: '国内站 .cn' })).toHaveClass('is-active')
    fireEvent.click(screen.getByRole('button', { name: '国际站 .ai' }))

    expect(useRunDraft.getState().draft.gridImageSite).toBe('ai')
    expect(screen.getByText('RUNNINGHUB_AI_API_KEY')).toBeInTheDocument()
  })

  it('shows the frozen G2 site and image settings for an existing run', () => {
    const request = {
      comfyui: { grid_image: { provider: 'runninghub_image_task', runninghub_site: 'ai', model: 'rhart-image-g-2', aspect_ratio: '9:16', resolution: '1k', quality: 'high' } },
    } as unknown as RunRequestPayload

    renderWorkspace('four_grid_asset', { readOnly: true, runRequest: request })

    expect(screen.getByRole('button', { name: '国际站 .ai' })).toHaveClass('is-active')
    expect(screen.getByRole('button', { name: '国际站 .ai' })).toBeDisabled()
    expect(screen.getByDisplayValue('竖屏 9:16')).toBeDisabled()
    expect(screen.getByDisplayValue('1K 快速')).toBeDisabled()
  })

  it('edits an isolated recovery draft without changing the new-run draft', () => {
    const onChange = vi.fn()
    const value = recoveryDraft()
    renderWorkspace('four_grid_asset', { recovery: { value, onChange } })

    fireEvent.click(screen.getByRole('button', { name: '国内站 .cn' }))

    expect(onChange).toHaveBeenCalledWith({
      ...value,
      gridImage: { runninghub_site: 'cn', aspect_ratio: '9:16', resolution: '1k' },
    })
    expect(useRunDraft.getState().draft.gridImageSite).toBe('cn')
    expect(screen.getByText('恢复编辑')).toBeInTheDocument()
  })

  it('shows the frozen model and prompt from the run', async () => {
    const request = {
      model_configs: { chief_screenwriter: { provider_mode: 'runninghub', runninghub_site: 'cn', model: 'qwen/qwen3.7-plus' } },
      prompt_profile: { profile_id: 'profile-one', profile_version: 3, stage_overrides: { chief_screenwriter: '真实任务冻结提示词' } },
    } as unknown as RunRequestPayload

    renderWorkspace('chief_screenwriter', { readOnly: true, runRequest: request, promptSnapshot: { chief_screenwriter: '真实任务冻结提示词' } })

    expect(await screen.findByRole('combobox', { name: '本工序模型' })).toBeDisabled()
    expect(screen.getByRole('combobox', { name: '本工序模型' })).toHaveTextContent('qwen/qwen3.7-plus')
    expect(screen.getByDisplayValue('真实任务冻结提示词')).toBeDisabled()
  })

  it('uses the complete selected-site catalog in the custom model picker', async () => {
    renderWorkspace('quality_gate')
    clickRunningHubMode()

    await waitFor(() => expect(screen.getByRole('button', { name: /国内站/ })).not.toBeDisabled())
    fireEvent.click(screen.getByRole('button', { name: /国内站/ }))
    fireEvent.click(screen.getByRole('combobox', { name: '本工序模型' }))

    expect(screen.getByRole('option', { name: 'glm-5.2' })).toBeInTheDocument()
    expect(screen.getByRole('option', { name: 'deepseek/deepseek-v4-pro' })).toBeInTheDocument()
    expect(screen.queryByRole('option', { name: 'anthropic/claude-sonnet-5' })).not.toBeInTheDocument()
  })

  it('switches to the international catalog without mixing domestic-only options', async () => {
    renderWorkspace('quality_gate')
    clickRunningHubMode()

    await waitFor(() => expect(screen.getByRole('button', { name: /国际站/ })).not.toBeDisabled())
    fireEvent.click(screen.getByRole('button', { name: /国际站/ }))
    fireEvent.click(screen.getByRole('combobox', { name: '本工序模型' }))

    expect(screen.getByRole('option', { name: 'anthropic/claude-sonnet-5' })).toBeInTheDocument()
    expect(screen.queryByRole('option', { name: 'qwen/qwen3.7-plus' })).not.toBeInTheDocument()
  })

  it('edits ComfyUI recovery fields only when stage 10 is unfinished', () => {
    const onChange = vi.fn()
    const value = recoveryDraft()
    const request = { comfyui: { ...value.comfyui, grid_image: { provider: 'runninghub_image_task', runninghub_site: 'ai', model: 'rhart-image-g-2', aspect_ratio: '9:16', resolution: '1k', quality: 'high' } } } as unknown as RunRequestPayload
    renderWorkspace('comfyui', { runRequest: request, recovery: { value, onChange } })

    fireEvent.change(screen.getByLabelText('工作流 JSON 路径'), { target: { value: 'D:/recovered.json' } })

    expect(onChange).toHaveBeenCalledWith({
      ...value,
      comfyui: { ...value.comfyui, workflow_api_path: 'D:/recovered.json' },
    })
  })
})
