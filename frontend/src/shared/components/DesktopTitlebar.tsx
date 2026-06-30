import React from 'react'

declare global {
  interface Window {
    reliefDesktop?: {
      platform: string
      shell: string
      getSettings: () => Promise<any>
      saveSettings: (settings: any) => Promise<any>
      getHandshake: () => Promise<{
        backendUrl: string
        backendPort: number
        platform: string
        version: string
      }>
    }
  }
}

export function DesktopTitlebar() {
  const isDesktop = typeof window !== 'undefined' && !!window.reliefDesktop
  if (!isDesktop) return null

  const isMac = window.reliefDesktop?.platform === 'darwin'

  return (
    <div
      className="fixed top-0 left-0 right-0 h-9 flex items-center justify-between px-4 bg-bg border-b border-stroke select-none shrink-0 z-[10000]"
      style={{ WebkitAppRegion: 'drag' } as React.CSSProperties}
    >
      {/* For Mac: push content right to clear traffic lights */}
      {isMac ? (
        <div className="w-[80px] shrink-0" />
      ) : null}

      <div className="flex-1 flex items-center justify-center">
        <span className="text-[10px] font-bold uppercase tracking-[0.25em] text-muted/70">
          LTX 2.3 Studio Console
        </span>
      </div>

      {/* For Windows: push content left to clear window controls */}
      {!isMac ? (
        <div className="w-[140px] shrink-0" />
      ) : null}
    </div>
  )
}
