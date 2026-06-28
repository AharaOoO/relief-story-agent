import type { ReactNode } from 'react'

type EmptyStateProps = {
  title: string
  message: string
  action?: ReactNode
}

export function EmptyState({ title, message, action }: EmptyStateProps) {
  return (
    <div className="empty-state">
      <h3>{title}</h3>
      <p>{message}</p>
      {action ? <div className="button-row">{action}</div> : null}
    </div>
  )
}
