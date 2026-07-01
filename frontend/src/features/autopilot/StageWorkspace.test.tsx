import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import type { ComponentProps } from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { StageWorkspace } from './StageWorkspace'
import { useRunDraft } from '../run-composer/runDraft.store'
import type { RunRequestPayload } from '../run-composer/runRequest.builder'
import { fetchProviderCatalog } from '../workbench/workbench.api'

vi.mock('../workbench/workbench.api', () => ({
  fetchProviderCatalog: vi.fn().mockResolvedValue({
    runninghub: {
      cn: { base_url: 'https://llm.runninghub.cn/v1', api_key_env: 'RUNNINGHUB_CN_SHARED_API_KEY', stages: { chief_screenwriter: ['qwen/qwen3.7-plus'] } },
      ai: { base_url: 'https://llm.runninghub.ai/v1', api_key_env: 'RUNNINGHUB_AI_SHARED_API_KEY', stages: { chief_screenwriter: ['google/gemini-3.5-flash'] } },
    },
  }),
}))

function renderWorkspace(stageId: string, props: Partial<ComponentProps<typeof StageWorkspace>> = {}) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(<QueryClientProvider client={client}><StageWorkspace stageId={stageId} {...props} /></QueryClientProvider>)
}

function clickRunningHubMode() {
  const button = screen.getAllByRole('button').find((item) => item.textContent?.includes('RunningHub'))
  expect(button).toBeTruthy()
  fireEvent.click(button!)
}

beforeEach(() => {
  window.localStorage.clear()
  window.reliefDesktop = undefined
  useRunDraft.getState().resetDraft()
  vi.mocked(fetchProviderCatalog).mockResolvedValue({
    runninghub: {
      cn: { base_url: 'https://llm.runninghub.cn/v1', api_key_env: 'RUNNINGHUB_CN_SHARED_API_KEY', stages: { chief_screenwriter: ['qwen/qwen3.7-plus'] } },
      ai: { base_url: 'https://llm.runninghub.ai/v1', api_key_env: 'RUNNINGHUB_AI_SHARED_API_KEY', stages: { chief_screenwriter: ['google/gemini-3.5-flash'] } },
    },
  })
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
    } as unknown as RunRequestPayload

    renderWorkspace('four_grid_asset', { readOnly: true, runRequest: request })

    expect(screen.getByRole('button', { name: '国际站 .ai' })).toHaveClass('is-active')
    expect(screen.getByRole('button', { name: '国际站 .ai' })).toBeDisabled()
    expect(screen.getByDisplayValue('竖屏 9:16')).toBeDisabled()
    expect(screen.getByDisplayValue('1K 快速')).toBeDisabled()
  })

  it('edits an isolated G2 recovery draft without changing the new-run draft', () => {
    const onChange = vi.fn()
    renderWorkspace('four_grid_asset', {
      readOnly: true,
      gridImageRecovery: {
        value: {
          runninghub_site: 'ai',
          aspect_ratio: '9:16',
          resolution: '1k',
        },
        onChange,
      },
    })

    fireEvent.click(screen.getByRole('button', { name: '国内站 .cn' }))

    expect(onChange).toHaveBeenCalledWith({
      runninghub_site: 'cn',
      aspect_ratio: '9:16',
      resolution: '1k',
    })
    expect(useRunDraft.getState().draft.gridImageSite).toBe('cn')
    expect(screen.getByText('恢复编辑')).toBeInTheDocument()
  })

  it('shows the frozen model and prompt from the run instead of the current local draft', async () => {
    const request = {
      model_configs: {
        chief_screenwriter: { provider_mode: 'runninghub', runninghub_site: 'cn', model: 'qwen/qwen3.7-plus' },
      },
      prompt_profile: {
        profile_id: 'profile-one',
        profile_version: 3,
        stage_overrides: { chief_screenwriter: '这是真实任务冻结的总编剧提示词' },
      },
    } as unknown as RunRequestPayload

    renderWorkspace('chief_screenwriter', { readOnly: true, runRequest: request, promptSnapshot: { chief_screenwriter: '这是真实任务冻结的总编剧提示词' } })

    expect(await screen.findByDisplayValue('qwen/qwen3.7-plus')).toBeDisabled()
    expect(screen.getByDisplayValue('这是真实任务冻结的总编剧提示词')).toBeDisabled()
  })

  it('falls back to curated RunningHub defaults when provider catalog lacks the selected stage', async () => {
    vi.mocked(fetchProviderCatalog).mockResolvedValueOnce({
      runninghub: {
        cn: { base_url: 'https://llm.runninghub.cn/v1', api_key_env: 'RUNNINGHUB_CN_SHARED_API_KEY', stages: {} },
        ai: { base_url: 'https://llm.runninghub.ai/v1', api_key_env: 'RUNNINGHUB_AI_SHARED_API_KEY', stages: {} },
      },
    })

    renderWorkspace('gpt_prompt_writer')

    expect(await screen.findByDisplayValue('GPT-5')).toBeInTheDocument()
    clickRunningHubMode()
    expect(await screen.findByDisplayValue('openai/gpt-5.5')).toBeInTheDocument()
    expect(screen.getByText(/最长等待 5 分钟/)).toBeInTheDocument()
    fireEvent.change(screen.getByDisplayValue('RunningHub 国际站 .ai'), { target: { value: 'cn' } })

    expect(screen.getByDisplayValue('qwen/qwen3.7-max')).toBeInTheDocument()
  })

  it('keeps RunningHub stage selectors limited to curated models even when the backend returns extra models', async () => {
    vi.mocked(fetchProviderCatalog).mockResolvedValueOnce({
      runninghub: {
        cn: { base_url: 'https://llm.runninghub.cn/v1', api_key_env: 'RUNNINGHUB_CN_SHARED_API_KEY', stages: {} },
        ai: {
          base_url: 'https://llm.runninghub.ai/v1',
          api_key_env: 'RUNNINGHUB_AI_SHARED_API_KEY',
          stages: {
            quality_gate: [
              'deepseek/deepseek-v4-pro',
              'openai/gpt-5.5',
              'anthropic/claude-opus-4.8',
              'bytedance/doubao-seed-2.0-pro',
            ],
          },
        },
      },
    })

    renderWorkspace('quality_gate')

    clickRunningHubMode()
    await waitFor(() => {
      expect(screen.getByRole('option', { name: 'openai/gpt-5.5' })).toBeInTheDocument()
    })

    expect(screen.queryByRole('option', { name: 'anthropic/claude-opus-4.8' })).not.toBeInTheDocument()
    expect(screen.queryByRole('option', { name: 'bytedance/doubao-seed-2.0-pro' })).not.toBeInTheDocument()
  })
})
