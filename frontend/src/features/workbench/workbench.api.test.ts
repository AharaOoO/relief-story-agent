import { describe, expect, it } from 'vitest'
import { fetchTimeline, formatPreflightIssue } from './workbench.api'

describe('preflight diagnostics', () => {
  it('renders backend structured blockers as readable text', () => {
    expect(formatPreflightIssue({ check: 'model_environment', message: 'API Key 尚未配置' })).toBe('API Key 尚未配置')
    expect(formatPreflightIssue('ComfyUI 无法连接')).toBe('ComfyUI 无法连接')
  })
})

describe('timeline contract', () => {
  it('reads the backend stages field', async () => {
    const originalFetch = globalThis.fetch
    globalThis.fetch = async () => new Response(JSON.stringify({ stages: [{ stage_id: 'quality_gate', status: 'completed' }] }), { status: 200 })
    try {
      await expect(fetchTimeline('run-demo')).resolves.toEqual([
        { stage_id: 'quality_gate', status: 'completed' },
      ])
    } finally {
      globalThis.fetch = originalFetch
    }
  })
})
