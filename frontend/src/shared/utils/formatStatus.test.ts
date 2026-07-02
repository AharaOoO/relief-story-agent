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

  it('covers pipeline and batch-specific statuses shown in the new UI', () => {
    expect(getStatusLabel('pending')).toBe('待命')
    expect(getStatusLabel('waiting')).toBe('等待确认')
    expect(getStatusLabel('skipped')).toBe('已跳过')
    expect(getStatusLabel('partial_failed')).toBe('部分失败')
    expect(getStatusTone('partial_failed')).toBe('danger')
  })
})
