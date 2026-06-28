import { useQuery } from '@tanstack/react-query'
import { CopyButton } from '../../../shared/components/CopyButton'
import { ErrorState } from '../../../shared/components/ErrorState'
import { JsonViewer } from '../../../shared/components/JsonViewer'
import { StatusBadge } from '../../../shared/components/StatusBadge'
import { formatBytes } from '../../../shared/utils/formatBytes'
import { fetchBatchArtifacts, fetchRunArtifacts } from '../api/artifacts.api'

type ArtifactRow = {
  id?: string
  kind?: string
  name?: string
  path?: string
  exists?: boolean
  size?: number
  size_bytes?: number
}

function getArtifactRows(value: unknown): ArtifactRow[] {
  if (Array.isArray(value)) return value as ArtifactRow[]
  if (value && typeof value === 'object' && 'artifacts' in value) {
    const rows = (value as { artifacts?: unknown }).artifacts
    return Array.isArray(rows) ? (rows as ArtifactRow[]) : []
  }
  return []
}

export function ArtifactList({
  scope,
  targetId,
  kind,
}: {
  scope: 'run' | 'batch'
  targetId: string
  kind: string
}) {
  const artifacts = useQuery({
    queryKey: ['artifacts', scope, targetId],
    queryFn: () =>
      scope === 'run' ? fetchRunArtifacts(targetId) : fetchBatchArtifacts(targetId),
    enabled: targetId.trim().length > 0,
  })
  const rows = getArtifactRows(artifacts.data).filter((artifact) =>
    kind === 'all' ? true : artifact.kind === kind,
  )

  if (artifacts.error) {
    return (
      <ErrorState error={artifacts.error} onRetry={() => artifacts.refetch()} />
    )
  }

  return (
    <div className="stack">
      <div className="table-wrap">
        <table className="data-table">
          <thead>
            <tr>
              <th>artifact</th>
              <th>kind</th>
              <th>path</th>
              <th>status</th>
              <th>size</th>
              <th>action</th>
            </tr>
          </thead>
          <tbody>
            {rows.length > 0 ? (
              rows.map((artifact, index) => {
                const path = artifact.path ?? ''
                return (
                  <tr key={artifact.id ?? path ?? index}>
                    <td>{artifact.name ?? artifact.id ?? '-'}</td>
                    <td>{artifact.kind ?? '-'}</td>
                    <td>{path || '-'}</td>
                    <td>
                      <StatusBadge
                        status={artifact.exists === false ? 'blocked' : 'ready'}
                      />
                    </td>
                    <td>
                      {formatBytes(artifact.size_bytes ?? artifact.size ?? 0)}
                    </td>
                    <td>
                      {path ? (
                        <CopyButton value={path} label="复制路径" />
                      ) : (
                        '-'
                      )}
                    </td>
                  </tr>
                )
              })
            ) : (
              <tr>
                <td colSpan={6}>后端暂未返回匹配产物。</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      {artifacts.data ? (
        <div className="alert-box" role="status">
          <h3>Artifacts response</h3>
          <JsonViewer value={artifacts.data} />
        </div>
      ) : null}
    </div>
  )
}
