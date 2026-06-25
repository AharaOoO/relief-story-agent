# Local ComfyUI Smoke Runner Design

## Objective

Build a focused real-run smoke layer for the local LTX 2.3 short-video agent.
The goal is to prove that the already approved creative output can be delivered
into the user's ComfyUI workflow and accepted by `/prompt`.

This stage is not a UI, not a full batch scheduler rewrite, and not another
creative model call. It is a local deployment confidence tool: before the agent
is shared with fans, a user should be able to run one command or one API request
and learn whether their machine, workflow, four-grid image path, and ComfyUI
endpoint are ready.

## Confirmed Scope

The global creative pipeline remains:

```text
chief_screenwriter
-> deepseek_polish
-> quality_gate
-> gpt_prompt_writer
-> gpt_prompt_audit
-> gpt_prompt_reviser (at most once)
-> final_prompts
-> four_grid_asset
-> artifacts
-> comfyui
```

This specification strengthens the final verification path:

```text
final_storyboard/final_prompts
-> four-grid image validation
-> ComfyUI upload
-> workflow patch
-> ComfyUI /prompt enqueue
-> smoke result artifacts
```

The smoke runner never changes script text, storyboard content, prompt wording,
audit results, or model configuration. It consumes finalized inputs and checks
that the execution handoff works.

## Design Influences

The implementation should stay lightweight, but borrow the useful engineering
ideas from mature workflow systems:

- Temporal Workflows treat external calls as activities whose results are
  recorded and replayed instead of repeated. The smoke runner should similarly
  persist upload and enqueue receipts so retry behavior is predictable.
- Prefect task-runner guidance emphasizes task granularity, explicit resource
  constraints, and avoiding unbounded nested work. The smoke runner should use
  the existing image and ComfyUI concurrency boundaries instead of creating a
  second hidden scheduler.
- LangGraph persistence separates thread-scoped checkpoints from longer-lived
  stores. The smoke runner should write run-scoped artifacts and not invent a
  global memory layer.

These influences are design constraints, not dependencies. The first
implementation should use the existing Python modules and persistence model.

Reference pages:

- Temporal Workflows: https://docs.temporal.io/workflows
- Prefect task runners: https://docs.prefect.io/v3/concepts/task-runners
- LangGraph persistence: https://docs.langchain.com/oss/python/langgraph/persistence

## Public Interfaces

### API

Add:

```text
POST /api/smoke/comfyui
```

The request accepts:

```text
workflow_path
comfyui_base_url
final_storyboard or final_prompts artifact reference
manual_grid_image_path, optional
output_root, optional
seed, optional
filename_prefix, optional
dry_run, default false
timeout_seconds, optional
```

The response returns:

```text
status: passed | failed
ready: boolean
preflight: structured check results
workflow_summary
grid_asset
upload_result
patched_replacements
prompt_id, when enqueued
artifact_dir
logs
failure_code, optional
```

`dry_run=true` runs validation and workflow patch preview but does not upload or
enqueue. `dry_run=false` performs the real ComfyUI upload and `/prompt` call.

### CLI

Add:

```text
python -m relief_story_agent.smoke_comfyui --request path\to\smoke_request.json
```

Optional flags:

```text
--dry-run
--comfyui-base-url http://127.0.0.1:8188
--output-root path\to\artifacts
--timeout-seconds 30
```

The CLI prints a concise human-readable summary and writes the same JSON
artifacts as the API. It must exit with code `0` only when the smoke status is
`passed`.

## Input Model

Create `ComfyUISmokeRequest` and `ComfyUISmokeResult` models rather than
overloading `RunRequest`.

The smoke request can reference finalized pipeline output in two ways:

1. By run id and artifact root, when the normal orchestrator has already
   produced final prompt artifacts.
2. By direct `final_storyboard` or `final_prompts` JSON object, useful for
   isolated local testing.

If both are provided, direct JSON takes precedence and a warning is logged. The
runner must never use pre-audit storyboard data when a final storyboard is
available.

## Preflight Checks

Preflight returns a list of checks with:

```text
id
status: pass | warn | fail
severity: info | warning | error
message
evidence
suggested_action
```

Required checks:

- `workflow_file_readable`: workflow exists and is valid JSON.
- `workflow_format_supported`: LiteGraph and existing API workflow formats are
  handled through current adapters.
- `ltx_injection_points`: prompt JSON, seed, filename prefix, and four-grid
  image nodes are detected.
- `grid_shape`: expected grid is 2 columns by 2 rows for the supplied LTX 2.3
  workflow.
- `final_prompts_available`: final storyboard or final prompt payload exists.
- `final_prompts_post_audit`: final data is explicitly marked as audit-passed
  or revision-final when available.
- `grid_image_valid`: manual or existing four-grid asset can be decoded and
  passes structural checks.
- `output_root_writable`: artifact directory can be created and written.
- `comfyui_reachable`: ComfyUI responds before real upload/enqueue. This check
  is skipped in dry-run mode unless the user requests network checking.
- `patch_preview_safe`: only declared workflow fields would change.

Secrets must never appear in check evidence. Local paths may appear because this
is a local developer tool, but artifact JSON should preserve them as strings
without reading unrelated directories.

## Workflow Patching Contract

The smoke runner reuses the existing LTX workflow adapter. For the supplied
workflow it must patch exactly:

```text
node 202: LTX JSON prompt payload
node 37: random seed / noise_seed
node 79: output filename_prefix
node 196: uploaded ComfyUI grid image filename
```

No other node may be changed. If a future workflow has different node ids, graph
detection may resolve different ids, but the same semantic fields apply.

The smoke result records both the resolved semantic injection points and the
exact node ids patched.

## Four-Grid Image Behavior

The smoke runner can use:

- an existing `GridImageAsset` from a completed run;
- a manual image path supplied in the smoke request;
- an already generated image artifact referenced by path.

The first version should not call an image generation model from the smoke
runner. If no usable image is available, the runner fails with
`grid_image_missing` and tells the user which config field to provide.

Before upload, the image is copied into the smoke artifact directory and
validated using the same structural validator as the production run:

- decodable image;
- supported extension and MIME type;
- positive dimensions;
- square-ish 2x2 contact sheet shape;
- non-empty quadrant variation;
- byte size within configured limit.

## ComfyUI Handoff

For real smoke execution:

1. Call ComfyUI `/upload/image` with multipart data.
2. Normalize the returned filename for `LoadImage`.
3. Patch the workflow using the normalized filename.
4. Call ComfyUI `/prompt`.
5. Persist the returned `prompt_id`.

The runner stops after successful enqueue. It does not wait for render
completion, poll output files, or inspect generated video in this stage. Those
belong to a later "render monitor and collector" specification.

## Artifacts

Write a dedicated timestamped smoke artifact directory under `output_root`:

```text
smoke_request.json
smoke_preflight.json
smoke_grid_image.<ext>
smoke_upload.json
smoke_workflow_patched.json
smoke_result.json
smoke_logs.jsonl
```

If `dry_run=true`, omit `smoke_upload.json`. The result artifact still records
that upload and enqueue were skipped by policy.

Artifacts must be enough to reproduce what was sent to ComfyUI without exposing
model API secrets.

## Failure Semantics

Failures should be precise and user-actionable:

```text
workflow_unreadable
workflow_invalid_json
workflow_unsupported
workflow_injection_ambiguous
final_prompts_missing
final_prompts_not_audit_final
grid_image_missing
grid_image_invalid
output_root_unwritable
comfyui_unreachable
comfyui_upload_failed
workflow_patch_failed
comfyui_prompt_failed
```

The smoke runner should classify failures before returning:

- local configuration failures are non-retryable until the user changes input;
- ComfyUI connection failures are retryable;
- upload timeout after request send is uncertain external state, so the
  deterministic upload filename should be reused on retry;
- `/prompt` failure is not retried automatically in the first version.

## Resource and Concurrency Rules

The smoke runner must use existing `ExecutionResourceLimits` for ComfyUI
submission. It should not bypass the scheduler's GPU protection. Since the
first smoke version does not generate images, it does not consume image-provider
concurrency.

Only one real smoke enqueue should run per process by default. Multiple dry-run
preflights may run concurrently because they do not touch the GPU queue.

## Security and Portability

- The runner does not execute workflow scripts or custom Python nodes; it treats
  workflow JSON as data.
- API keys and model credentials are not required for first-version smoke.
- Paths are normalized and copied into artifact directories before upload.
- Uploaded filenames are deterministic and sanitized.
- ComfyUI base URL must be explicit or come from local config; no remote default
  is assumed.
- The feature should work on Windows paths because the target user environment
  is Windows-first.

## Testing Strategy

### Unit Tests

- request model validation;
- direct JSON final prompts take precedence over artifact reference;
- missing final prompts fail before ComfyUI network calls;
- missing grid image fails before workflow patch;
- dry-run does not call upload or `/prompt`;
- patch preview reports only declared replacements;
- smoke artifacts redact secrets and include enough replay data.

### Integration Tests With Mock ComfyUI

- `/upload/image` receives multipart file and returns a normalized image name;
- `/prompt` receives patched workflow with the normalized grid image filename;
- offline ComfyUI returns `comfyui_unreachable`;
- upload failure returns `comfyui_upload_failed`;
- prompt failure returns `comfyui_prompt_failed`;
- successful smoke returns `passed`, `ready=true`, and a `prompt_id`.

### Real-Workflow Regression Test

Use the sanitized LTX 2.3 fixture derived from the user's workflow structure.
The test must prove:

- LiteGraph workflow analysis still resolves nodes `202`, `37`, `79`, and
  `196`;
- grid shape is `2x2`;
- dry-run writes preflight and patched workflow artifacts;
- real-run with mock ComfyUI uploads the copied grid image and enqueues the
  patched workflow.

## Acceptance Criteria

The stage is complete when:

1. `POST /api/smoke/comfyui` can run dry-run and real smoke paths.
2. `python -m relief_story_agent.smoke_comfyui --request ...` provides the same
   capability from the terminal.
3. The runner refuses to use non-final prompt data when final data is expected.
4. The supplied LTX 2.3 workflow topology is detected without hardcoded
   placeholder maps.
5. Real smoke upload injects the grid image filename into the detected
   `LoadImage` node.
6. `/prompt` success records a ComfyUI `prompt_id`.
7. All smoke artifacts are written and sufficient for debugging.
8. Dry-run has no ComfyUI side effects.
9. Unit, mock integration, real-workflow regression, and full project tests
   pass.

## Out of Scope

- UI or browser control panel;
- automatic image generation inside smoke;
- waiting for video render completion;
- downloading or organizing final ComfyUI video outputs;
- arbitrary workflow graph repair;
- changing the approved creative stage order;
- replacing the current scheduler with Temporal, Prefect, LangGraph, Ray, or
  another external workflow runtime in this slice.

## Next Step After Approval

After this spec is reviewed, create an implementation plan that likely adds:

- `relief_story_agent/smoke_comfyui.py` for CLI and orchestration;
- API route wiring in `relief_story_agent/api.py`;
- smoke request/result models in `relief_story_agent/models.py` or a focused
  smoke model module;
- artifact helpers for smoke output;
- tests for dry-run, mock ComfyUI real-run, and the sanitized LTX fixture.
