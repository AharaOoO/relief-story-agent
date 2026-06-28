import { SectionCard } from '../../../shared/components/SectionCard'
import { StatusBadge } from '../../../shared/components/StatusBadge'

export function PromptAuditPanel() {
  return (
    <SectionCard
      title="Prompt Audit"
      description="审查站位、越轴、动态逻辑和镜头叙事对应。"
      tone="yellow"
    >
      <div className="metric-grid">
        <div className="metric">
          <span>空间关系</span>
          <strong>
            <StatusBadge status="ready" />
          </strong>
        </div>
        <div className="metric">
          <span>静态逻辑</span>
          <strong>
            <StatusBadge status="warning" />
          </strong>
        </div>
        <div className="metric">
          <span>动态逻辑</span>
          <strong>
            <StatusBadge status="awaiting_approval" />
          </strong>
        </div>
      </div>
    </SectionCard>
  )
}
