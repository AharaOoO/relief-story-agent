import { Chip } from '@heroui/react'
import { getStatusLabel, getStatusTone } from '../utils/formatStatus'

type StatusBadgeProps = {
  status: string
  label?: string
}

export function StatusBadge({ status, label }: StatusBadgeProps) {
  return (
    <Chip className={`status-chip tone-${getStatusTone(status)}`}>
      {label ?? getStatusLabel(status)}
    </Chip>
  )
}
