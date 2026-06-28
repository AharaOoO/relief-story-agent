import type { RecommendedActionCode } from '../../../shared/contracts/common.contract'
import { StatusBadge } from '../../../shared/components/StatusBadge'

const labels: Record<RecommendedActionCode, string> = {
  publish: '可发布',
  refresh_comfyui_outputs: '查询 ComfyUI 输出',
  fix_template: '修复模板',
  check_comfyui_mapping: '检查 workflow 映射',
  manual_review_prompt_audit: '人工审查提示词',
  manual_review_script_quality: '人工审查剧本质量',
  retry_from_stage: '从失败阶段重试',
  manual_review: '人工处理',
}

export function RecommendedActionBadge({
  code,
}: {
  code: RecommendedActionCode
}) {
  const status = code === 'publish' ? 'ready' : code.includes('manual') ? 'warning' : 'running'
  return <StatusBadge status={status} label={labels[code]} />
}
