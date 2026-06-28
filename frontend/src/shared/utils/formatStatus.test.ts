import { describe, expect, it } from 'vitest'
import { getStatusTone, getStatusLabel } from './formatStatus'

describe('formatStatus', () => {
  it('maps known backend statuses to Chinese labels and visual tones', () => {
    expect(getStatusLabel('ready')).toBe('就绪')
    expect(getStatusTone('ready')).toBe('success')
    expect(getStatusLabel('awaiting_approval')).toBe('待审查')
    expect(getStatusTone('awaiting_approval')).toBe('warning')
    expect(getStatusLabel('failed')).toBe('失败')
    expect(getStatusTone('failed')).toBe('danger')
  })

  it('keeps unknown values safe instead of throwing', () => {
    expect(getStatusLabel('not_from_backend')).toBe('未知')
    expect(getStatusTone('not_from_backend')).toBe('neutral')
  })
})
