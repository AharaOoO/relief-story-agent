import { create } from 'zustand'
import type { GenerationMode } from '../contracts/common.contract'

type UiStore = {
  sidebarCollapsed: boolean
  apiBaseUrl: string
  selectedGenerationMode: GenerationMode
  recentComfyUIEndpoint: string
  recentWorkflowPath: string
  setSidebarCollapsed: (value: boolean) => void
  setApiBaseUrl: (value: string) => void
  setSelectedGenerationMode: (value: GenerationMode) => void
  setRecentComfyUIEndpoint: (value: string) => void
  setRecentWorkflowPath: (value: string) => void
}

export const useUiStore = create<UiStore>((set) => ({
  sidebarCollapsed: false,
  apiBaseUrl: 'http://127.0.0.1:8891',
  selectedGenerationMode: 'local_comfyui',
  recentComfyUIEndpoint: 'http://127.0.0.1:8188',
  recentWorkflowPath: 'D:/ComfyUI/workflows/ltx23_four_grid.json',
  setSidebarCollapsed: (sidebarCollapsed) => set({ sidebarCollapsed }),
  setApiBaseUrl: (apiBaseUrl) => set({ apiBaseUrl }),
  setSelectedGenerationMode: (selectedGenerationMode) =>
    set({ selectedGenerationMode }),
  setRecentComfyUIEndpoint: (recentComfyUIEndpoint) =>
    set({ recentComfyUIEndpoint }),
  setRecentWorkflowPath: (recentWorkflowPath) => set({ recentWorkflowPath }),
}))
