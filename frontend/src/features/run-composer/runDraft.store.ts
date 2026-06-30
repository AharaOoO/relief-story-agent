import { useCallback, useEffect, useState } from 'react'
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

export function useRunDraft() {
  const [draft, setDraft] = useState<RunDraft>(loadDraft)

  useEffect(() => {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(draft))
  }, [draft])

  const patchDraft = useCallback((patch: Partial<RunDraft>) => {
    setDraft((current) => ({ ...current, ...patch }))
  }, [])

  const resetDraft = useCallback(() => setDraft(createRunDraft()), [])

  return { draft, setDraft, patchDraft, resetDraft }
}
