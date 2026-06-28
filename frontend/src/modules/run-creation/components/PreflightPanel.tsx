import { SectionCard } from '../../../shared/components/SectionCard'
import { StatusBadge } from '../../../shared/components/StatusBadge'
import { useLocalReadiness } from '../../../shared/hooks/useBackendHealth'
import { normalizeReadiness } from '../../../shared/utils/normalizeReadiness'

export function PreflightPanel() {
  const readiness = useLocalReadiness()
  const data = normalizeReadiness(readiness.data)

  return (
    <SectionCard
      title="Preflight"
      description="preflight failed 时不创建 run。"
    >
      <div className="metric-grid">
        <div className="metric">
          <span>ready_for_real_runs</span>
          <strong>
            <StatusBadge status={data.ready_for_real_runs ? 'ready' : 'blocked'} />
          </strong>
        </div>
        <div className="metric">
          <span>blockers</span>
          <strong>{data.blockers.length}</strong>
        </div>
      </div>
      <div className="stack" style={{ marginTop: 14 }}>
        {data.blockers.slice(0, 2).map((blocker) => (
          <div className="alert-box" key={blocker.code}>
            <h3>{blocker.title}</h3>
            <p>{blocker.detail}</p>
          </div>
        ))}
      </div>
    </SectionCard>
  )
}
