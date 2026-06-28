import { endpointPaths } from '../../../shared/api/endpointPaths'
import { postJson, requestJson } from '../../../shared/api/httpClient'

export function fetchRunTimeline(runId: string): Promise<unknown> {
  return requestJson(endpointPaths.runTimeline(runId))
}

export function fetchRunEvents(runId: string): Promise<unknown> {
  return requestJson(endpointPaths.runEvents(runId))
}

export function approveRun(runId: string): Promise<unknown> {
  return postJson(endpointPaths.runApprove(runId), {})
}

export function retryRun(runId: string): Promise<unknown> {
  return postJson(endpointPaths.runRetry(runId), {})
}

export function cancelRun(runId: string): Promise<unknown> {
  return postJson(endpointPaths.runCancel(runId), null)
}
