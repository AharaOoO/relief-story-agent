import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { StageWorkspace } from './StageWorkspace'
import type { RunRequestPayload } from '../run-composer/runRequest.builder'

vi.mock('../workbench/workbench.api', () => ({
  fetchProviderCatalog: vi.fn().mockResolvedValue({
    runninghub: {
      cn: { base_url: 'https://llm.runninghub.cn/v1', api_key_env: 'RUNNINGHUB_CN_API_KEY', stages: { chief_screenwriter: ['qwen/qwen3.7-plus'] } },
      ai: { base_url: 'https://llm.runninghub.ai/v1', api_key_env: 'RUNNINGHUB_AI_API_KEY', stages: { chief_screenwriter: ['google/gemini-3.5-flash'] } },
    },
  }),
}))

describe('StageWorkspace run snapshot', () => {
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
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })

    render(<QueryClientProvider client={client}><StageWorkspace stageId="chief_screenwriter" readOnly runRequest={request} promptSnapshot={{ chief_screenwriter: '这是真实任务冻结的总编剧提示词' }} /></QueryClientProvider>)

    expect(await screen.findByDisplayValue('qwen/qwen3.7-plus')).toBeDisabled()
    expect(screen.getByDisplayValue('这是真实任务冻结的总编剧提示词')).toBeDisabled()
  })
})
