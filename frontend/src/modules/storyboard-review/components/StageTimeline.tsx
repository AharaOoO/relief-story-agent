import { StatusBadge } from '../../../shared/components/StatusBadge'
import { PIPELINE_STAGE_LABELS } from '../../../shared/contracts/pipeline.contract'
import { sampleTimeline } from '../../../shared/fixtures/sampleRun'

export function StageTimeline() {
  return (
    <div className="timeline">
      {sampleTimeline.map((item, index) => (
        <div
          className={`timeline-item${item.status === 'awaiting_approval' ? ' is-active' : ''}`}
          key={item.stage}
        >
          <span className="timeline-dot">{index + 1}</span>
          <div>
            <strong>{PIPELINE_STAGE_LABELS[item.stage]}</strong>
            <div
              className="progress-line"
              aria-label={PIPELINE_STAGE_LABELS[item.stage]}
              role="progressbar"
              aria-valuemin={0}
              aria-valuemax={100}
              aria-valuenow={item.percent}
            >
              <span style={{ width: `${item.percent}%` }} />
            </div>
          </div>
          <StatusBadge status={item.status} />
        </div>
      ))}
    </div>
  )
}
