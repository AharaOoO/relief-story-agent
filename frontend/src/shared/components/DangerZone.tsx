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
    <div className="liquid-glass bg-red-500/10 backdrop-blur-xl border border-red-500/30 shadow-[0_8px_32px_rgba(239,68,68,0.15)] rounded-3xl p-6">
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
