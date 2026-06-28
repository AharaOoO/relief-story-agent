import { endpointPaths } from '../../../shared/api/endpointPaths'
import { postJson, requestJson } from '../../../shared/api/httpClient'

export function fetchBatchRecoveryPlan(batchId: string): Promise<unknown> {
  return requestJson(endpointPaths.batchRecoveryPlan(batchId))
}

export function recoverBatch(batchId: string, payload: unknown): Promise<unknown> {
  return postJson(endpointPaths.batchRecover(batchId), payload)
}

export function fetchAcceptanceStatus(): Promise<unknown> {
  return requestJson(endpointPaths.localAcceptanceStatus)
}
