import type React from 'react'

export function DesktopTitlebar() {
  const isDesktop = typeof window !== 'undefined' && !!window.reliefDesktop
  if (!isDesktop) return null

  const isMac = window.reliefDesktop?.platform === 'darwin'

  return (
    <div
      className="desktop-titlebar"
      style={{ WebkitAppRegion: 'drag' } as React.CSSProperties}
    >
      {/* For Mac: push content right to clear traffic lights */}
      {isMac ? (
        <div className="w-[80px] shrink-0" />
      ) : null}

      <div className="flex-1 flex items-center justify-center">
        <span>
          RELIEF STORY AGENT · LTX 2.3
        </span>
      </div>

      {/* For Windows: push content left to clear window controls */}
      {!isMac ? (
        <div className="w-[140px] shrink-0" />
      ) : null}
    </div>
  )
}
