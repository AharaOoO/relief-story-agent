import { endpointPaths } from '../../../shared/api/endpointPaths'
import { postJson, requestJson } from '../../../shared/api/httpClient'

export function fetchRunArtifacts(runId: string): Promise<unknown> {
  return requestJson(endpointPaths.runArtifacts(runId))
}

export function fetchBatchArtifacts(batchId: string): Promise<unknown> {
  return requestJson(endpointPaths.batchArtifacts(batchId))
}

export function exportBatch(batchId: string, payload: unknown): Promise<unknown> {
  return postJson(endpointPaths.batchExport(batchId), payload)
}

export function validateBatchExport(
  batchId: string,
  payload: unknown,
): Promise<unknown> {
  return postJson(endpointPaths.batchExportValidate(batchId), payload)
}

export function validateBatchExportZip(
  batchId: string,
  payload: unknown,
): Promise<unknown> {
  return postJson(endpointPaths.batchExportValidateZip(batchId), payload)
}
