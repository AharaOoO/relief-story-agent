import type { GenerationMode } from '../../../shared/contracts/common.contract'

export type StoryInputSpec = {
  mode: 'auto' | 'idea' | 'requirements' | 'script' | 'mixed'
  content: string
  source_name?: string
  language?: string
  preserve_original_plot?: boolean
}

export type CreationSpec = {
  duration_seconds: number
  video_aspect_ratio: '16:9' | '9:16'
  image_resolution: '2k' | '1080p'
  style_preset_id: string
  series_name: string
  audience: string
  creative_constraints: string[]
}

export type PromptProfileBinding = {
  profile_id: string
  profile_version: number
  stage_overrides: Record<string, string>
}

export type RenderBackendSpec = {
  provider: 'comfyui' | 'runninghub_workflow'
  runninghub_workflow_id?: string
}


export type RunRequest = {
  idea?: string
  input_spec?: StoryInputSpec
  creation_spec?: CreationSpec
  prompt_profile?: PromptProfileBinding
  render_backend?: RenderBackendSpec
  generation_mode?: GenerationMode
  approval_mode: 'manual' | 'auto_after_audit_pass' | 'auto'
  duration_seconds?: number
  dry_run?: boolean
}

export type PreflightResult = {
  ready: boolean
  blockers: string[]
  warnings: string[]
}
