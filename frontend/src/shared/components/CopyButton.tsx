import { Button } from '@heroui/react'
import { Check, Clipboard } from 'lucide-react'
import { useState } from 'react'

type CopyButtonProps = {
  value: string
  label?: string
}

export function CopyButton({ value, label = '复制' }: CopyButtonProps) {
  const [copyState, setCopyState] = useState<
    'idle' | 'copied' | 'failed' | 'manual'
  >('idle')
  const visibleLabel =
    copyState === 'copied'
      ? `${label}已复制`
      : copyState === 'manual'
        ? `${label}，请手动复制`
        : copyState === 'failed'
          ? `${label}失败`
          : label

  async function handleCopy() {
    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(value)
      } else {
        copyWithTextarea(value)
      }
      setCopyState('copied')
      window.setTimeout(() => setCopyState('idle'), 1800)
    } catch {
      try {
        copyWithTextarea(value)
        setCopyState('copied')
        window.setTimeout(() => setCopyState('idle'), 1800)
      } catch {
        setCopyState('manual')
      }
    }
  }

  return (
    <div className="stack" style={{ gap: 8 }}>
      <Button className="ghost-button" onPress={handleCopy}>
        {copyState === 'copied' ? <Check size={16} /> : <Clipboard size={16} />}
        {visibleLabel}
      </Button>
      {copyState === 'manual' ? (
        <textarea
          aria-label={`${label} value`}
          readOnly
          value={value}
          onFocus={(event) => event.currentTarget.select()}
        />
      ) : null}
    </div>
  )
}

function copyWithTextarea(value: string) {
  const textarea = document.createElement('textarea')
  textarea.value = value
  textarea.setAttribute('readonly', '')
  textarea.style.left = '-9999px'
  textarea.style.opacity = '0'
  textarea.style.position = 'fixed'
  document.body.appendChild(textarea)
  textarea.select()
  const copied = document.execCommand?.('copy') ?? false
  document.body.removeChild(textarea)

  if (!copied) {
    throw new Error('Fallback copy failed.')
  }
}
