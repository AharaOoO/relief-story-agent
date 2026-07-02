import {
  MODEL_STAGE_IDS,
  type ModelStageId,
  type StageModelDraft,
} from '../run-composer/runRequest.builder'
import type {
  GridImageRetryOverride,
  RunDetail,
  RunRetryPayload,
} from '../workbench/workbench.api'
import { AUTOPILOT_STAGES, type AutopilotStageStatus } from './stages'

export type RecoveryDraft = {
  stageModels: Partial<Record<ModelStageId, StageModelDraft>>
  stagePrompts: Partial<Record<ModelStageId, string>>
  gridImage: GridImageRetryOverride
  comfyui: {
    endpoint: string
    workflow_api_path: string | null
    output_timeout_seconds: number
  }
}

export type StageEditingState = 'frozen' | 'editable' | 'automatic'

const CONFIGURABLE_STAGES = new Set([
  ...MODEL_STAGE_IDS,
  'four_grid_asset',
  'comfyui',
])

export function stageEditingState(
  stageId: string,
  statuses: Record<string, AutopilotStageStatus>,
  runStatus: string,
  failedStage?: string,
): StageEditingState {
  const status = statuses[stageId]
  if (status === 'completed' || status === 'skipped') return 'frozen'
  if (runStatus !== 'failed' || !failedStage) return 'frozen'

  const stageIndex = AUTOPILOT_STAGES.findIndex((stage) => stage.id === stageId)
  const failedIndex = AUTOPILOT_STAGES.findIndex((stage) => stage.id === failedStage)
  if (stageIndex < 0 || failedIndex < 0 || stageIndex < failedIndex) return 'frozen'
  return CONFIGURABLE_STAGES.has(stageId) ? 'editable' : 'automatic'
}

export function createRecoveryDraft(run: RunDetail): RecoveryDraft {
  const request = run.request
  const stageModels = Object.fromEntries(
    MODEL_STAGE_IDS.flatMap((stageId) => {
      const config = request?.model_configs?.[stageId]
      return config ? [[stageId, { ...config }]] : []
    }),
  ) as Partial<Record<ModelStageId, StageModelDraft>>
  const stagePrompts = Object.fromEntries(
    MODEL_STAGE_IDS.flatMap((stageId) => {
      const prompt = run.prompt_snapshot?.[stageId]
        ?? request?.prompt_profile?.stage_overrides?.[stageId]
      return prompt !== undefined ? [[stageId, prompt]] : []
    }),
  ) as Partial<Record<ModelStageId, string>>
  const grid = request?.comfyui?.grid_image

  return {
    stageModels,
    stagePrompts,
    gridImage: {
      runninghub_site: grid?.runninghub_site ?? 'cn',
      aspect_ratio: grid?.aspect_ratio ?? '16:9',
      resolution: grid?.resolution ?? '2k',
    },
    comfyui: {
      endpoint: request?.comfyui?.endpoint ?? 'http://127.0.0.1:8188',
      workflow_api_path: request?.comfyui?.workflow_api_path ?? null,
      output_timeout_seconds: request?.comfyui?.output_timeout_seconds ?? 600,
    },
  }
}

function valuesEqual(left: unknown, right: unknown) {
  return JSON.stringify(left) === JSON.stringify(right)
}

export function buildRecoveryRetryPayload(
  originalRun: RunDetail,
  draft: RecoveryDraft,
  statuses: Record<string, AutopilotStageStatus>,
): RunRetryPayload {
  const original = createRecoveryDraft(originalRun)
  const failedStage = originalRun.failed_stage
  const payload: RunRetryPayload = {
    ...(failedStage ? { from_stage: failedStage } : {}),
  }
  const modelOverrides: Partial<Record<ModelStageId, StageModelDraft>> = {}
  const promptOverrides: Partial<Record<ModelStageId, string>> = {}

  for (const stageId of MODEL_STAGE_IDS) {
    if (stageEditingState(stageId, statuses, originalRun.status, failedStage) !== 'editable') {
      continue
    }
    if (!valuesEqual(draft.stageModels[stageId], original.stageModels[stageId])) {
      const model = draft.stageModels[stageId]
      if (model) modelOverrides[stageId] = { ...model }
    }
    if (draft.stagePrompts[stageId] !== original.stagePrompts[stageId]) {
      promptOverrides[stageId] = draft.stagePrompts[stageId] ?? ''
    }
  }
  if (Object.keys(modelOverrides).length) payload.model_config_overrides = modelOverrides
  if (Object.keys(promptOverrides).length) payload.prompt_overrides = promptOverrides

  if (
    stageEditingState('four_grid_asset', statuses, originalRun.status, failedStage) === 'editable'
    && !valuesEqual(draft.gridImage, original.gridImage)
  ) {
    payload.grid_image_override = { ...draft.gridImage }
  }

  if (stageEditingState('comfyui', statuses, originalRun.status, failedStage) === 'editable') {
    const comfyuiOverride: NonNullable<RunRetryPayload['comfyui_override']> = {}
    for (const field of ['endpoint', 'workflow_api_path', 'output_timeout_seconds'] as const) {
      if (draft.comfyui[field] !== original.comfyui[field]) {
        Object.assign(comfyuiOverride, { [field]: draft.comfyui[field] })
      }
    }
    if (Object.keys(comfyuiOverride).length) payload.comfyui_override = comfyuiOverride
  }
  return payload
}
