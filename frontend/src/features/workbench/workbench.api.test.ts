import { describe, expect, it } from 'vitest'
import {
  analyzeComfyWorkflow,
  approveRun,
  cancelBatch,
  connectComfyUI,
  fetchRunEvents,
  fetchRunArtifacts,
  fetchTimeline,
  formatPreflightIssue,
  pauseBatch,
  refreshRunComfyUI,
  clonePromptProfile,
  listPromptProfiles,
  resetPromptProfile,
  resumeBatch,
  retryBatch,
  updatePromptProfile,
} from './workbench.api'

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

  it('includes downloaded ComfyUI outputs in the asset list', async () => {
    const originalFetch = globalThis.fetch
    globalThis.fetch = async () => new Response(JSON.stringify({
      artifacts: [{ type: 'final_prompts', path: 'D:/run/prompts.json' }],
      actual_outputs: [{ media_type: 'video', filename: 'final.mp4', local_path: 'D:/run/final.mp4' }],
    }), { status: 200 })
    try {
      await expect(fetchRunArtifacts('run-video')).resolves.toEqual(expect.arrayContaining([
        expect.objectContaining({ type: 'final_prompts', path: 'D:/run/prompts.json' }),
        expect.objectContaining({ kind: 'video', name: 'final.mp4', local_path: 'D:/run/final.mp4' }),
      ]))
    } finally {
      globalThis.fetch = originalFetch
    }
  })
})

describe('workbench control contracts', () => {
  it('calls the real run and batch control endpoints', async () => {
    const originalFetch = globalThis.fetch
    const requests: Array<{ url: string; method: string; body: string }> = []
    globalThis.fetch = async (input, init) => {
      requests.push({
        url: String(input),
        method: init?.method ?? 'GET',
        body: String(init?.body ?? ''),
      })
      return new Response(JSON.stringify({ status: 'ok', events: [], next_cursor: 7 }), { status: 200 })
    }
    try {
      await pauseBatch('batch-one')
      await resumeBatch('batch-one')
      await cancelBatch('batch-one')
      await retryBatch('batch-one', 'quality_gate')
      await approveRun('run-one')
      await refreshRunComfyUI('run-one')
      await fetchRunEvents('run-one', 6)
    } finally {
      globalThis.fetch = originalFetch
    }

    expect(requests.map((request) => request.url)).toEqual(expect.arrayContaining([
      expect.stringContaining('/api/batches/batch-one/pause'),
      expect.stringContaining('/api/batches/batch-one/resume'),
      expect.stringContaining('/api/batches/batch-one/cancel'),
      expect.stringContaining('/api/batches/batch-one/retry'),
      expect.stringContaining('/api/runs/run-one/approve'),
      expect.stringContaining('/api/runs/run-one/refresh-comfyui'),
      expect.stringContaining('/api/runs/run-one/events?after=6'),
    ]))
    expect(requests.find((request) => request.url.includes('/retry'))?.body).toContain('quality_gate')
    expect(requests.filter((request) => !request.url.includes('/events')).every((request) => request.method === 'POST')).toBe(true)
  })

  it('analyzes and connects the selected ComfyUI workflow', async () => {
    const originalFetch = globalThis.fetch
    const requests: Array<{ url: string; body: Record<string, unknown> }> = []
    globalThis.fetch = async (input, init) => {
      requests.push({ url: String(input), body: JSON.parse(String(init?.body ?? '{}')) as Record<string, unknown> })
      return new Response(JSON.stringify({ connected: true, ready: true }), { status: 200 })
    }
    try {
      await analyzeComfyWorkflow('http://127.0.0.1:8188', 'D:/workflow.json')
      await connectComfyUI('http://127.0.0.1:8188', 'D:/workflow.json')
    } finally {
      globalThis.fetch = originalFetch
    }

    expect(requests[0].url).toContain('/api/comfyui/analyze-workflow')
    expect(requests[0].body).toMatchObject({ comfyui: { endpoint: 'http://127.0.0.1:8188', workflow_api_path: 'D:/workflow.json' } })
    expect(requests[1].url).toContain('/api/comfyui/connect')
    expect(requests[1].body).toMatchObject({ endpoint: 'http://127.0.0.1:8188', workflow_api_path: 'D:/workflow.json' })
  })

  it('persists reusable prompt profiles through the backend API', async () => {
    const originalFetch = globalThis.fetch
    const requests: Array<{ url: string; method: string }> = []
    globalThis.fetch = async (input, init) => {
      requests.push({ url: String(input), method: init?.method ?? 'GET' })
      return new Response(JSON.stringify({ items: [], id: 'profile-one', stages: {} }), { status: 200 })
    }
    try {
      await listPromptProfiles()
      await clonePromptProfile('system-default', '我的制片模板')
      await updatePromptProfile({ id: 'profile-one', name: '我的制片模板', description: '', version: 1, source: 'user', stages: {} })
      await resetPromptProfile('profile-one')
    } finally {
      globalThis.fetch = originalFetch
    }

    expect(requests.map((request) => [request.method, request.url])).toEqual(expect.arrayContaining([
      ['GET', expect.stringContaining('/api/prompt-profiles')],
      ['POST', expect.stringContaining('/api/prompt-profiles/system-default/clone')],
      ['PUT', expect.stringContaining('/api/prompt-profiles/profile-one')],
      ['POST', expect.stringContaining('/api/prompt-profiles/profile-one/reset')],
    ]))
  })
})
