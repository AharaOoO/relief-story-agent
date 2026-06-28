import type { CommonStatus, RecommendedActionCode } from '../contracts/common.contract'
import type { PipelineStage } from '../contracts/pipeline.contract'

export type StageItem = {
  stage: PipelineStage
  status: CommonStatus
  percent: number
}

export type StoryboardShot = {
  id: string
  title: string
  imagePrompt: string
  negativePrompt: string
  camera: string
  status: CommonStatus
}

export const sampleTimeline: StageItem[] = [
  { stage: 'chief_screenwriter', status: 'completed', percent: 100 },
  { stage: 'deepseek_polish', status: 'completed', percent: 100 },
  { stage: 'quality_gate', status: 'completed', percent: 100 },
  { stage: 'gpt_prompt_writer', status: 'completed', percent: 100 },
  { stage: 'gpt_prompt_audit', status: 'awaiting_approval', percent: 64 },
  { stage: 'gpt_prompt_reviser', status: 'idle', percent: 0 },
  { stage: 'final_prompts', status: 'idle', percent: 0 },
  { stage: 'four_grid_asset', status: 'idle', percent: 0 },
  { stage: 'artifacts', status: 'idle', percent: 0 },
  { stage: 'comfyui', status: 'idle', percent: 0 },
]

export const sampleStoryboard: StoryboardShot[] = [
  {
    id: 'shot-01',
    title: '夜归的人停在路灯下',
    imagePrompt: 'soft evening street, tired office worker slowing down, warm window light, calm cinematic framing',
    negativePrompt: 'horror, aggressive crowd, harsh lighting, distorted hands',
    camera: 'medium wide, slow push-in, stable eyeline',
    status: 'awaiting_approval',
  },
  {
    id: 'shot-02',
    title: '便利店热饮冒出白雾',
    imagePrompt: 'small convenience store counter, warm cup, quiet relief mood, tactile steam, gentle color contrast',
    negativePrompt: 'dramatic conflict, cluttered signage, unreadable text',
    camera: 'close-up, shallow depth, no axis break',
    status: 'ready',
  },
  {
    id: 'shot-03',
    title: '窗边坐下，城市慢下来',
    imagePrompt: 'window seat, soft rain, tiny city lights, relaxed breathing, low stimulation composition',
    negativePrompt: 'high speed, horror, fight scene, saturated neon',
    camera: 'static profile, 35mm, stable negative space',
    status: 'ready',
  },
]

export const sampleRunActions: Array<{
  code: RecommendedActionCode
  label: string
}> = [
  { code: 'manual_review_prompt_audit', label: '人工审查提示词' },
  { code: 'retry_from_stage', label: '从失败阶段重试' },
  { code: 'refresh_comfyui_outputs', label: '查询 ComfyUI 输出' },
]
