import { create } from 'zustand'
import { createRunDraft, type RunDraft } from './runRequest.builder'

const STORAGE_KEY = 'relief-story-agent:run-draft:v2'

function loadDraft(): RunDraft {
  if (typeof window === 'undefined') return createRunDraft()
  try {
    const stored = JSON.parse(window.localStorage.getItem(STORAGE_KEY) ?? '{}') as Partial<RunDraft>
    return {
      ...createRunDraft(),
      ...stored,
      stageModels: stored.stageModels ?? {},
      stagePrompts: stored.stagePrompts ?? {},
    }
  } catch {
    return createRunDraft()
  }
}

function persistDraft(draft: RunDraft) {
  if (typeof window === 'undefined') return
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(draft))
}

type RunDraftStore = {
  draft: RunDraft
  setDraft: (draft: RunDraft) => void
  patchDraft: (patch: Partial<RunDraft>) => void
  resetDraft: () => void
}

export const useRunDraft = create<RunDraftStore>((set) => ({
  draft: loadDraft(),
  setDraft: (draft) => {
    persistDraft(draft)
    set({ draft })
  },
  patchDraft: (patch) => set((state) => {
    const draft = { ...state.draft, ...patch }
    persistDraft(draft)
    return { draft }
  }),
  resetDraft: () => {
    const draft = createRunDraft()
    persistDraft(draft)
    set({ draft })
  },
}))
