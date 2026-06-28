import type { RunRequest } from '../contracts/run.contract'

type RunRequestFormProps = {
  value: RunRequest
  onChange: (value: RunRequest) => void
}

export function RunRequestForm({ value, onChange }: RunRequestFormProps) {
  return (
    <div className="form-grid">
      <div className="field">
        <label htmlFor="run-idea">创作目标</label>
        <textarea
          id="run-idea"
          placeholder="例如：一个深夜下班的人，在便利店门口被一杯热饮安慰。"
          value={value.idea}
          onChange={(event) => onChange({ ...value, idea: event.target.value })}
        />
      </div>
      <div className="grid-two">
        <div className="field">
          <label htmlFor="duration">时长</label>
          <input
            id="duration"
            min={6}
            max={120}
            type="number"
            value={value.duration_seconds}
            onChange={(event) =>
              onChange({
                ...value,
                duration_seconds: Number(event.target.value),
              })
            }
          />
        </div>
        <div className="field">
          <label htmlFor="approval">审查模式</label>
          <select
            id="approval"
            value={value.approval_mode}
            onChange={(event) =>
              onChange({
                ...value,
                approval_mode: event.target.value as RunRequest['approval_mode'],
              })
            }
          >
            <option value="manual">人工审查</option>
            <option value="auto_after_audit_pass">Audit 通过后自动</option>
          </select>
        </div>
      </div>
    </div>
  )
}
