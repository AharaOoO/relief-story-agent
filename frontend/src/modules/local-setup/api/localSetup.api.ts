import { endpointPaths } from '../../../shared/api/endpointPaths'
import { postJson, requestJson } from '../../../shared/api/httpClient'
import type { ReadinessStatus } from '../../../shared/contracts/readiness.contract'
import type {
  BootstrapInfo,
  ComfyUIConnectionRequest,
  WorkflowDiscoveryResult,
} from '../contracts/localSetup.contract'

export function fetchLocalBootstrap(): Promise<BootstrapInfo> {
  return requestJson<BootstrapInfo>(endpointPaths.localBootstrap)
}

export function fetchLocalReadiness(): Promise<ReadinessStatus> {
  return requestJson<ReadinessStatus>(endpointPaths.localReadiness)
}

export function fetchLocalDoctor(params: {
  checkComfyUIConnection?: boolean
  comfyuiEndpoint?: string
  comfyuiWorkflowPath?: string
  comfyuiTimeoutSeconds?: number
}): Promise<unknown> {
  const query = new URLSearchParams()

  if (params.checkComfyUIConnection !== undefined) {
    query.set(
      'check_comfyui_connection',
      String(params.checkComfyUIConnection),
    )
  }
  if (params.comfyuiEndpoint) {
    query.set('comfyui_endpoint', params.comfyuiEndpoint)
  }
  if (params.comfyuiWorkflowPath) {
    query.set('comfyui_workflow_path', params.comfyuiWorkflowPath)
  }
  if (params.comfyuiTimeoutSeconds !== undefined) {
    query.set('comfyui_timeout_seconds', String(params.comfyuiTimeoutSeconds))
  }

  const suffix = query.toString() ? `?${query}` : ''
  return requestJson(`${endpointPaths.localDoctor}${suffix}`)
}

export function writeSetupBundle(payload: unknown): Promise<unknown> {
  return postJson(endpointPaths.localSetupBundle, payload)
}

export function connectComfyUI(
  payload: ComfyUIConnectionRequest,
): Promise<{ ready?: boolean; detail?: string }> {
  return postJson(endpointPaths.comfyuiConnect, payload)
}

export function discoverWorkflows(payload: {
  endpoint: string
  search_roots: string[]
  max_results: number
  include_unsupported: boolean
  filename_keywords: string[]
}): Promise<{ workflows: WorkflowDiscoveryResult[] }> {
  return postJson(endpointPaths.comfyuiDiscoverWorkflows, payload)
}
