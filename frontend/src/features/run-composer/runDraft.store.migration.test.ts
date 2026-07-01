import { beforeEach, describe, expect, it, vi } from 'vitest'

const LEGACY_STORAGE_KEY = 'relief-story-agent:run-draft:v2'
const CURRENT_STORAGE_KEY = 'relief-story-agent:run-draft:v3'

const legacyRunningHubStageModels = {
  chief_screenwriter: { provider_mode: 'runninghub', runninghub_site: 'ai', model: 'google/gemini-3.5-flash' },
  deepseek_polish: { provider_mode: 'runninghub', runninghub_site: 'ai', model: 'deepseek/deepseek-v4-pro' },
  quality_gate: { provider_mode: 'runninghub', runninghub_site: 'ai', model: 'deepseek/deepseek-v4-pro' },
  gpt_prompt_writer: { provider_mode: 'runninghub', runninghub_site: 'ai', model: 'openai/gpt-5.5' },
  gpt_prompt_audit: { provider_mode: 'runninghub', runninghub_site: 'ai', model: 'openai/gpt-5.4-mini' },
  gpt_prompt_reviser: { provider_mode: 'runninghub', runninghub_site: 'ai', model: 'openai/gpt-5.4-mini' },
}

describe('run draft storage migration', () => {
  beforeEach(() => {
    vi.resetModules()
    window.localStorage.clear()
  })

  it('migrates legacy RunningHub LLM defaults to ordinary provider APIs while preserving user draft content', async () => {
    window.localStorage.setItem(LEGACY_STORAGE_KEY, JSON.stringify({
      content: '一个深夜下班的人在便利店门口被热饮安慰。',
      inputMode: 'idea',
      durationSeconds: 120,
      runninghubSite: 'ai',
      stageModels: legacyRunningHubStageModels,
      stagePrompts: {
        chief_screenwriter: '请先敲定核心矛盾。',
      },
    }))

    const { useRunDraft } = await import('./runDraft.store')

    const { draft } = useRunDraft.getState()
    expect(draft.content).toBe('一个深夜下班的人在便利店门口被热饮安慰。')
    expect(draft.durationSeconds).toBe(120)
    expect(draft.stagePrompts.chief_screenwriter).toBe('请先敲定核心矛盾。')
    expect(draft.stageModels.chief_screenwriter?.provider_mode).toBe('openai_compatible')
    expect(draft.stageModels.chief_screenwriter?.api_key_env).toBe('GEMINI_API_KEY')
    expect(draft.stageModels.gpt_prompt_writer?.api_key_env).toBe('OPENAI_API_KEY')

    const persisted = JSON.parse(window.localStorage.getItem(CURRENT_STORAGE_KEY) ?? '{}')
    expect(persisted.stageModels.chief_screenwriter.provider_mode).toBe('openai_compatible')
    expect(persisted.stageModels.deepseek_polish.api_key_env).toBe('DEEPSEEK_API_KEY')
  })
})
