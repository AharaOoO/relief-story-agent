import { endpointPaths } from '../../shared/api/endpointPaths'
import { postJson, requestJson } from '../../shared/api/httpClient'
import type {
  BatchRequestPayload,
  ModelStageId,
  RunRequestPayload,
} from '../run-composer/runRequest.builder'
import type { TimelineEntry } from '../autopilot/stages'

export type ProviderCatalog = {
  runninghub: Record<
    'cn' | 'ai',
    {
      base_url: string
      api_key_env: string
      stages: Record<string, string[]>
    }
  >
}

export type PreflightResult = {
  ready: boolean
  passed?: boolean
  blockers: PreflightIssue[]
  warnings: PreflightIssue[]
  suggested_actions?: Array<{ code: string; label: string; description: string }>
  checks?: Array<{ name: string; status: string; message: string }>
}

export type PreflightIssue = string | {
  check?: string
  code?: string
  message?: string
  description?: string
  details?: Record<string, unknown>
}

export function formatPreflightIssue(issue: PreflightIssue): string {
  if (typeof issue === 'string') return issue
  return issue.message ?? issue.description ?? issue.check ?? issue.code ?? '配置检查未通过'
}

export type RunSummary = {
  run_id: string
  status: string
  current_stage: string
  idea?: string
  created_at?: string
  updated_at?: string
  progress?: number
}

export type RunDetail = RunSummary & {
  request?: RunRequestPayload
  prompt_snapshot?: Partial<Record<string, string>>
  error?: string
  outputs?: Record<string, unknown>
  parent_batch_id?: string
}

export type ListResponse<T> = {
  total: number
  limit: number
  items: T[]
}

export type BatchSummary = {
  batch_id: string
  status: string
  paused?: boolean
  item_count?: number
  summary?: Record<string, number>
  items?: Array<{ run_id?: string; idea?: string; status: string; current_stage?: string; error?: string }>
  total_items?: number
  completed_items?: number
  failed_items?: number
  created_at?: string
  updated_at?: string
}

export type ArtifactRecord = {
  id?: string
  artifact_id?: string
  run_id?: string
  kind?: string
  type?: string
  path?: string
  local_path?: string
  name?: string
  created_at?: string
  metadata?: Record<string, unknown>
}

export type RunEventRecord = {
  sequence: number
  event_type: string
  stage?: string
  message?: string
  data?: Record<string, unknown>
}

export type RunEventsResponse = {
  run_id: string
  after: number
  next_cursor: number
  is_terminal: boolean
  events: RunEventRecord[]
}

export type ComfyUIConnectionReport = {
  connected?: boolean
  ready?: boolean
  endpoint?: string
  checks?: Array<{ name: string; status: string; message: string }>
  workflow?: Record<string, unknown>
  [key: string]: unknown
}

export type PromptProfile = {
  id: string
  name: string
  description: string
  version: number
  source: 'system' | 'user' | 'imported'
  content_hash?: string
  created_at?: string
  updated_at?: string
  stages: Partial<Record<ModelStageId, string>>
}

export function fetchProviderCatalog(): Promise<ProviderCatalog> {
  return requestJson(endpointPaths.providerCatalog)
}

export function validateRun(payload: RunRequestPayload): Promise<PreflightResult> {
  return postJson(
    `${endpointPaths.configValidate}?check_comfyui_connection=true`,
    payload,
  )
}

export function createRun(payload: RunRequestPayload): Promise<RunDetail> {
  return postJson(
    `${endpointPaths.runs}?preflight=true&check_comfyui_connection=true`,
    payload,
  )
}

export function createBatch(payload: BatchRequestPayload): Promise<BatchSummary> {
  return postJson(
    `${endpointPaths.batches}?preflight=true&check_comfyui_connection=true`,
    payload,
  )
}

export function listRuns(): Promise<ListResponse<RunSummary>> {
  return requestJson(`${endpointPaths.runs}?limit=100`)
}

export function fetchRun(runId: string): Promise<RunDetail> {
  return requestJson(endpointPaths.runDetail(runId))
}

export async function fetchTimeline(runId: string): Promise<TimelineEntry[]> {
  const response = await requestJson<TimelineEntry[] | { items?: TimelineEntry[]; stages?: TimelineEntry[] }>(
    endpointPaths.runTimeline(runId),
  )
  return Array.isArray(response) ? response : (response.stages ?? response.items ?? [])
}

export async function fetchRunArtifacts(runId: string): Promise<ArtifactRecord[]> {
  const response = await requestJson<
    ArtifactRecord[] | {
      items?: ArtifactRecord[]
      artifacts?: ArtifactRecord[]
      actual_outputs?: Array<{ media_type?: string; filename?: string; local_path?: string; url?: string; prompt_id?: string }>
    }
  >(endpointPaths.runArtifacts(runId))
  if (Array.isArray(response)) return response
  const artifacts = response.items ?? response.artifacts ?? []
  const outputs: ArtifactRecord[] = (response.actual_outputs ?? []).map((output, index) => ({
    id: `${output.prompt_id ?? runId}-output-${index}`,
    run_id: runId,
    kind: output.media_type ?? 'output',
    name: output.filename ?? 'ComfyUI output',
    local_path: output.local_path,
    path: output.url,
  }))
  return [...artifacts, ...outputs]
}

export function listBatches(): Promise<ListResponse<BatchSummary>> {
  return requestJson(`${endpointPaths.batches}?limit=100`)
}

export async function listArtifacts(): Promise<ArtifactRecord[]> {
  const runs = await listRuns()
  const settled = await Promise.allSettled(
    runs.items.slice(0, 30).map((run) => fetchRunArtifacts(run.run_id)),
  )
  return settled.flatMap((result) =>
    result.status === 'fulfilled' ? result.value : [],
  )
}

export function cancelRun(runId: string): Promise<RunDetail> {
  return postJson(endpointPaths.runCancel(runId), {})
}

export function retryRun(runId: string, fromStage?: string): Promise<RunDetail> {
  return postJson(endpointPaths.runRetry(runId), {
    ...(fromStage ? { from_stage: fromStage } : {}),
  })
}

export function approveRun(runId: string): Promise<RunDetail> {
  return postJson(endpointPaths.runApprove(runId), {})
}

export function refreshRunComfyUI(runId: string): Promise<ArtifactRecord[]> {
  return postJson(endpointPaths.runRefreshComfyUI(runId), {})
}

export function fetchRunEvents(runId: string, after = 0): Promise<RunEventsResponse> {
  return requestJson(`${endpointPaths.runEvents(runId)}?after=${after}`)
}

export function pauseBatch(batchId: string): Promise<BatchSummary> {
  return postJson(endpointPaths.batchPause(batchId), {})
}

export function resumeBatch(batchId: string): Promise<BatchSummary> {
  return postJson(endpointPaths.batchResume(batchId), {})
}

export function cancelBatch(batchId: string): Promise<BatchSummary> {
  return postJson(endpointPaths.batchCancel(batchId), {})
}

export function retryBatch(batchId: string, fromStage?: string): Promise<BatchSummary> {
  return postJson(endpointPaths.batchRetry(batchId), {
    ...(fromStage ? { from_stage: fromStage } : {}),
  })
}

export function analyzeComfyWorkflow(endpoint: string, workflowPath: string): Promise<Record<string, unknown>> {
  return postJson(endpointPaths.comfyuiAnalyzeWorkflow, {
    comfyui: {
      enabled: true,
      endpoint,
      workflow_api_path: workflowPath,
    },
  })
}

export function connectComfyUI(endpoint: string, workflowPath?: string): Promise<ComfyUIConnectionReport> {
  return postJson(endpointPaths.comfyuiConnect, {
    endpoint,
    ...(workflowPath ? { workflow_api_path: workflowPath } : {}),
  })
}

export function listPromptProfiles(): Promise<{ items: PromptProfile[] }> {
  return requestJson(endpointPaths.promptProfiles)
}

export function clonePromptProfile(profileId: string, name: string): Promise<PromptProfile> {
  return postJson(endpointPaths.promptProfileClone(profileId), { name })
}

export function updatePromptProfile(profile: PromptProfile): Promise<PromptProfile> {
  return requestJson(endpointPaths.promptProfile(profile.id), {
    method: 'PUT',
    body: JSON.stringify(profile),
  })
}

export function resetPromptProfile(profileId: string): Promise<PromptProfile> {
  return postJson(endpointPaths.promptProfileReset(profileId), {})
}
