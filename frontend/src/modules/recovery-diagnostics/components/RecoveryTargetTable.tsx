import { StatusBadge } from '../../../shared/components/StatusBadge'

const rows = [
  {
    run_id: 'run_window_003',
    failed_stage: 'comfyui',
    error_kind: 'external',
    action_code: 'refresh_comfyui_outputs',
  },
  {
    run_id: 'run_rain_002',
    failed_stage: 'gpt_prompt_audit',
    error_kind: 'manual_review',
    action_code: 'manual_review_prompt_audit',
  },
]

export function RecoveryTargetTable() {
  return (
    <div className="table-wrap">
      <table className="data-table">
        <thead>
          <tr>
            <th>run_id</th>
            <th>failed_stage</th>
            <th>error_kind</th>
            <th>action</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.run_id}>
              <td>{row.run_id}</td>
              <td>{row.failed_stage}</td>
              <td>
                <StatusBadge
                  status={row.error_kind === 'external' ? 'warning' : 'blocked'}
                  label={row.error_kind}
                />
              </td>
              <td>{row.action_code}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
