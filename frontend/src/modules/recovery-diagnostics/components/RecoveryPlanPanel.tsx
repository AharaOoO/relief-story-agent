import { useQuery } from '@tanstack/react-query'
import { ErrorState } from '../../../shared/components/ErrorState'
import { JsonViewer } from '../../../shared/components/JsonViewer'
import { SectionCard } from '../../../shared/components/SectionCard'
import { StatusBadge } from '../../../shared/components/StatusBadge'
import { fetchBatchRecoveryPlan } from '../api/recovery.api'

const groups = [
  ['publish_ready', '可发布', 'ready'],
  ['auto_recoverable', '可自动恢复', 'ready'],
  ['manual_review_required', '需人工审查', 'warning'],
  ['wait_required', '等待外部结果', 'warning'],
  ['blocked', '阻塞', 'blocked'],
]

export function RecoveryPlanPanel({ batchId }: { batchId: string }) {
  const plan = useQuery({
    queryKey: ['batch-recovery-plan', batchId],
    queryFn: () => fetchBatchRecoveryPlan(batchId),
    enabled: batchId.trim().length > 0,
  })

  return (
    <SectionCard
      title="Recovery Plan"
      description="只有 transient/throttled/timeout 才自动恢复。"
      tone="yellow"
    >
      <div className="metric-grid">
        {groups.map(([code, label, status]) => (
          <div className="metric" key={code}>
            <span>{code}</span>
            <strong>
              <StatusBadge status={status} label={label} />
            </strong>
          </div>
        ))}
      </div>
      {plan.error ? (
        <ErrorState error={plan.error} onRetry={() => plan.refetch()} />
      ) : null}
      {plan.data ? (
        <div className="alert-box" role="status">
          <h3>Recovery plan response</h3>
          <JsonViewer value={plan.data} />
        </div>
      ) : null}
    </SectionCard>
  )
}
