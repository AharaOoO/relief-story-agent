export const PIPELINE_STAGES = [
  'chief_screenwriter',
  'deepseek_polish',
  'quality_gate',
  'gpt_prompt_writer',
  'gpt_prompt_audit',
  'gpt_prompt_reviser',
  'final_prompts',
  'four_grid_asset',
  'artifacts',
  'comfyui',
] as const

export type PipelineStage = (typeof PIPELINE_STAGES)[number]

export const PIPELINE_STAGE_LABELS: Record<PipelineStage, string> = {
  chief_screenwriter: 'Gemini 总编剧',
  deepseek_polish: 'DeepSeek 改稿',
  quality_gate: '剧本质量门禁',
  gpt_prompt_writer: 'GPT 分镜提示词',
  gpt_prompt_audit: '提示词审查',
  gpt_prompt_reviser: '提示词一次修正',
  final_prompts: '最终提示词',
  four_grid_asset: '四宫格参考图',
  artifacts: '产物整理',
  comfyui: 'ComfyUI/LTX 入队',
}
