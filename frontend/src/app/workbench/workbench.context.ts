import { createContext, useContext } from 'react'

export type WorkbenchContextValue = { openSettings: () => void }

export const WorkbenchContext = createContext<WorkbenchContextValue>({
  openSettings: () => undefined,
})

export function useWorkbench() {
  return useContext(WorkbenchContext)
}
