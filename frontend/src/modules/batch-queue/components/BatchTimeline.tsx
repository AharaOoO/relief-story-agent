import { StatusBadge } from '../../../shared/components/StatusBadge'
import { sampleBatchRows } from '../../../shared/fixtures/sampleBatch'
import { RecommendedActionBadge } from './RecommendedActionBadge'

export function BatchTimeline() {
  return (
    <div className="table-wrap">
      <table className="data-table">
        <thead>
          <tr>
            <th>run</th>
            <th>idea</th>
            <th>status</th>
            <th>stage</th>
            <th>action</th>
          </tr>
        </thead>
        <tbody>
          {sampleBatchRows.map((row) => (
            <tr key={row.run_id}>
              <td>{row.run_id}</td>
              <td>{row.idea}</td>
              <td>
                <StatusBadge status={row.status} />
              </td>
              <td>
                <strong>{row.active_stage}</strong>
                <div
                  className="progress-line"
                  aria-label={row.run_id}
                  role="progressbar"
                  aria-valuemin={0}
                  aria-valuemax={100}
                  aria-valuenow={row.stage_percent}
                >
                  <span style={{ width: `${row.stage_percent}%` }} />
                </div>
              </td>
              <td>
                <RecommendedActionBadge code={row.recommended_action} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
