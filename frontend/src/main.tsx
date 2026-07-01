import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import { applyDesktopHandshake } from './shared/api/desktopHandshake'

async function init() {
  // @ts-ignore
  if (window.reliefDesktop?.getHandshake) {
    try {
      // @ts-ignore
      const handshake = await window.reliefDesktop.getHandshake()
      applyDesktopHandshake(handshake)
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
