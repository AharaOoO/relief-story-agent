import { SectionCard } from '../../../shared/components/SectionCard'
import { PIPELINE_STAGES, PIPELINE_STAGE_LABELS } from '../../../shared/contracts/pipeline.contract'

export function StageBindingPanel() {
  return (
    <SectionCard
      title="阶段绑定"
      description="只改显示与 profile 绑定，不改后端固定 stage name。"
    >
      <div className="timeline">
        {PIPELINE_STAGES.map((stage, index) => (
          <div className="timeline-item" key={stage}>
            <span className="timeline-dot">{index + 1}</span>
            <strong>{PIPELINE_STAGE_LABELS[stage]}</strong>
            <span>{stage}</span>
          </div>
        ))}
      </div>
    </SectionCard>
  )
}
