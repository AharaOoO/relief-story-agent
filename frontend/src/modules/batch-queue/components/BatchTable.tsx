import { useQuery } from '@tanstack/react-query'
import { ErrorState } from '../../../shared/components/ErrorState'
import { JsonViewer } from '../../../shared/components/JsonViewer'
import { StatusBadge } from '../../../shared/components/StatusBadge'
import { fetchBatches } from '../api/batches.api'

type BatchRow = {
  id?: string
  batch_id?: string
  status?: string
  total?: number
  completed?: number
  failed?: number
}

function getBatchRows(value: unknown): BatchRow[] {
  if (Array.isArray(value)) return value as BatchRow[]
  if (value && typeof value === 'object' && 'batches' in value) {
    const rows = (value as { batches?: unknown }).batches
    return Array.isArray(rows) ? (rows as BatchRow[]) : []
  }
  return []
}

export function BatchTable() {
  const batches = useQuery({
    queryKey: ['batches'],
    queryFn: fetchBatches,
  })
  const rows = getBatchRows(batches.data)

  if (batches.error) {
    return <ErrorState error={batches.error} onRetry={() => batches.refetch()} />
  }

  return (
    <div className="stack">
      <div className="table-wrap">
        <table className="data-table">
          <thead>
            <tr>
              <th>batch_id</th>
              <th>status</th>
              <th>total</th>
              <th>completed</th>
              <th>failed</th>
            </tr>
          </thead>
          <tbody>
            {rows.length > 0 ? (
              rows.map((row) => {
                const id = row.batch_id ?? row.id ?? 'unknown'
                return (
                  <tr key={id}>
                    <td>{id}</td>
                    <td>
                      <StatusBadge status={row.status ?? 'unknown'} />
                    </td>
                    <td>{row.total ?? '-'}</td>
                    <td>{row.completed ?? '-'}</td>
                    <td>{row.failed ?? '-'}</td>
                  </tr>
                )
              })
            ) : (
              <tr>
                <td colSpan={5}>后端暂未返回 batch 列表。</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      {batches.data ? (
        <div className="alert-box" role="status">
          <h3>Batches response</h3>
          <JsonViewer value={batches.data} />
        </div>
      ) : null}
    </div>
  )
}
