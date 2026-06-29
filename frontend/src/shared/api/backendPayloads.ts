type UiApprovalMode = 'manual' | 'auto_after_audit_pass' | 'auto'

type UiRunRequest = {
  idea?: string
  input_spec?: any
  creation_spec?: any
  prompt_profile?: any
  render_backend?: any
  approval_mode?: UiApprovalMode
  duration_seconds?: number
  dry_run?: boolean
  generation_mode?: string
}

export type BackendRunRequest = {
  idea?: string
  input_spec?: any
  creation_spec?: any
  prompt_profile?: any
  render_backend?: any
  approval_mode: 'manual' | 'auto'
  duration_seconds?: number
}

export function toBackendRunRequest(request: UiRunRequest): BackendRunRequest {
  return {
    idea: request.idea ? request.idea.trim() : undefined,
    input_spec: request.input_spec,
    creation_spec: request.creation_spec,
    prompt_profile: request.prompt_profile,
    render_backend: request.render_backend,
    approval_mode:
      request.approval_mode === 'auto_after_audit_pass' ? 'auto' : 'manual',
    duration_seconds: request.duration_seconds,
  }
}

export function buildBatchRunRequest({
  ideasText,
  approvalMode,
  durationSeconds,
}: {
  ideasText: string
  approvalMode: UiApprovalMode
  durationSeconds: number
}) {
  const items = ideasText
    .split(/\r?\n/)
    .map((idea) => idea.trim())
    .filter(Boolean)
    .map((idea) =>
      toBackendRunRequest({
        idea,
        approval_mode: approvalMode,
        duration_seconds: durationSeconds,
      }),
    )

  return { items }
}

export function buildSetupBundleRequest({
  outputDir,
  workflowPath,
  comfyuiEndpoint,
}: {
  outputDir: string
  workflowPath: string
  comfyuiEndpoint: string
}) {
  return {
    output_dir: outputDir.trim(),
    workflow_path: workflowPath.trim(),
    comfyui_endpoint: comfyuiEndpoint.trim(),
    output_root: 'D:/relief_story_runs',
    gemini_api_key_env: 'GEMINI_API_KEY',
    deepseek_api_key_env: 'DEEPSEEK_API_KEY',
    gpt_api_key_env: 'OPENAI_API_KEY',
    acceptance_output_dir: 'D:/relief_story_acceptance',
    export_output_dir: 'D:/relief_story_exports',
  }
}

export function buildWorkflowDiscoveryRequest({
  endpoint,
  searchRootsText,
}: {
  endpoint: string
  searchRootsText: string
}) {
  return {
    endpoint: endpoint.trim(),
    search_roots: searchRootsText
      .split(/\r?\n/)
      .map((root) => root.trim())
      .filter(Boolean),
    max_results: 25,
    include_unsupported: true,
    filename_keywords: ['ltx', 'story', 'workflow', 'four'],
  }
}
