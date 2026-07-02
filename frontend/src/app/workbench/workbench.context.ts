import { createContext, useContext } from 'react'

export type SettingsTab = 'secrets' | 'prompts' | 'comfyui' | 'image' | 'storage' | 'diagnostics'

export type WorkbenchContextValue = { openSettings: (tab?: SettingsTab) => void }

export const WorkbenchContext = createContext<WorkbenchContextValue>({
  openSettings: () => undefined,
})

export function useWorkbench() {
  return useContext(WorkbenchContext)
}
