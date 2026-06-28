import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { CopyButton } from './CopyButton'

describe('CopyButton', () => {
  beforeEach(() => {
    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      value: {
        writeText: vi.fn().mockResolvedValue(undefined),
      },
    })
  })

  it('shows copied feedback after the clipboard write succeeds', async () => {
    render(<CopyButton value="relief-story-agent serve" label="Copy command" />)

    fireEvent.click(screen.getByRole('button', { name: 'Copy command' }))

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /已复制/ })).toBeInTheDocument()
    })
    expect(navigator.clipboard.writeText).toHaveBeenCalledWith(
      'relief-story-agent serve',
    )
  })

  it('falls back to a temporary textarea when clipboard API is unavailable', async () => {
    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      value: undefined,
    })
    document.execCommand = vi.fn().mockReturnValue(true)
    render(<CopyButton value="fallback command" label="Copy command" />)

    fireEvent.click(screen.getByRole('button', { name: 'Copy command' }))

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /已复制/ })).toBeInTheDocument()
    })
    expect(document.execCommand).toHaveBeenCalledWith('copy')
  })

  it('shows a manual copy field when browser copy APIs are unavailable', async () => {
    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      value: undefined,
    })
    document.execCommand = undefined as unknown as typeof document.execCommand
    render(<CopyButton value="manual command" label="Copy command" />)

    fireEvent.click(screen.getByRole('button', { name: 'Copy command' }))

    await waitFor(() => {
      expect(
        screen.getByRole('button', { name: /手动复制/ }),
      ).toBeInTheDocument()
    })
    expect(screen.getByLabelText('Copy command value')).toHaveValue(
      'manual command',
    )
  })
})
