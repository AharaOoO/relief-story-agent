import type { PipelineStage } from '../../shared/contracts/pipeline.contract'

export const MODEL_STAGE_IDS = [
  'chief_screenwriter',
  'deepseek_polish',
  'quality_gate',
  'gpt_prompt_writer',
  'gpt_prompt_audit',
  'gpt_prompt_reviser',
] as const satisfies readonly PipelineStage[]

export type ModelStageId = (typeof MODEL_STAGE_IDS)[number]
export type RunningHubSite = 'cn' | 'ai'
export type StoryInputMode = 'auto' | 'idea' | 'requirements' | 'script' | 'mixed'

export type StageModelDraft = {
  provider_mode: 'runninghub' | 'openai_compatible'
  runninghub_site?: RunningHubSite
  base_url?: string
  api_key_env?: string
  model: string
  temperature?: number
  timeout_seconds?: number
}

export type RunDraft = {
  content: string
  inputMode: StoryInputMode
  sourceName: string
  durationSeconds: number
  aspectRatio: '16:9' | '9:16'
  imageResolution: '1k' | '2k'
  stylePresetId: string
  seriesName: string
  audience: string
  creativeConstraints: string
  taskCount: number
  approvalMode: 'auto' | 'manual'
  promptProfileId: string
  promptProfileVersion: number
  stageModels: Partial<Record<ModelStageId, StageModelDraft>>
  stagePrompts: Partial<Record<ModelStageId, string>>
  comfyuiEnabled: boolean
  comfyuiEndpoint: string
  workflowPath: string
  outputRoot: string
  runninghubSite: RunningHubSite
}

export type RunRequestPayload = {
  idempotency_key: string
  idea: string
  input_spec: {
    mode: StoryInputMode
    content: string
    source_name?: string
    language: 'zh-CN'
    preserve_original_plot: true
  }
  creation_spec: {
    duration_seconds: number
    video_aspect_ratio: '16:9' | '9:16'
    image_resolution: '1k' | '2k'
    style_preset_id: string
    series_name: string
    audience: string
    creative_constraints: string[]
  }
  prompt_profile: {
    profile_id: string
    profile_version: number
    stage_overrides: Partial<Record<ModelStageId, string>>
  }
  render_backend: { provider: 'comfyui' }
  queue_priority: number
  output_root?: string
  approval_mode: 'auto' | 'manual'
  model_configs: Record<ModelStageId, StageModelDraft>
  comfyui: {
    enabled: boolean
    endpoint: string
    workflow_api_path: string | null
    wait_for_completion: boolean
    download_outputs: boolean
    grid_image: {
      provider: 'runninghub_image_task'
      runninghub_site: RunningHubSite
      model: 'rhart-image-g-2'
      aspect_ratio: '16:9' | '9:16'
      resolution: '1k' | '2k'
      quality: 'high'
    }
  }
}

export type BatchRequestPayload = {
  idempotency_key: string
  failure_policy: {
    auto_retry_failed_items: number
    pause_on_failure_count: number
    pause_on_failure_rate: number
  }
  items: RunRequestPayload[]
}

const DEFAULT_RUNNINGHUB_MODELS: Record<RunningHubSite, Record<ModelStageId, string>> = {
  cn: {
    chief_screenwriter: 'qwen/qwen3.7-plus',
    deepseek_polish: 'deepseek/deepseek-v4-pro',
    quality_gate: 'deepseek/deepseek-v4-pro',
    gpt_prompt_writer: 'qwen/qwen3.7-max',
    gpt_prompt_audit: 'deepseek/deepseek-v4-pro',
    gpt_prompt_reviser: 'qwen/qwen3.7-plus',
  },
  ai: {
    chief_screenwriter: 'google/gemini-3.5-flash',
    deepseek_polish: 'deepseek/deepseek-v4-pro',
    quality_gate: 'deepseek/deepseek-v4-pro',
    gpt_prompt_writer: 'openai/gpt-5.5',
    gpt_prompt_audit: 'openai/gpt-5.4-mini',
    gpt_prompt_reviser: 'openai/gpt-5.4-mini',
  },
}

export function defaultRunningHubModel(site: RunningHubSite, stageId: ModelStageId): string {
  return DEFAULT_RUNNINGHUB_MODELS[site][stageId]
}

export function createRunningHubStageModels(
  site: RunningHubSite,
): Record<ModelStageId, StageModelDraft> {
  return Object.fromEntries(
    MODEL_STAGE_IDS.map((stageId) => [stageId, {
      provider_mode: 'runninghub' as const,
      runninghub_site: site,
      model: DEFAULT_RUNNINGHUB_MODELS[site][stageId],
    }]),
  ) as Record<ModelStageId, StageModelDraft>
}

function normalizeConstraints(value: string): string[] {
  return value
    .split(/\r?\n|[；;]/)
    .map((item) => item.trim())
    .filter(Boolean)
}

function createRequestId(prefix: string, index = 0): string {
  const randomPart = Math.random().toString(36).slice(2, 10)
  return `${prefix}-${Date.now()}-${index}-${randomPart}`
}

function normalizeModelConfigs(draft: RunDraft): Record<ModelStageId, StageModelDraft> {
  const globalDefaults = createRunningHubStageModels(draft.runninghubSite)
  return Object.fromEntries(MODEL_STAGE_IDS.map((stageId) => {
    const candidate = draft.stageModels[stageId]
    const site = candidate?.runninghub_site ?? draft.runninghubSite
    const fallback = createRunningHubStageModels(site)[stageId]
    const source = candidate?.model?.trim() ? candidate : fallback ?? globalDefaults[stageId]
    const normalized: StageModelDraft = {
      provider_mode: source.provider_mode,
      model: source.model,
      ...(source.runninghub_site ? { runninghub_site: source.runninghub_site } : {}),
      ...(source.base_url ? { base_url: source.base_url } : {}),
      ...(source.api_key_env ? { api_key_env: source.api_key_env } : {}),
      ...(source.temperature !== undefined ? { temperature: source.temperature } : {}),
      ...(source.timeout_seconds !== undefined ? { timeout_seconds: source.timeout_seconds } : {}),
    }
    return [stageId, normalized]
  })) as Record<ModelStageId, StageModelDraft>
}

export function createRunDraft(): RunDraft {
  return {
    content: '',
    inputMode: 'auto',
    sourceName: '',
    durationSeconds: 90,
    aspectRatio: '16:9',
    imageResolution: '2k',
    stylePresetId: 'cinematic_suspense',
    seriesName: '',
    audience: '',
    creativeConstraints: '',
    taskCount: 1,
    approvalMode: 'auto',
    promptProfileId: 'system-default',
    promptProfileVersion: 1,
    stageModels: createRunningHubStageModels('ai'),
    stagePrompts: {},
    comfyuiEnabled: true,
    comfyuiEndpoint: 'http://127.0.0.1:8188',
    workflowPath: '',
    outputRoot: '',
    runninghubSite: 'ai',
  }
}

export function buildRunRequest(draft: RunDraft, index = 0): RunRequestPayload {
  const sourceName = draft.sourceName.trim()
  const outputRoot = draft.outputRoot.trim()

  return {
    idempotency_key: createRequestId('desktop-run', index),
    idea: draft.content.trim(),
    input_spec: {
      mode: draft.inputMode,
      content: draft.content.trim(),
      ...(sourceName ? { source_name: sourceName } : {}),
      language: 'zh-CN',
      preserve_original_plot: true,
    },
    creation_spec: {
      duration_seconds: draft.durationSeconds,
      video_aspect_ratio: draft.aspectRatio,
      image_resolution: draft.imageResolution,
      style_preset_id: draft.stylePresetId,
      series_name: draft.seriesName.trim(),
      audience: draft.audience.trim(),
      creative_constraints: normalizeConstraints(draft.creativeConstraints),
    },
    prompt_profile: {
      profile_id: draft.promptProfileId,
      profile_version: draft.promptProfileVersion,
      stage_overrides: { ...draft.stagePrompts },
    },
    render_backend: { provider: 'comfyui' },
    queue_priority: 0,
    ...(outputRoot ? { output_root: outputRoot } : {}),
    approval_mode: draft.approvalMode,
    model_configs: normalizeModelConfigs(draft),
    comfyui: {
      enabled: draft.comfyuiEnabled,
      endpoint: draft.comfyuiEndpoint.trim() || 'http://127.0.0.1:8188',
      workflow_api_path: draft.workflowPath.trim() || null,
      wait_for_completion: true,
      download_outputs: true,
      grid_image: {
        provider: 'runninghub_image_task',
        runninghub_site: draft.runninghubSite,
        model: 'rhart-image-g-2',
        aspect_ratio: draft.aspectRatio,
        resolution: draft.imageResolution,
        quality: 'high',
      },
    },
  }
}

export function buildBatchRequest(draft: RunDraft): BatchRequestPayload {
  const count = Math.min(20, Math.max(1, Math.floor(draft.taskCount)))
  return {
    idempotency_key: createRequestId('desktop-batch'),
    failure_policy: {
      auto_retry_failed_items: 1,
      pause_on_failure_count: 3,
      pause_on_failure_rate: 0.5,
    },
    items: Array.from({ length: count }, (_, index) => buildRunRequest(draft, index)),
  }
}
