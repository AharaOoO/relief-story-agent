import { Check, Circle, LoaderCircle, Minus, X } from 'lucide-react'
import { AUTOPILOT_STAGES, type AutopilotStageStatus } from './stages'

type StageRailProps = {
  selectedStage: string
  statuses: Record<string, AutopilotStageStatus>
  onSelect: (stageId: string) => void
}

function StatusIcon({ status }: { status: AutopilotStageStatus }) {
  if (status === 'completed') return <Check size={15} />
  if (status === 'running') return <LoaderCircle className="spin" size={15} />
  if (status === 'failed') return <X size={15} />
  if (status === 'skipped') return <Minus size={15} />
  return <Circle size={13} />
}

export function StageRail({ selectedStage, statuses, onSelect }: StageRailProps) {
  return (
    <ol className="stage-rail" aria-label="十道自动工序">
      {AUTOPILOT_STAGES.map((stage) => {
        const status = statuses[stage.id] ?? 'pending'
        return (
          <li key={stage.id}>
            <button type="button" className={selectedStage === stage.id ? 'is-selected' : ''} onClick={() => onSelect(stage.id)}>
              <span className="stage-order">{stage.order}</span>
              <span className="stage-rail-copy"><strong>{stage.label}</strong><small>{stage.title}</small></span>
              <span className={`stage-status-icon is-${status}`} title={status}><StatusIcon status={status} /></span>
            </button>
          </li>
        )
      })}
    </ol>
  )
}
