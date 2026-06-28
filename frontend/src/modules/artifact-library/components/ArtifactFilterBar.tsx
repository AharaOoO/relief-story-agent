import { SectionCard } from '../../../shared/components/SectionCard'

type ArtifactFilterBarProps = {
  scope: 'run' | 'batch'
  targetId: string
  kind: string
  onScopeChange: (scope: 'run' | 'batch') => void
  onTargetIdChange: (id: string) => void
  onKindChange: (kind: string) => void
}

export function ArtifactFilterBar({
  scope,
  targetId,
  kind,
  onScopeChange,
  onTargetIdChange,
  onKindChange,
}: ArtifactFilterBarProps) {
  return (
    <SectionCard title="筛选" description="run/batch scope 与 artifact kind。">
      <div className="grid-three">
        <div className="field">
          <label htmlFor="scope">Scope</label>
          <select
            id="scope"
            value={scope}
            onChange={(event) => onScopeChange(event.target.value as 'run' | 'batch')}
          >
            <option value="run">run</option>
            <option value="batch">batch</option>
          </select>
        </div>
        <div className="field">
          <label htmlFor="artifact-kind">Kind</label>
          <select
            id="artifact-kind"
            value={kind}
            onChange={(event) => onKindChange(event.target.value)}
          >
            <option value="all">all</option>
            <option value="video">video</option>
            <option value="manifest">manifest</option>
            <option value="prompt">prompt</option>
          </select>
        </div>
        <div className="field">
          <label htmlFor="artifact-id">ID</label>
          <input
            id="artifact-id"
            value={targetId}
            onChange={(event) => onTargetIdChange(event.target.value)}
          />
        </div>
      </div>
    </SectionCard>
  )
}
