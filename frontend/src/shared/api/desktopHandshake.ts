import { useUiStore } from '../store/uiStore'

type BackendHandshake = {
  backendUrl?: string
}

export function applyDesktopHandshake(handshake: BackendHandshake | null | undefined) {
  const backendUrl = handshake?.backendUrl?.trim()
  if (!backendUrl) return
  useUiStore.getState().setApiBaseUrl(backendUrl)
  if (typeof window !== 'undefined') {
    window.dispatchEvent(new CustomEvent('relief:backend-handshake', { detail: handshake }))
  }
}
