import { endpointPaths } from '../../shared/api/endpointPaths'
import { postJson, requestJson } from '../../shared/api/httpClient'
import type {
  BatchRequestPayload,
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
  item_count?: number
  summary?: Record<string, number>
  items?: Array<{ status: string }>
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
    ArtifactRecord[] | { items?: ArtifactRecord[]; artifacts?: ArtifactRecord[] }
  >(endpointPaths.runArtifacts(runId))
  return Array.isArray(response)
    ? response
    : (response.items ?? response.artifacts ?? [])
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
