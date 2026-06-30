import { Card } from '@heroui/react'
import type { ReactNode } from 'react'

type SectionCardProps = {
  title: string
  description?: string
  children: ReactNode
  footer?: ReactNode
  tone?: 'default' | 'yellow' | 'blue'
  action?: ReactNode
}

export function SectionCard({
  title,
  description,
  children,
  footer,
  tone = 'default',
  action,
}: SectionCardProps) {
  const toneClass =
    tone === 'yellow' ? ' is-yellow' : tone === 'blue' ? ' is-blue' : ''

  return (
    <Card className={`section-card${toneClass} liquid-glass bg-white/20 backdrop-blur-2xl border border-white/50 shadow-[0_8px_32px_rgba(88,135,255,0.1)] rounded-3xl overflow-hidden`}>
      <Card.Header className="section-card__header">
        <div>
          <Card.Title className="section-card__title">{title}</Card.Title>
          {description ? (
            <Card.Description className="section-card__description">
              {description}
            </Card.Description>
          ) : null}
        </div>
        {action}
      </Card.Header>
      <Card.Content className="section-card__content">{children}</Card.Content>
      {footer ? (
        <Card.Footer className="section-card__footer">{footer}</Card.Footer>
      ) : null}
    </Card>
  )
}
