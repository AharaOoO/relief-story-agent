import type { ReactNode } from 'react'

type PageHeaderProps = {
  title: string
  description?: string
  kicker?: string
  actions?: ReactNode
}

export function PageHeader({
  title,
  description,
  kicker = 'Creator Console',
  actions,
}: PageHeaderProps) {
  return (
    <header className="page-header">
      <div className="page-kicker">{kicker}</div>
      <h1 className="display-font">{title}</h1>
      {description ? <p>{description}</p> : null}
      {actions ? <div className="page-actions">{actions}</div> : null}
    </header>
  )
}
