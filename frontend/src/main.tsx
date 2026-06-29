import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import { useUiStore } from './shared/store/uiStore'

async function init() {
  // @ts-ignore
  if (window.reliefDesktop?.getHandshake) {
    try {
      // @ts-ignore
      const handshake = await window.reliefDesktop.getHandshake()
      if (handshake.backendUrl) {
        useUiStore.getState().setApiBaseUrl(handshake.backendUrl)
      }
    } catch (e) {
      console.error('Handshake failed:', e)
    }
  }

  createRoot(document.getElementById('root')!).render(
    <StrictMode>
      <App />
    </StrictMode>,
  )
}

init()
