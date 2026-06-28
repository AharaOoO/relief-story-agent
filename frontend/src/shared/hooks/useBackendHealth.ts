import { useQuery } from '@tanstack/react-query'
import { fetchHealth, fetchReadiness } from '../api/status.api'
import { useUiStore } from '../store/uiStore'

export function useBackendHealth() {
  const apiBaseUrl = useUiStore((state) => state.apiBaseUrl)

  return useQuery({
    queryKey: ['backend-health', apiBaseUrl],
    queryFn: fetchHealth,
    refetchInterval: 15_000,
  })
}

export function useLocalReadiness() {
  const apiBaseUrl = useUiStore((state) => state.apiBaseUrl)

  return useQuery({
    queryKey: ['local-readiness', apiBaseUrl],
    queryFn: fetchReadiness,
    refetchInterval: 15_000,
  })
}
