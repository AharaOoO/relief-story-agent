/// <reference types="vite/client" />

declare global {
  interface Window {
    reliefDesktop?: {
      platform: string
      shell: string
      getRuntimeConfig: () => Promise<Record<string, unknown>>
      saveRuntimeConfig: (config: Record<string, unknown>) => Promise<unknown>
      getSecretStatus: () => Promise<Record<string, { configured: boolean; masked: string }>>
      saveSecret: (name: string, value: string) => Promise<unknown>
      deleteSecret: (name: string) => Promise<unknown>
      pickWorkflow: () => Promise<{ canceled: boolean; path?: string }>
      pickScript: () => Promise<{ canceled: boolean; path?: string; name?: string; content?: string }>
      pickDirectory: () => Promise<{ canceled: boolean; path?: string }>
      openPath: (targetPath: string) => Promise<{ opened: boolean }>
      restartBackend: () => Promise<DesktopHandshake>
      getHandshake: () => Promise<DesktopHandshake>
    }
  }
}

type DesktopHandshake = {
  backendUrl: string
  backendPort: number
  backendStatus: 'running' | 'stopped'
  platform: string
  version: string
}
