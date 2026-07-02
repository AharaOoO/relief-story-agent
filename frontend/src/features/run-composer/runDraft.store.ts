import { create } from 'zustand'
import {
  createRunDraft,
  createStandardStageModels,
  MODEL_STAGE_IDS,
  normalizeDurationSeconds,
  type RunDraft,
} from './runRequest.builder'

const STORAGE_KEY = 'relief-story-agent:run-draft:v6'
const LEGACY_STORAGE_KEYS = [
  'relief-story-agent:run-draft:v5',
  'relief-story-agent:run-draft:v4',
  'relief-story-agent:run-draft:v3',
  'relief-story-agent:run-draft:v2',
]

function shouldMigrateLegacyRunningHubModels(stored: Partial<RunDraft>): boolean {
  const stageModels = stored.stageModels
  if (!stageModels) return false
  return MODEL_STAGE_IDS.some((stageId) => stageModels[stageId]?.provider_mode === 'runninghub')
}

function mergeStoredDraft(stored: Partial<RunDraft>, migrateLegacyModels = false): RunDraft {
  const base = createRunDraft()
  const stageModels = {
    ...base.stageModels,
    ...(stored.stageModels ?? {}),
  }
  if (migrateLegacyModels && shouldMigrateLegacyRunningHubModels(stored)) {
    const standardModels = createStandardStageModels()
    for (const stageId of MODEL_STAGE_IDS) {
      if (stageModels[stageId]?.provider_mode === 'runninghub') {
        stageModels[stageId] = standardModels[stageId]
      }
    }
  }
  return {
    ...base,
    ...stored,
    durationSeconds: normalizeDurationSeconds(stored.durationSeconds ?? base.durationSeconds),
    gridImageSite: stored.gridImageSite ?? stored.runninghubSite ?? base.gridImageSite,
    stageModels,
    stagePrompts: stored.stagePrompts ?? base.stagePrompts,
  }
}

function parseStoredDraft(value: string | null): Partial<RunDraft> | null {
  if (!value) return null
  try {
    return JSON.parse(value) as Partial<RunDraft>
  } catch {
    return null
  }
}

function loadDraft(): RunDraft {
  if (typeof window === 'undefined') return createRunDraft()
  const current = parseStoredDraft(window.localStorage.getItem(STORAGE_KEY))
  if (current) return mergeStoredDraft(current)

  for (const legacyKey of LEGACY_STORAGE_KEYS) {
    const legacy = parseStoredDraft(window.localStorage.getItem(legacyKey))
    if (legacy) {
      const migrated = mergeStoredDraft(legacy, true)
      persistDraft(migrated)
      return migrated
    }
  }

  return createRunDraft()
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
