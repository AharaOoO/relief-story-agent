import { endpointPaths } from './endpointPaths'
import { requestJson } from './httpClient'
import type { ReadinessStatus } from '../contracts/readiness.contract'

export type HealthResponse = {
  status?: string
  ok?: boolean
  version?: string
  scheduler?: string
}

export function fetchHealth(): Promise<HealthResponse> {
  return requestJson<HealthResponse>(endpointPaths.health)
}

export function fetchReadiness(): Promise<ReadinessStatus> {
  return requestJson<ReadinessStatus>(endpointPaths.localReadiness)
}
