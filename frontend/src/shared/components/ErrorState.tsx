import { Button } from '@heroui/react'
import { normalizeApiError } from '../api/apiError'
import { safeJson } from '../utils/safeJson'
import { CopyButton } from './CopyButton'

type ErrorStateProps = {
  title?: string
  error: unknown
  onRetry?: () => void
}

export function ErrorState({ title, error, onRetry }: ErrorStateProps) {
  const normalized = normalizeApiError(error)
  const diagnostic = safeJson(normalized)

  return (
    <div className="alert-box" role="alert">
      <h3>{title ?? normalized.title}</h3>
      <p>{normalized.message}</p>
      {normalized.suggestedAction ? <p>{normalized.suggestedAction}</p> : null}
      <div className="button-row" style={{ marginTop: 12 }}>
        {onRetry ? (
          <Button className="secondary-button" onPress={onRetry}>
            重试
          </Button>
        ) : null}
        <CopyButton value={diagnostic} label="复制诊断" />
      </div>
    </div>
  )
}
