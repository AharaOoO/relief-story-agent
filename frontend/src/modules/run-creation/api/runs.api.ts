import { endpointPaths } from '../../../shared/api/endpointPaths'
import { postJson, requestJson } from '../../../shared/api/httpClient'
import { toBackendRunRequest } from '../../../shared/api/backendPayloads'
import type { RunRequest, PreflightResult } from '../contracts/run.contract'

export function preflightRun(payload: RunRequest): Promise<PreflightResult> {
  return postJson(
    `${endpointPaths.configValidate}?check_comfyui_connection=false`,
    toBackendRunRequest(payload),
  )
}

export function createRun(payload: RunRequest): Promise<{ run_id: string }> {
  return postJson(
    `${endpointPaths.runs}?preflight=false&check_comfyui_connection=false`,
    toBackendRunRequest(payload),
  )
}

export function fetchRun(runId: string): Promise<unknown> {
  return requestJson(endpointPaths.runDetail(runId))
}
