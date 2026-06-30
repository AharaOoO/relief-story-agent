/// <reference types="vite/client" />

declare global {
  interface Window {
    reliefDesktop?: {
      platform: string
      shell: string
      getSettings: () => Promise<Record<string, string>>
      saveSettings: (settings: Record<string, string>) => Promise<void>
      getHandshake: () => Promise<any>
    }
  }
}
