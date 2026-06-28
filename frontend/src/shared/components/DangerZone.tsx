import { Button } from '@heroui/react'
import { AlertTriangle } from 'lucide-react'
import type { ReactNode } from 'react'

type DangerZoneProps = {
  title: string
  description: string
  actionLabel: string
  children?: ReactNode
  onAction?: () => void
}

export function DangerZone({
  title,
  description,
  actionLabel,
  children,
  onAction,
}: DangerZoneProps) {
  return (
    <div className="alert-box">
      <h3>
        <AlertTriangle size={18} /> {title}
      </h3>
      <p>{description}</p>
      {children}
      <div className="button-row" style={{ marginTop: 12 }}>
        <Button className="danger-button" onPress={onAction}>
          {actionLabel}
        </Button>
      </div>
    </div>
  )
}
