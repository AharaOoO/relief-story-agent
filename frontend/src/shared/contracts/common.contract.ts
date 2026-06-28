export const COMMON_STATUSES = [
  'idle',
  'checking',
  'ready',
  'blocked',
  'warning',
  'queued',
  'running',
  'paused',
  'awaiting_approval',
  'completed',
  'failed',
  'cancelled',
  'unknown',
] as const

export type CommonStatus = (typeof COMMON_STATUSES)[number]

export type GenerationMode = 'local_comfyui' | 'runninghub_cloud'

export type RecommendedActionCode =
  | 'publish'
  | 'refresh_comfyui_outputs'
  | 'fix_template'
  | 'check_comfyui_mapping'
  | 'manual_review_prompt_audit'
  | 'manual_review_script_quality'
  | 'retry_from_stage'
  | 'manual_review'
