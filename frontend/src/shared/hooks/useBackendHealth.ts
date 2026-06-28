import { useQuery } from '@tanstack/react-query'
import { fetchHealth, fetchReadiness } from '../api/status.api'

export function useBackendHealth() {
  return useQuery({
    queryKey: ['backend-health'],
    queryFn: fetchHealth,
    refetchInterval: 15_000,
  })
}

export function useLocalReadiness() {
  return useQuery({
    queryKey: ['local-readiness'],
    queryFn: fetchReadiness,
    refetchInterval: 15_000,
  })
}
