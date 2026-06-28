import { SectionCard } from '../../../shared/components/SectionCard'
import { StatusBadge } from '../../../shared/components/StatusBadge'

export function AcceptanceStatusPanel() {
  return (
    <SectionCard
      title="Acceptance"
      description="ready_for_release 由后端 acceptance-status 计算，前端不手动宣称。"
      tone="blue"
    >
      <div className="metric-grid">
        <div className="metric">
          <span>model check</span>
          <strong>
            <StatusBadge status="blocked" />
          </strong>
        </div>
        <div className="metric">
          <span>single run</span>
          <strong>
            <StatusBadge status="blocked" />
          </strong>
        </div>
        <div className="metric">
          <span>export</span>
          <strong>
            <StatusBadge status="warning" />
          </strong>
        </div>
      </div>
    </SectionCard>
  )
}
