import { Button } from '@heroui/react'

type ConfirmDialogProps = {
  open: boolean
  title: string
  description: string
  confirmText?: string
  cancelText?: string
  variant?: 'default' | 'danger'
  onConfirm: () => void | Promise<void>
  onCancel: () => void
}

export function ConfirmDialog({
  open,
  title,
  description,
  confirmText = '确认',
  cancelText = '取消',
  variant = 'default',
  onConfirm,
  onCancel,
}: ConfirmDialogProps) {
  if (!open) return null

  return (
    <div className="dialog-backdrop" role="presentation">
      <section className="dialog-panel" role="dialog" aria-modal="true">
        <h2 className="display-font" style={{ margin: 0 }}>
          {title}
        </h2>
        <p>{description}</p>
        <div className="button-row">
          <Button
            className={variant === 'danger' ? 'danger-button' : 'hero-button'}
            onPress={onConfirm}
          >
            {confirmText}
          </Button>
          <Button className="secondary-button" onPress={onCancel}>
            {cancelText}
          </Button>
        </div>
      </section>
    </div>
  )
}
