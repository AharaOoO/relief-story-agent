import { describe, expect, it } from 'vitest'
import { buildBatchRequest, buildRunRequest, createRunDraft } from './runRequest.builder'

describe('autopilot run request builder', () => {
  it('builds a valid blank auto request with landscape 2k defaults', () => {
    const request = buildRunRequest(createRunDraft())

    expect(request.input_spec).toEqual({
      mode: 'auto',
      content: '',
      language: 'zh-CN',
      preserve_original_plot: true,
    })
    expect(request.creation_spec.video_aspect_ratio).toBe('16:9')
    expect(request.creation_spec.image_resolution).toBe('2k')
    expect(request.approval_mode).toBe('auto')
  })

  it('carries six-stage models, prompt overrides and comfyui config', () => {
    const draft = createRunDraft()
    draft.content = '保留原剧情，把它改成影视级运镜短剧。'
    draft.inputMode = 'requirements'
    draft.aspectRatio = '9:16'
    draft.workflowPath = 'D:/ComfyUI/workflows/ltx.json'
    draft.comfyuiEndpoint = 'http://127.0.0.1:8188'
    draft.stageModels.quality_gate = {
      provider_mode: 'runninghub',
      runninghub_site: 'cn',
      model: 'deepseek/deepseek-v4-pro',
    }
    draft.stagePrompts.quality_gate = '严格检查故事逻辑 {{script_json}}'

    const request = buildRunRequest(draft)

    expect(request.input_spec.mode).toBe('requirements')
    expect(request.model_configs.quality_gate.model).toBe('deepseek/deepseek-v4-pro')
    expect(request.prompt_profile.stage_overrides.quality_gate).toContain('{{script_json}}')
    expect(request.comfyui.endpoint).toBe('http://127.0.0.1:8188')
    expect(request.comfyui.workflow_api_path).toBe('D:/ComfyUI/workflows/ltx.json')
    expect(request.comfyui.grid_image.aspect_ratio).toBe('9:16')
  })

  it('builds 1-20 batch items from the same defaults', () => {
    const draft = createRunDraft()
    draft.taskCount = 3
    const batch = buildBatchRequest(draft)

    expect(batch.items).toHaveLength(3)
    expect(batch.items.every((item) => item.input_spec.mode === 'auto')).toBe(true)
  })

  it('repairs stale empty model selections before sending a request', () => {
    const draft = createRunDraft()
    draft.stageModels.deepseek_polish = {
      provider_mode: 'runninghub',
      runninghub_site: 'cn',
      model: '',
    }

    const request = buildRunRequest(draft)

    expect(request.model_configs.deepseek_polish.model).toBe('deepseek/deepseek-v4-pro')
  })
})
