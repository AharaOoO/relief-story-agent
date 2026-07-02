import { endpointPaths } from '../../shared/api/endpointPaths'
import { postJson, requestJson } from '../../shared/api/httpClient'
import type {
  BatchRequestPayload,
  ModelStageId,
  RunRequestPayload,
  StageModelDraft,
} from '../run-composer/runRequest.builder'
import type { TimelineEntry } from '../autopilot/stages'

export type ProviderCatalog = {
  runninghub: Record<
    'cn' | 'ai',
    {
      base_url: string
      api_key_env: string
      models: string[]
      recommended_by_stage: Partial<Record<ModelStageId, string[]>>
      source_url: string
      snapshot_date: string
    }
  >
}

export type PreflightResult = {
  ready?: boolean
  passed?: boolean
  blockers?: PreflightIssue[]
  warnings?: PreflightIssue[]
  suggested_actions?: Array<{ code: string; label: string; description: string }>
  checks?: Array<{ name: string; status: string; message: string }>
}

export type RunConfigurationDiagnosis = {
  ready: boolean
  passed?: boolean
  summary?: {
    total?: number
    passed?: number
    failed?: number
    warning?: number
    warnings?: number
  }
  checks?: Array<{
    name: string
    status: string
    message: string
    details?: Record<string, unknown>
  }>
  suggested_actions?: Array<{ code: string; label: string; description?: string }>
  provenance?: Record<string, unknown>
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
  failed_stage?: string
  outputs?: Record<string, unknown>
  parent_batch_id?: string
}

export type GridImageRetryOverride = {
  runninghub_site: 'cn' | 'ai'
  aspect_ratio: '16:9' | '9:16'
  resolution: '1k' | '2k'
}

export type RunRetryPayload = {
  from_stage?: string
  model_config_overrides?: Partial<Record<ModelStageId, StageModelDraft>>
  prompt_overrides?: Partial<Record<ModelStageId, string>>
  grid_image_override?: GridImageRetryOverride
  comfyui_override?: {
    endpoint?: string
    workflow_api_path?: string | null
    output_timeout_seconds?: number
  }
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
  exists?: boolean
  created_at?: string
  metadata?: Record<string, unknown>
  segment_id?: string
  order?: number
  prompt_id?: string
  media_type?: string
}

export type WorkflowModelBinding = {
  node_id: string
  class_type: string
  title: string
  input_name: string
  selected: string
  available: boolean
  choices: string[]
}

export type SegmentRenderState = {
  segment_id: string
  shot_id: string
  order: number
  authored_time_range: string
  render_time_range: string
  duration_seconds: number
  fps: number
  frame_count: number
  local_frame_indices: number[]
  positive_prompt: string
  negative_prompt: string
  seed: number
  strength: number
  grid_panel_prompts: string[]
  grid_image_prompt: string
  grid_image_asset?: { local_path?: string; comfyui_filename?: string; provider?: string; model?: string; task_id?: string }
  workflow_name: string
  workflow_path: string
  workflow_sha256: string
  workflow_api_artifact: string
  workflow_models: WorkflowModelBinding[]
  submission?: { prompt_id: string; client_id: string; status: string; error?: string }
  outputs: Array<{ filename: string; media_type: string; local_path?: string; url?: string; prompt_id: string }>
  status: string
  error: string
}

export type VideoAssemblyState = {
  status: string
  clip_paths: string[]
  output_path: string
  error: string
}

export type RenderPlan = {
  run_id: string
  status: string
  current_stage: string
  duration_mode: 'auto' | 'explicit'
  target_duration_seconds: number
  planned_duration_seconds: number
  segments: SegmentRenderState[]
  video_assembly: VideoAssemblyState
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

export function diagnoseRunConfiguration(
  payload: RunRequestPayload,
): Promise<RunConfigurationDiagnosis> {
  return postJson(
    `${endpointPaths.configDiagnose}?check_comfyui_connection=true`,
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

export function fetchRenderPlan(runId: string): Promise<RenderPlan> {
  return requestJson(endpointPaths.runRenderPlan(runId))
}

export function retrySegmentImage(runId: string, segmentId: string, payload: { runninghub_site?: 'cn' | 'ai'; aspect_ratio?: '16:9' | '9:16'; resolution?: '1k' | '2k'; force?: boolean } = {}): Promise<RunDetail> {
  return postJson(endpointPaths.runSegmentRetryImage(runId, segmentId), payload)
}

export function retrySegmentVideo(runId: string, segmentId: string, force = false): Promise<RunDetail> {
  return postJson(endpointPaths.runSegmentRetryVideo(runId, segmentId), { force })
}

export function cancelSegment(runId: string, segmentId: string): Promise<RunDetail> {
  return postJson(endpointPaths.runSegmentCancel(runId, segmentId), {})
}

export function assembleRunVideo(runId: string): Promise<RunDetail> {
  return postJson(endpointPaths.runAssemble(runId), {})
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
  const artifacts = (response.items ?? response.artifacts ?? []).filter(
    (artifact) => artifact.exists !== false,
  )
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

export function retryRun(runId: string, payload: RunRetryPayload = {}): Promise<RunDetail> {
  return postJson(endpointPaths.runRetry(runId), payload)
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
