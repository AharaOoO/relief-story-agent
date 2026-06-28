import { SectionCard } from '../../../shared/components/SectionCard'
import { StatusBadge } from '../../../shared/components/StatusBadge'

export function RunHeader({ runId }: { runId: string }) {
  return (
    <SectionCard title="Run Header" description="当前 run 的固定事实，不做 release ready 推断。">
      <div className="metric-grid">
        <div className="metric">
          <span>run_id</span>
          <strong>{runId}</strong>
        </div>
        <div className="metric">
          <span>状态</span>
          <strong>
            <StatusBadge status="awaiting_approval" />
          </strong>
        </div>
        <div className="metric">
          <span>Active Stage</span>
          <strong>gpt_prompt_audit</strong>
        </div>
      </div>
    </SectionCard>
  )
}
