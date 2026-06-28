import { SectionCard } from '../../../shared/components/SectionCard'
import { StatusBadge } from '../../../shared/components/StatusBadge'

export function ExportValidationPanel() {
  return (
    <SectionCard
      title="Export Validation"
      description="validation failed 时不得显示“可发布”。"
    >
      <div className="metric-grid">
        <div className="metric">
          <span>manifest</span>
          <strong>
            <StatusBadge status="ready" />
          </strong>
        </div>
        <div className="metric">
          <span>video signature</span>
          <strong>
            <StatusBadge status="blocked" label="未通过" />
          </strong>
        </div>
        <div className="metric">
          <span>publish</span>
          <strong>
            <StatusBadge status="warning" label="不可发布" />
          </strong>
        </div>
      </div>
    </SectionCard>
  )
}
