import { endpointPaths } from '../../../shared/api/endpointPaths'
import { postJson, requestJson } from '../../../shared/api/httpClient'

export function planBatch(payload: unknown): Promise<unknown> {
  return postJson(
    `${endpointPaths.batchPlan}?check_comfyui_connection=false`,
    payload,
  )
}

export function createBatch(payload: unknown): Promise<{ batch_id: string }> {
  return postJson(
    `${endpointPaths.batches}?preflight=false&check_comfyui_connection=false`,
    payload,
  )
}

export function fetchBatches(): Promise<unknown> {
  return requestJson(endpointPaths.batches)
}

export function fetchBatchTimeline(batchId: string): Promise<unknown> {
  return requestJson(endpointPaths.batchTimeline(batchId))
}

export function pauseBatch(batchId: string): Promise<unknown> {
  return postJson(endpointPaths.batchPause(batchId), null)
}

export function resumeBatch(batchId: string): Promise<unknown> {
  return postJson(endpointPaths.batchResume(batchId), null)
}

export function cancelBatch(batchId: string): Promise<unknown> {
  return postJson(endpointPaths.batchCancel(batchId), null)
}

export function retryBatch(batchId: string): Promise<unknown> {
  return postJson(endpointPaths.batchRetry(batchId), {})
}

export function exportBatchArtifacts(batchId: string): Promise<unknown> {
  return postJson(endpointPaths.batchExport(batchId), {
    export_root: 'D:/relief_story_exports',
    include_zip: true,
  })
}
