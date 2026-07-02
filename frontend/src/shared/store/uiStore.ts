import { create } from 'zustand'
import type { GenerationMode } from '../contracts/common.contract'

type UiStore = {
  apiBaseUrl: string
  selectedGenerationMode: GenerationMode
  recentComfyUIEndpoint: string
  recentWorkflowPath: string
  setApiBaseUrl: (value: string) => void
  setSelectedGenerationMode: (value: GenerationMode) => void
  setRecentComfyUIEndpoint: (value: string) => void
  setRecentWorkflowPath: (value: string) => void
}

export const useUiStore = create<UiStore>((set) => ({
  apiBaseUrl: 'http://127.0.0.1:8891',
  selectedGenerationMode: 'local_comfyui',
  recentComfyUIEndpoint: 'http://127.0.0.1:8188',
  recentWorkflowPath: 'D:/ComfyUI/workflows/ltx23_four_grid.json',
  setApiBaseUrl: (apiBaseUrl) => set({ apiBaseUrl }),
  setSelectedGenerationMode: (selectedGenerationMode) =>
    set({ selectedGenerationMode }),
  setRecentComfyUIEndpoint: (recentComfyUIEndpoint) =>
    set({ recentComfyUIEndpoint }),
  setRecentWorkflowPath: (recentWorkflowPath) => set({ recentWorkflowPath }),
}))
