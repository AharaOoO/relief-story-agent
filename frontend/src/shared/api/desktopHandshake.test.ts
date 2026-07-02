import { describe, expect, it } from 'vitest'
import { useUiStore } from '../store/uiStore'
import { applyDesktopHandshake } from './desktopHandshake'

describe('desktop handshake', () => {
  it('switches every following API request to the restarted sidecar port', () => {
    useUiStore.getState().setApiBaseUrl('http://127.0.0.1:8891')

    applyDesktopHandshake({ backendUrl: 'http://127.0.0.1:13175' })

    expect(useUiStore.getState().apiBaseUrl).toBe('http://127.0.0.1:13175')
  })
})
