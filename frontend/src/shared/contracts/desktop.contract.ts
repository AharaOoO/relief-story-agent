export type DesktopSettings = {
  host: string
  backendPort: number
  frontendPort: number
  comfyUiEndpoint: string
  workflowPath: string
  stateDir: string
  logDir: string
}

export type DesktopState = {
  platform: string
  shell: 'electron'
  isDev: boolean
  settings: DesktopSettings
  settingsPath: string
  backendUrl: string
  frontendDevUrl: string
  uiOrigin: string
  backendRunning: boolean
  backendPid: number | null
}

export type DesktopBridge = {
  platform: string
  shell: 'electron'
  settings: {
    load: () => Promise<DesktopState>
    save: (settings: DesktopSettings) => Promise<DesktopState>
    reset: () => Promise<DesktopState>
  }
  backend: {
    restart: () => Promise<DesktopState>
    status: () => Promise<DesktopState>
  }
  logs: {
    open: () => Promise<{ opened: boolean; path: string; error: string | null }>
  }
}

declare global {
  interface Window {
    reliefDesktop?: DesktopBridge
  }
}

