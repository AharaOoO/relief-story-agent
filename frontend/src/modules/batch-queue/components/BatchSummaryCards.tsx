import { StatusBadge } from '../../../shared/components/StatusBadge'

export function BatchSummaryCards() {
  return (
    <div className="metric-grid">
      <div className="metric">
        <span>Running Batch</span>
        <strong>1</strong>
      </div>
      <div className="metric">
        <span>Completed</span>
        <strong>1</strong>
      </div>
      <div className="metric">
        <span>Attention</span>
        <strong>
          <StatusBadge status="awaiting_approval" />
        </strong>
      </div>
    </div>
  )
}
