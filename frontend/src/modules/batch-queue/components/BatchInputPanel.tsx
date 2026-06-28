import { SectionCard } from '../../../shared/components/SectionCard'

type BatchInputPanelProps = {
  ideasText: string
  onIdeasTextChange: (value: string) => void
}

export function BatchInputPanel({
  ideasText,
  onIdeasTextChange,
}: BatchInputPanelProps) {
  return (
    <SectionCard
      title="Batch Input"
      description="每行一个 idea；plan 阶段不会创建任务。"
    >
      <div className="field">
        <label htmlFor="batch-ideas">Ideas</label>
        <textarea
          id="batch-ideas"
          value={ideasText}
          onChange={(event) => onIdeasTextChange(event.target.value)}
        />
      </div>
    </SectionCard>
  )
}
