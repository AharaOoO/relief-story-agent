/// <reference types="vite/client" />

declare global {
  interface Window {
    reliefDesktop?: {
      platform: string
      shell: string
      getRuntimeConfig: () => Promise<Record<string, unknown>>
      saveRuntimeConfig: (config: Record<string, unknown>) => Promise<{ config: Record<string, unknown>; handshake: DesktopHandshake }>
      getSecretStatus: () => Promise<Record<string, { configured: boolean; masked: string }>>
      saveSecret: (name: string, value: string) => Promise<{ status: { configured: boolean; masked: string }; handshake: DesktopHandshake }>
      deleteSecret: (name: string) => Promise<{ status: { configured: boolean; masked: string }; handshake: DesktopHandshake }>
      pickWorkflow: () => Promise<{ canceled: boolean; path?: string }>
      pickScript: () => Promise<{ canceled: boolean; path?: string; name?: string; content?: string }>
      pickDirectory: () => Promise<{ canceled: boolean; path?: string }>
      getPathForFile: (file: File) => string
      openPath: (targetPath: string) => Promise<{ opened: boolean }>
      restartBackend: () => Promise<DesktopHandshake>
      getHandshake: () => Promise<DesktopHandshake>
    }
  }
}

export {}

type DesktopHandshake = {
  backendUrl: string
  backendPort: number | null
  backendStatus: 'running' | 'stopped'
  backendLogPath: string
  backendLastError: string
  frontendPort: number | null
  platform: string
  version: string
}
