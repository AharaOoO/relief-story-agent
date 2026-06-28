import { SectionCard } from '../../../shared/components/SectionCard'
import { StatusBadge } from '../../../shared/components/StatusBadge'
import { useLocalReadiness } from '../../../shared/hooks/useBackendHealth'
import { normalizeReadiness } from '../../../shared/utils/normalizeReadiness'

export function ReadinessPanel() {
  const readiness = useLocalReadiness()
  const data = normalizeReadiness(readiness.data)

  return (
    <SectionCard
      title="Readiness"
      description="不隐藏 blockers；smoke passed 不等于 release ready。"
      tone="yellow"
    >
      <div className="metric-grid">
        <div className="metric">
          <span>配置</span>
          <strong>
            <StatusBadge
              status={data.ready_for_configuration ? 'ready' : 'blocked'}
            />
          </strong>
        </div>
        <div className="metric">
          <span>真实运行</span>
          <strong>
            <StatusBadge
              status={data.ready_for_real_runs ? 'ready' : 'blocked'}
            />
          </strong>
        </div>
        <div className="metric">
          <span>发布</span>
          <strong>
            <StatusBadge
              status={data.ready_for_release ? 'ready' : 'warning'}
            />
          </strong>
        </div>
      </div>
      <div className="stack" style={{ marginTop: 16 }}>
        {data.warnings.map((warning) => (
          <div className="alert-box" key={warning.code}>
            <h3>{warning.title}</h3>
            <p>{warning.detail}</p>
          </div>
        ))}
        {data.blockers.map((blocker) => (
          <div className="alert-box" key={blocker.code}>
            <h3>{blocker.title}</h3>
            <p>{blocker.detail}</p>
            {blocker.suggested_action ? <p>{blocker.suggested_action}</p> : null}
          </div>
        ))}
      </div>
    </SectionCard>
  )
}
