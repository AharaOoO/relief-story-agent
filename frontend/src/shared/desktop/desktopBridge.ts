import type { DesktopBridge } from '../contracts/desktop.contract'

export function getDesktopBridge(): DesktopBridge | null {
  return window.reliefDesktop ?? null
}

