import { SectionCard } from '../../../shared/components/SectionCard'
import { StatusBadge } from '../../../shared/components/StatusBadge'

export function FailureDetailCard() {
  return (
    <SectionCard title="Failure Detail" description="每个失败状态必须有下一步动作。">
      <div className="metric-grid">
        <div className="metric">
          <span>failed_stage</span>
          <strong>comfyui</strong>
        </div>
        <div className="metric">
          <span>error_kind</span>
          <strong>external</strong>
        </div>
        <div className="metric">
          <span>retryable</span>
          <strong>
            <StatusBadge status="warning" label="需计划" />
          </strong>
        </div>
      </div>
    </SectionCard>
  )
}
