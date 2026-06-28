import { describe, expect, it } from 'vitest'
import { normalizeApiError, redactSecretText } from './apiError'

describe('apiError', () => {
  it('turns fetch failures into a useful network error', () => {
    const error = normalizeApiError(new TypeError('fetch failed'), {
      endpoint: '/api/local/readiness',
    })

    expect(error.kind).toBe('network_error')
    expect(error.endpoint).toBe('/api/local/readiness')
    expect(error.suggestedAction).toContain('启动')
  })

  it('redacts API keys from diagnostic text', () => {
    const text = redactSecretText(
      'OPENAI_API_KEY=sk-live-value DEEPSEEK_API_KEY=secret-value',
    )

    expect(text).not.toContain('sk-live-value')
    expect(text).not.toContain('secret-value')
    expect(text).toContain('OPENAI_API_KEY=<redacted>')
  })
})
