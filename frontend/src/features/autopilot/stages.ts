import type { PipelineStage } from '../../shared/contracts/pipeline.contract'
import type { ModelStageId } from '../run-composer/runRequest.builder'

export type AutopilotStageStatus =
  | 'pending'
  | 'running'
  | 'completed'
  | 'failed'
  | 'waiting'
  | 'skipped'

export type AutopilotStage = {
  id: PipelineStage
  order: number
  label: string
  title: string
  description: string
  modelStage: boolean
}

export type TimelineEntry = {
  stage?: string
  stage_id?: string
  status?: string
}

const stage = (
  id: PipelineStage,
  order: number,
  label: string,
  title: string,
  description: string,
  modelStage = false,
): AutopilotStage => ({ id, order, label, title, description, modelStage })

export const AUTOPILOT_STAGES: readonly AutopilotStage[] = [
  stage('chief_screenwriter', 1, '备料', '总编剧定稿', '确定故事内核、人物动机与核心矛盾。', true),
  stage('deepseek_polish', 2, '慢炖', '影视化改稿', '把故事改成可拍、可演、节奏清楚的短剧。', true),
  stage('quality_gate', 3, '试味', '剧本质量门禁', '检查逻辑、节奏、人物与硬性创作标准。', true),
  stage('gpt_prompt_writer', 4, '配菜', '导演分镜提示词', '生成影视级运镜与 LTX 2.3 视频提示词。', true),
  stage('gpt_prompt_audit', 5, '调味', '提示词审查', '寻找连续性、镜头逻辑与生成风险。', true),
  stage('gpt_prompt_reviser', 6, '回锅', '提示词修正', '依据审查报告修补问题；无需修正时自动跳过。', true),
  stage('final_prompts', 7, '锁菜谱', '最终提示词', '冻结审核通过的镜头与四宫格提示词。'),
  stage('four_grid_asset', 8, '出盘', '四宫格参考图', '调用 G2 生成 2K 横屏或竖屏参考图。'),
  stage('artifacts', 9, '打包', '产物整理', '保存剧本、提示词、审查报告和参考图。'),
  stage('comfyui', 10, '出餐中', 'ComfyUI / LTX 入队', '注入专属工作流并依次进入本地生成队列。'),
]

export function getStageDisplayName(stageId?: string, fallback = '等待开始') {
  if (!stageId) return fallback
  const stageDefinition = AUTOPILOT_STAGES.find((item) => item.id === stageId)
  return stageDefinition ? `${stageDefinition.label} · ${stageDefinition.title}` : '未知工序'
}

const STATUS_PRIORITY: Record<string, number> = {
  pending: 0,
  queued: 1,
  waiting: 2,
  running: 3,
  succeeded: 4,
  completed: 4,
  skipped: 4,
  failed: 5,
  cancelled: 5,
}

function normalizeStatus(value: string | undefined): AutopilotStageStatus {
  if (value === 'succeeded' || value === 'completed') return 'completed'
  if (value === 'running') return 'running'
  if (value === 'failed' || value === 'cancelled') return 'failed'
  if (value === 'waiting' || value === 'awaiting_approval') return 'waiting'
  if (value === 'skipped') return 'skipped'
  return 'pending'
}

export function stageStatusFromTimeline(
  stageId: PipelineStage,
  timeline: readonly TimelineEntry[],
  runStatus = '',
  currentStage = '',
): AutopilotStageStatus {
  const matching = timeline.filter(
    (entry) => (entry.stage_id ?? entry.stage) === stageId,
  )
  const latest = [...matching].sort(
    (a, b) => (STATUS_PRIORITY[b.status ?? ''] ?? 0) - (STATUS_PRIORITY[a.status ?? ''] ?? 0),
  )[0]
  if (latest) return normalizeStatus(latest.status)

  const stageIndex = AUTOPILOT_STAGES.findIndex((item) => item.id === stageId)
  const currentIndex = AUTOPILOT_STAGES.findIndex((item) => item.id === currentStage)

  if (
    stageId === ('gpt_prompt_reviser' satisfies ModelStageId) &&
    (runStatus === 'completed' || currentIndex > stageIndex)
  ) {
    return 'skipped'
  }
  if (currentStage === stageId && runStatus === 'running') return 'running'
  if (currentIndex > stageIndex) return 'completed'
  if (currentIndex === stageIndex && runStatus === 'awaiting_approval') return 'waiting'
  return 'pending'
}
