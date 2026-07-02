import { describe, expect, it } from 'vitest'
import type { ModelStageId, RunRequestPayload } from '../run-composer/runRequest.builder'
import type { RunDetail } from '../workbench/workbench.api'
import { AUTOPILOT_STAGES, type AutopilotStageStatus } from './stages'
import {
  buildRecoveryRetryPayload,
  createRecoveryDraft,
  stageEditingState,
} from './recoveryDraft'

const configurableStages = new Set([
  'chief_screenwriter',
  'deepseek_polish',
  'quality_gate',
  'gpt_prompt_writer',
  'gpt_prompt_audit',
  'gpt_prompt_reviser',
  'four_grid_asset',
  'comfyui',
])

function statusesForFailure(failedStage: string) {
  const failedIndex = AUTOPILOT_STAGES.findIndex((stage) => stage.id === failedStage)
  return Object.fromEntries(AUTOPILOT_STAGES.map((stage, index) => [
    stage.id,
    index < failedIndex ? 'completed' : index === failedIndex ? 'failed' : 'pending',
  ])) as Record<string, AutopilotStageStatus>
}

function failedRun(failedStage = 'quality_gate'): RunDetail {
  const request = {
    idea: 'recovery test',
    model_configs: {
      chief_screenwriter: { provider_mode: 'runninghub', runninghub_site: 'ai', model: 'google/gemini-3.5-flash' },
      deepseek_polish: { provider_mode: 'runninghub', runninghub_site: 'cn', model: 'deepseek/deepseek-v4-pro' },
      quality_gate: { provider_mode: 'runninghub', runninghub_site: 'cn', model: 'deepseek/deepseek-v4-flash' },
      gpt_prompt_writer: { provider_mode: 'runninghub', runninghub_site: 'ai', model: 'openai/gpt-5.5' },
      gpt_prompt_audit: { provider_mode: 'runninghub', runninghub_site: 'ai', model: 'openai/gpt-5.4-mini' },
      gpt_prompt_reviser: { provider_mode: 'runninghub', runninghub_site: 'ai', model: 'openai/gpt-5.4-mini' },
    },
    prompt_profile: {
      profile_id: 'system-default',
      profile_version: 1,
      stage_overrides: { quality_gate: 'original gate prompt' },
    },
    comfyui: {
      enabled: true,
      endpoint: 'http://127.0.0.1:8188',
      workflow_api_path: 'D:/workflow/original.json',
      output_timeout_seconds: 600,
      wait_for_completion: true,
      download_outputs: true,
      grid_image: {
        provider: 'runninghub_image_task',
        runninghub_site: 'ai',
        model: 'rhart-image-g-2',
        aspect_ratio: '16:9',
        resolution: '2k',
        quality: 'high',
      },
    },
  } as RunRequestPayload
  return {
    run_id: 'run-recovery',
    status: 'failed',
    current_stage: 'failed',
    failed_stage: failedStage,
    request,
    prompt_snapshot: {
      quality_gate: 'original gate prompt',
      gpt_prompt_writer: 'original writer prompt',
    },
  }
}

describe('stageEditingState', () => {
  it('freezes completed stages and edits the failed and downstream configurable stages', () => {
    const statuses = statusesForFailure('quality_gate')

    expect(stageEditingState('chief_screenwriter', statuses, 'failed', 'quality_gate')).toBe('frozen')
    expect(stageEditingState('deepseek_polish', statuses, 'failed', 'quality_gate')).toBe('frozen')
    expect(stageEditingState('quality_gate', statuses, 'failed', 'quality_gate')).toBe('editable')
    expect(stageEditingState('gpt_prompt_writer', statuses, 'failed', 'quality_gate')).toBe('editable')
    expect(stageEditingState('four_grid_asset', statuses, 'failed', 'quality_gate')).toBe('editable')
    expect(stageEditingState('comfyui', statuses, 'failed', 'quality_gate')).toBe('editable')
    expect(stageEditingState('final_prompts', statuses, 'failed', 'quality_gate')).toBe('automatic')
    expect(stageEditingState('artifacts', statuses, 'failed', 'quality_gate')).toBe('automatic')
  })

  it('applies the same lock boundary for every failed stage', () => {
    for (const [failedIndex, failed] of AUTOPILOT_STAGES.entries()) {
      const statuses = statusesForFailure(failed.id)
      for (const [index, stage] of AUTOPILOT_STAGES.entries()) {
        const state = stageEditingState(stage.id, statuses, 'failed', failed.id)
        if (index < failedIndex || statuses[stage.id] === 'completed') {
          expect(state, `${failed.id} -> ${stage.id}`).toBe('frozen')
        } else if (configurableStages.has(stage.id)) {
          expect(state, `${failed.id} -> ${stage.id}`).toBe('editable')
        } else {
          expect(state, `${failed.id} -> ${stage.id}`).toBe('automatic')
        }
      }
    }
  })
})

describe('recovery retry payload', () => {
  it('submits only changed unfinished configuration', () => {
    const run = failedRun()
    const original = createRecoveryDraft(run)
    const draft = structuredClone(original)
    draft.stageModels.quality_gate = {
      provider_mode: 'runninghub',
      runninghub_site: 'cn',
      model: 'glm-5.2',
    }
    draft.stageModels.gpt_prompt_writer = {
      provider_mode: 'runninghub',
      runninghub_site: 'ai',
      model: 'anthropic/claude-sonnet-5',
    }
    draft.stageModels.deepseek_polish = {
      provider_mode: 'runninghub',
      runninghub_site: 'cn',
      model: 'glm-5.1',
    }
    draft.stagePrompts.quality_gate = 'updated gate prompt'
    draft.gridImage.runninghub_site = 'cn'
    draft.comfyui.workflow_api_path = 'D:/workflow/recovered.json'

    const payload = buildRecoveryRetryPayload(
      run,
      draft,
      statusesForFailure('quality_gate'),
    )

    expect(payload.from_stage).toBe('quality_gate')
    expect(payload.model_config_overrides).toEqual({
      quality_gate: draft.stageModels.quality_gate,
      gpt_prompt_writer: draft.stageModels.gpt_prompt_writer,
    })
    expect(payload.model_config_overrides).not.toHaveProperty('deepseek_polish')
    expect(payload.prompt_overrides).toEqual({ quality_gate: 'updated gate prompt' })
    expect(payload.grid_image_override).toEqual(draft.gridImage)
    expect(payload.comfyui_override).toEqual({ workflow_api_path: 'D:/workflow/recovered.json' })
  })

  it('returns a stage-only retry when nothing changed', () => {
    const run = failedRun('gpt_prompt_audit')
    const draft = createRecoveryDraft(run)

    expect(buildRecoveryRetryPayload(
      run,
      draft,
      statusesForFailure('gpt_prompt_audit'),
    )).toEqual({ from_stage: 'gpt_prompt_audit' })
  })

  it('copies model and prompt values instead of sharing mutable run state', () => {
    const run = failedRun()
    const draft = createRecoveryDraft(run)
    const stage = 'quality_gate' satisfies ModelStageId

    draft.stageModels[stage]!.model = 'glm-5.2'
    draft.stagePrompts[stage] = 'changed'

    expect(run.request?.model_configs[stage].model).toBe('deepseek/deepseek-v4-flash')
    expect(run.prompt_snapshot?.[stage]).toBe('original gate prompt')
  })
})
