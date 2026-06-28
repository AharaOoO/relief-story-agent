import type { CommonStatus, RecommendedActionCode } from '../contracts/common.contract'

export type BatchRow = {
  run_id: string
  idea: string
  status: CommonStatus
  active_stage: string
  failed_stage?: string
  stage_percent: number
  recommended_action: RecommendedActionCode
}

export const sampleBatchRows: BatchRow[] = [
  {
    run_id: 'run_morning_001',
    idea: '上班前五分钟给自己松绑',
    status: 'completed',
    active_stage: 'artifacts',
    stage_percent: 100,
    recommended_action: 'publish',
  },
  {
    run_id: 'run_rain_002',
    idea: '雨天路边的一杯热饮',
    status: 'awaiting_approval',
    active_stage: 'gpt_prompt_audit',
    stage_percent: 63,
    recommended_action: 'manual_review_prompt_audit',
  },
  {
    run_id: 'run_window_003',
    idea: '夜里窗边慢慢呼吸',
    status: 'failed',
    active_stage: 'comfyui',
    failed_stage: 'comfyui',
    stage_percent: 88,
    recommended_action: 'refresh_comfyui_outputs',
  },
]
