# Relief Story Agent

API-first multi-model orchestration service for 60-120 second low-stimulation emotional-buffer shorts.

## Purpose

The first model stage is `chief_screenwriter`: a broad screenplay planner, not a healing-only generator. It chooses the story kernel, style, series direction, emotional arc, and draft script for pressure-heavy audiences.

Pipeline:

1. `chief_screenwriter`
2. `deepseek_polish`
3. `quality_gate`
4. `gpt_prompt_writer`
5. `gpt_prompt_audit`
6. Optional one-pass `gpt_prompt_reviser`
7. `final_prompts`
8. Optional `four_grid_asset` generation/upload for LTX 2.3 four-grid workflows
9. Optional `artifacts`
10. Optional ComfyUI workflow filling and `/prompt` enqueue

`gpt_prompt_writer` and `gpt_prompt_audit` can use user-provided UTF-8 Markdown templates, so prompt rules can be iterated without code edits. If the audit finds prompt issues, the system asks `gpt_prompt_reviser` to fix them once, then uses the revised prompts as the final ComfyUI input.

The core pipeline order is declared in `relief_story_agent/pipeline.py` as `StageSpec` records. Each stage has a category, retry policy, side-effect boundary, and expected outputs. Runtime execution, retry tails, recovery ordering, and failure-source classification use this shared registry so the fixed process stays consistent as the agent grows.

## Run

Fastest local Windows startup from the source checkout:

```powershell
.\start_relief_story_agent.bat
```

The launcher sets `PYTHONPATH` to the project root, creates `relief_story_state`, and starts the API on `http://127.0.0.1:8891`. This avoids the common `ModuleNotFoundError: No module named 'relief_story_agent'` when running from another directory.

For an installed developer setup, install once in editable mode so the module and console script can be launched from any directory:

```powershell
python -m pip install -e "D:\codex工作区"
```

Then start the API:

```powershell
python -m relief_story_agent.server --host 127.0.0.1 --port 8891
```

For local production use, prefer a persistent state directory so runs and batches survive API restarts:

```powershell
python -m relief_story_agent.server --host 127.0.0.1 --port 8891 --state-dir "D:\relief_story_state"
```

The server runs jobs through a local persistent background scheduler. `POST /api/runs` and `POST /api/batches` return `202 Accepted` after saving queued state; workers continue the pipeline in the background.

Health check:

```http
GET /api/health
GET /api/metrics
```

The response reports service status, scheduler status, state backend, model profile bindings, and missing model API-key environment variables. This endpoint is intended for local launchers and future desktop shells.

`GET /api/metrics` returns dashboard-level counters: run status distribution, failed-stage distribution, success rate, average duration, model token/cost totals, batch status distribution, and publish-ready video counts.

Preflight validation for a run request:

```http
POST /api/config/validate
POST /api/config/validate-batch
POST /api/config/diagnose
POST /api/config/diagnose-batch
```

This checks model API-key environment variables, prompt template paths/placeholders, the ComfyUI workflow file, placeholder-map targets, and `output_root` write access before a real run or batch is queued. It does not enqueue anything.

Use `validate` when you need a strict pass/fail gate. Use `diagnose` when building a launcher or UI: it returns `ready`, check counts, the raw checks, and `suggested_actions` such as `configure_model_environment`, `fix_prompt_template`, `fix_comfyui_workflow`, `start_or_check_comfyui`, and `fix_output_root`.

`diagnose` also returns `provenance`, a sha256 trace for configured prompt templates, the ComfyUI workflow, and the placeholder map. This makes it possible to confirm which local template/workflow versions were checked before a run starts.

To also ping the running ComfyUI server, add:

```http
POST /api/config/validate?check_comfyui_connection=true
POST /api/config/validate-batch?check_comfyui_connection=true
POST /api/config/diagnose?check_comfyui_connection=true
POST /api/config/diagnose-batch?check_comfyui_connection=true
```

To make validation a hard gate during creation, add `preflight=true` to `POST /api/runs` or `POST /api/batches`:

```http
POST /api/runs?preflight=true
POST /api/batches?preflight=true
```

If validation fails, the API returns `400` with the full validation report and does not create run or batch state. Add `check_comfyui_connection=true` as well when the launcher should ping ComfyUI before enqueueing.

Useful scheduler options:

```powershell
python -m relief_story_agent.server `
  --host 127.0.0.1 `
  --port 8891 `
  --state-dir "D:\relief_story_state" `
  --max-workers 2 `
  --lease-seconds 300 `
  --recovery-poll-seconds 5 `
  --image-generation-concurrency 2 `
  --comfyui-submission-concurrency 1
```

`--max-workers` limits concurrent runs. `--lease-seconds` controls how long a running job is considered owned by a worker before another process restart may recover it. `--recovery-poll-seconds` controls how often the scheduler scans persistent state for queued or expired running work.
`--image-generation-concurrency` limits GPT Image/OpenAI-compatible four-grid generation. `--comfyui-submission-concurrency` limits ComfyUI `/prompt` submissions, which is useful when the local GPU should process one LTX job at a time.

For a reusable multi-model deployment, copy `relief_story_agent/model_config.example.json`, set the referenced environment variables, and pass the registry at startup:

```powershell
$env:GEMINI_API_KEY = "your-gemini-key"
$env:DEEPSEEK_API_KEY = "your-deepseek-key"
$env:OPENAI_API_KEY = "your-openai-key"

python -m relief_story_agent.server `
  --host 127.0.0.1 `
  --port 8891 `
  --state-dir "D:\relief_story_state" `
  --model-config "D:\relief_story_agent_config\models.json"
```

Or use the console script installed by the package:

```powershell
relief-story-agent serve --host 127.0.0.1 --port 8891
```

The package also keeps `relief-story-agent-server` as a direct server entrypoint for scripts that do not need the unified CLI.

Generate a local starter bundle for a non-developer machine:

```powershell
relief-story-agent setup `
  --output-dir "D:/relief_story_config" `
  --workflow-path "D:/ComfyUI/workflows/ltx23_four_grid.json" `
  --comfyui-endpoint "http://127.0.0.1:8188" `
  --output-root "D:/relief_story_runs" `
  --pretty
```

The setup command writes `model_config.local.json`, `comfyui_connect.json`, `run_request.full-ltx.json`, `batch_request.full-ltx.json`, and editable prompt templates under `templates/`. It never writes API keys; generated model config files reference `GEMINI_API_KEY`, `DEEPSEEK_API_KEY`, and `OPENAI_API_KEY` environment variables.

Copyable deployment examples live in `relief_story_agent/examples/`:

- `start_server.example.ps1`
- `run_request.example.json`
- `batch_request.example.json`
- `comfyui_connect.example.json`

For both single runs and batches, set `idempotency_key` when calling from a launcher or script. Re-sending the same key with the same payload returns the existing job; re-sending the same key with different payload returns `409 Conflict`.

## Local ComfyUI Smoke Test

Use the smoke runner before batch generation to verify that a finalized LTX
storyboard and four-grid image can be accepted by your local ComfyUI workflow.

Dry-run:

```powershell
python -m relief_story_agent.smoke_comfyui --request .\smoke_request.json --dry-run
```

Real enqueue:

```powershell
python -m relief_story_agent.smoke_comfyui --request .\smoke_request.json
```

The same runner is available through:

```http
POST /api/smoke/comfyui
```

The request JSON accepts `workflow_path`, `comfyui_base_url`,
`final_storyboard` or `final_prompts`, `manual_grid_image_path`, `output_root`,
and optional `run_id`, `seed`, and `filename_prefix`.

Dry-run writes preflight and patched-workflow artifacts without uploading or
enqueueing. Real mode uploads the four-grid image to `/upload/image`, injects
the returned filename into the detected `LoadImage` node, submits `/prompt`,
and records the returned `prompt_id`.

This tool does not call text models, does not generate the four-grid image,
does not wait for render completion, and does not download final videos.

## Acceptance Evidence

Use the acceptance writer after real local checks to produce a stable report
that another reviewer or agent can inspect:

```powershell
relief-story-agent acceptance `
  --output-dir "D:/relief_story_acceptance" `
  --mode "local_e2e" `
  --status "manual_pending" `
  --check "full_tests=pass:238 passed" `
  --check "comfyui_dry_smoke=pass:smoke_result.json without prompt id" `
  --check "comfyui_real_smoke=manual_pending:" `
  --include-default-matrix `
  --notes "Add exact run ids, artifact dirs, video paths, and batch ids."
```

To import a completed smoke runner result directly:

```powershell
relief-story-agent acceptance `
  --output-dir "D:/relief_story_acceptance" `
  --mode "smoke" `
  --status "completed" `
  --smoke-result "D:/relief_story_smoke/smoke_relief_story/smoke_result.json"
```

The command writes `acceptance_report.json` and `ACCEPTANCE_REPORT.md`.
`summary.ready_for_release` is true only when the overall status and every
recorded check are passing. The static checklist lives in
`docs/ACCEPTANCE_REPORT_TEMPLATE.md`; it should not be treated as complete until
real ComfyUI smoke, single-run, batch, restart-recovery, export, and clean-setup
evidence has been recorded.

## ComfyUI / LTX 2.3 Workflows

For launcher, desktop-shell, or future UI flows where the user fills one local ComfyUI address box first, call:

```http
POST /api/comfyui/connect
```

Example payload:

```json
{
  "endpoint": "http://127.0.0.1:8188",
  "workflow_api_path": "D:/ComfyUI/workflows/ltx23_four_grid.json",
  "timeout_seconds": 5
}
```

The endpoint pings ComfyUI `/queue`, reports running and pending queue counts, and, when `workflow_api_path` is supplied, analyzes the local workflow with the same LTX/placeholder logic used by real runs. It returns `ready`, `connected`, `checks`, `suggested_actions`, `suggested_config`, and workflow details such as `adapter_mode`, `grid_shape`, and `ltx_injection_points`. It does not upload images, call models, enqueue `/prompt`, wait for rendering, or download outputs.

The same check is available without starting the API:

```powershell
relief-story-agent connect-comfyui --request .\relief_story_agent\examples\comfyui_connect.example.json --pretty
```

After `setup`, use the generated local file instead:

```powershell
relief-story-agent connect-comfyui --request "D:/relief_story_config/comfyui_connect.json" --pretty
```

`workflow_api_path` accepts two workflow shapes:

- ComfyUI API prompt JSON: uses `placeholder_map_path` and/or inline `placeholder_map` to fill per-shot inputs, then queues one prompt per storyboard shot. When both are provided, the file is loaded first and inline entries override entries with the same key.
- ComfyUI frontend LiteGraph JSON: detects the LTX prompt JSON node, converts the graph to API prompt format, expands KJNodes `SetNode/GetNode` pairs into direct links, fills the LTX payload, seed, and output filename prefix, then queues one prompt for the whole short.

For the supplied LTX 2.3 four-grid workflow, the detected replacement points are:

- four-grid LoadImage: node `196`
- LTX JSON: node `202`
- seed: node `37`
- video filename prefix: node `79`

The agent creates or accepts one 2x2 reference sheet before ComfyUI enqueue. Automatic mode uses an OpenAI-compatible image endpoint, defaulting to `gpt-image-2`:

```json
{
  "comfyui": {
    "enabled": true,
    "endpoint": "http://127.0.0.1:8188",
    "workflow_api_path": "C:/path/to/LTX-2.3-four-grid.json",
    "grid_image": {
      "mode": "auto",
      "provider": "openai_compatible",
      "base_url": "https://api.openai.com/v1",
      "api_key_env": "OPENAI_API_KEY",
      "model": "gpt-image-2",
      "size": "1024x1024",
      "quality": "medium",
      "output_format": "png"
    }
  }
}
```

Manual override skips image generation and copies a validated local image into the run artifact directory:

```json
{
  "grid_image": {
    "mode": "manual_override",
    "manual_image_path": "D:/images/my-four-grid.png"
  }
}
```

Grid image artifacts are written next to the prompt outputs:

- `09_four_grid_prompt.json`
- `10_four_grid_image.<ext>`
- `11_comfyui_upload.json`

Retries are checkpoint-aware. Once the four-grid image has been generated or copied, upload or ComfyUI failures reuse the same local asset. Once ComfyUI has accepted the upload receipt, retries skip the upload endpoint and only resume workflow patching or `/prompt` submission.

Example request fragment:

```json
{
  "output_root": "D:/relief_runs",
  "template_paths": {
    "prompt_writer_template_path": "D:/templates/prompt_writer.md",
    "prompt_audit_template_path": "D:/templates/prompt_audit.md"
  },
  "comfyui": {
    "enabled": true,
    "endpoint": "http://127.0.0.1:8188",
    "workflow_api_path": "C:/Users/dcf/Downloads/AI代码侠土豆-LTX-2.3 4宫格V3.0 红果短剧特调版 半自动(带运镜版).json",
    "grid_image": {
      "mode": "auto",
      "api_key_env": "OPENAI_API_KEY",
      "model": "gpt-image-2"
    }
  }
}
```

For LiteGraph LTX workflows, `placeholder_map_path` is optional because the LTX JSON, seed, and filename-prefix nodes are auto-detected. For ordinary ComfyUI API prompt JSON, use a mapping file like:

```json
{
  "placeholder_map": {
    "positive": {"node": "1", "input": "text", "source": "comfyui_inputs.positive"},
    "negative": {"node": "2", "input": "text", "source": "negative_prompt"},
    "seed": {"node": "3", "input": "seed", "source": "comfyui_inputs.seed"}
  }
}
```

`source` paths are read from the final shot object. If a source path, target node, or target input is missing, preflight or submission fails with the offending mapping key in the error message.

Before a real ComfyUI enqueue, preview the patched workflow plan:

```http
POST /api/comfyui/preview
```

The preview endpoint accepts `comfyui`, `storyboard`, `run_id`, `duration_seconds`, and optional `include_workflow`. It does not call ComfyUI. It returns deterministic `prompt_id`, `client_id`, content fingerprint, workflow format, node count, and the key replacements that will be applied. Set `include_workflow: true` only when debugging, because real workflows can be large.

Example payload:

```json
{
  "run_id": "preview-local-ltx",
  "duration_seconds": 90,
  "include_workflow": false,
  "comfyui": {
    "enabled": true,
    "endpoint": "http://127.0.0.1:8188",
    "workflow_api_path": "D:/ComfyUI/workflows/ltx23_four_grid.json",
    "placeholder_map_path": "D:/relief_story_templates/placeholder_map.json"
  },
  "storyboard": [
    {
      "shot_id": 1,
      "time_range": "0-10s",
      "description": "quiet convenience store night",
      "image_prompt": "quiet rainy convenience store night, tired office worker, soft neon reflection",
      "negative_prompt": "shouting, horror, violence, chaos, text, watermark",
      "comfyui_inputs": {
        "positive": "quiet rainy convenience store night, tired office worker, soft neon reflection",
        "negative": "shouting, horror, violence, chaos, text, watermark",
        "seed": 101,
        "strength": 0.72,
        "filename_prefix": "preview-local-ltx"
      }
    }
  ]
}
```

Template placeholders:

- `{{script_json}}`
- `{{storyboard_json}}`
- `{{audit_json}}`
- `{{duration_seconds}}`
- `{{preferred_style}}`
- `{{workflow_context}}`

Required placeholders:

- writer template: `{{script_json}}`
- audit template: `{{script_json}}`, `{{storyboard_json}}`

The default writer template asks GPT image2 four-grid prompts to stay concise, around 60-120 Chinese characters per `image_prompt`. The backend also caps overly long `image_prompt` values before they become final prompts.

## Batch Runs

Batch runs are the first automation layer for producing many shorts without UI work. Each item becomes an independent background run, so one failed item does not erase the state of the other items.

Use `defaults` to avoid repeating shared configuration on every item. Any field explicitly set on an item overrides the shared default:

```json
{
  "idempotency_key": "relief-batch-2026-06-24-demo",
  "failure_policy": {
    "auto_retry_failed_items": 1,
    "pause_on_failure_count": 3,
    "pause_on_failure_rate": 0.4
  },
  "defaults": {
    "approval_mode": "auto",
    "queue_priority": 0,
    "output_root": "D:/relief_story_runs",
    "comfyui": {
      "enabled": true,
      "endpoint": "http://127.0.0.1:8188",
      "workflow_api_path": "D:/ComfyUI/workflows/ltx23_four_grid.json",
      "placeholder_map_path": "D:/relief_story_templates/placeholder_map.json",
      "wait_for_completion": true,
      "download_outputs": true
    }
  },
  "items": [
    {"idea": "Convenience store night", "queue_priority": 5},
    {"idea": "Pressure creature", "preferred_style": "soft fantasy"}
  ]
}
```

`queue_priority` controls background scheduling order. Higher numbers run earlier; equal priorities keep their original enqueue order. A practical pattern is to give smoke-test items a higher priority, confirm templates and ComfyUI settings, then let the larger batch continue at normal priority.

Before enqueueing a real batch, preview the resolved plan:

```http
POST /api/batches/plan
```

The plan endpoint accepts the same payload as `POST /api/batches`, but it does not create runs, write batch state, call models, or enqueue ComfyUI work. It returns:

- `items`: resolved child requests after applying `defaults`;
- `execution_order`: the priority-sorted order workers will use;
- `failure_policy`: the active batch guardrails;
- `validation`: the same template, model-config, and workflow checks used by `POST /api/config/validate-batch`;
- `will_enqueue: false`, so launchers can safely use it for confirmation screens.

`idempotency_key` prevents accidental duplicate batch creation. Re-sending the same key with the same payload returns the existing batch. Re-sending the same key with a different payload is rejected with `409 Conflict`.

`failure_policy` is the batch-level safety guard for long local production queues:

- `auto_retry_failed_items`: automatically retries a failed child run this many times, from its failed stage.
- `pause_on_failure_count`: pauses remaining queued children after this many failed items.
- `pause_on_failure_rate`: pauses remaining queued children when `failed / total` reaches this ratio.

Set any value to `0` to disable that rule. Batch detail and list responses include the effective `failure_policy`, so a launcher or future UI can display the active guardrails.

```json
{
  "items": [
    {"idea": "便利店夜晚", "approval_mode": "auto"},
    {"idea": "压力小怪物", "approval_mode": "auto"}
  ]
}
```

`POST /api/batches` returns a `batch_id`, per-item `run_id` values, and a summary:

```json
{
  "summary": {
    "total": 2,
    "paused": 0,
    "completed": 2,
    "failed": 0,
    "cancelled": 0,
    "awaiting_approval": 0,
    "running": 0
  }
}
```

## Retry / Resume

Failed runs record `failed_stage`. Retry from that stage without rerunning completed stages:

```http
POST /api/runs/{run_id}/retry
```

To restart from an explicit stage:

```json
{"from_stage": "gpt_prompt_writer"}
```

Batch retry only processes failed items. Completed, cancelled, and awaiting-approval items are left unchanged:

```http
POST /api/batches/{batch_id}/retry
```

The batch endpoint accepts the same optional `from_stage` payload and refreshes the batch status and summary after retrying.

For a safer launcher flow, inspect the recovery plan before retrying:

```http
GET /api/batches/{batch_id}/recovery-plan
```

The recovery plan classifies every child run into `publish`, `auto`, `manual`, or `wait`. It includes `action_code`, `retry_from_stage`, `endpoint`, `request_payload`, and `blocking_reason`, so local launchers can safely auto-retry transient failed stages while holding template, prompt-audit, quality-gate, and ComfyUI mapping issues for operator review. This follows the same broad pattern used by durable workflow systems: retry narrow failed activities when safe, and surface permanent/configuration errors instead of blindly rerunning the whole workflow.

New failed runs also persist structured `last_failure` and `failure_records` entries. The default recovery policy is conservative: only `transient`, `throttled`, and `timeout` failures are eligible for automatic retry. `configuration`, `validation`, `contract`, `external`, `cancelled`, and `unknown` failures are held for operator review so unattended batches do not keep spending model quota on problems that need a template, workflow, quality, or code fix. Older run files without structured failure records still use the legacy failed-stage and timeline inference until they fail again under the new classifier.

To execute only safe automatic recovery actions from that plan:

```http
POST /api/batches/{batch_id}/recover
```

Use `dry_run` before a one-click launcher action:

```json
{"dry_run": true}
```

You can restrict execution to specific action codes:

```json
{"action_codes": ["retry_from_stage"]}
```

The recovery executor only runs items marked `safe_to_auto_execute`. Manual blockers are returned in `skipped` with a reason, so a launcher can show exactly which templates, workflow maps, quality gates, or prompt-audit issues still need human attention.

To stop a whole batch, cancel it once instead of cancelling every child run manually:

```http
POST /api/batches/{batch_id}/cancel
```

Completed and failed child runs keep their terminal state. Queued and approval-waiting child runs are cancelled immediately; running child runs receive a cooperative cancellation request and stop at the next safe stage boundary.

To temporarily hold a batch without losing progress, pause and resume it:

```http
POST /api/batches/{batch_id}/pause
POST /api/batches/{batch_id}/resume
```

Pausing a batch converts queued child runs to `paused`. Running children are allowed to finish their current pipeline execution; when they complete, any still-paused children remain held. Resuming converts paused children back to `queued` and the scheduler submits them again. Batch list responses include a `paused` flag for launcher and future UI state.

## Background Scheduler

The local scheduler is designed for durable desktop deployment:

- queued runs are written to disk before execution;
- workers claim runs with a lease and recover expired `running` jobs after restart;
- a recovery scanner keeps polling persistent state, so a run whose lease was still fresh at server startup will be recovered once that lease expires;
- `last_completed_stage` checkpoints prevent rerunning stages that already finished;
- cancellation is cooperative and is observed at stage boundaries;
- manual approval queues the continuation instead of running inside the HTTP request;
- batch summaries refresh as child runs complete.

Scheduler health:

```http
GET /api/scheduler
```

The scheduler response includes queue counts plus `active_items`, `queued_items`, `lease_seconds`, and `recovery_poll_seconds`. `queued_items` is already sorted by the real execution order: higher `queue_priority` first, original enqueue order second. Each item includes `run_id`, idea, status, stage, priority, parent batch id, and `position`.

Run event polling:

```http
GET /api/runs
GET /api/runs?status=completed&limit=20
GET /api/runs?parent_batch_id=batch_xxx
GET /api/runs/{run_id}/events
GET /api/runs/{run_id}/events?after=12
```

Run list entries include `queue_priority`, so launchers can show why one item is waiting behind another.

Batch listing:

```http
GET /api/batches
GET /api/batches?status=completed&limit=20
```

Batch list entries include compact child `items` with each child run's `queue_priority`, status, stage, and error.

Events are persisted with each run and include ordered `sequence` numbers. Current event types include `run_queued`, `run_claimed`, `stage_started`, `stage_completed`, `approval_queued`, `retry_queued`, `cancel_requested`, `comfyui_cancellation_requested`, `run_completed`, `run_failed`, and `run_cancelled`.

Artifact discovery:

```http
GET /api/runs/{run_id}/artifacts
GET /api/batches/{batch_id}/artifacts
POST /api/batches/{batch_id}/export
```

Completed runs with `output_root` write `00_manifest.json` plus:

- `01_script.json`
- `02_storyboard.json`
- `03_ltx_payload.json`
- `04_prompt_audit.json`
- `05_final_prompts.json`
- `06_model_execution.json`
- `07_comfyui_preview.json`

The run artifact index also exposes ComfyUI prompt IDs, precise cancellation results, diagnostics, expected future video output slots, actual downloaded outputs, final prompt summaries, `configuration_provenance`, and the ComfyUI dry-run preview trace. `configuration_provenance` records local template, workflow, and placeholder-map paths with existence, size, mtime, and sha256 so exported results can be traced back to the exact files used. The preview trace includes deterministic prompt IDs, workflow fingerprints, workflow format, node counts, and the fields that will be replaced before `/prompt`.

The batch artifact index summarizes publish-ready items with title, core sentence, scores, actual outputs, and `primary_video_path`. It also includes `audit_summary`, which reports item counts by status, failed-stage distribution, failed items, retryable items, aggregate token usage, estimated model cost, and recommended action counts. Each item includes `failed_stage`, `retryable`, `retry_from_stage`, `model_usage_summary`, and `recommended_action`, so a launcher can show exactly what can be retried.

`recommended_action.code` values include `publish`, `refresh_comfyui_outputs`, `fix_template`, `check_comfyui_mapping`, `manual_review_prompt_audit`, `manual_review_script_quality`, `retry_from_stage`, and `manual_review`.

`GET /api/batches/{batch_id}/recovery-plan` turns those per-item recommendations into an operator-ready plan with counts for publish-ready, auto-executable, manual-review, and waiting items.

The export endpoint copies publish assets into a clean directory and can create a zip package for sharing:

```json
{
  "export_root": "D:/relief_story_exports",
  "include_zip": true
}
```

Each batch export also writes:

- `batch_export_manifest.json`: full technical manifest with every item and copied artifact path.
- `publish_index.json`: structured publish index for launchers, uploaders, or future UI.
- `publish_index.csv`: spreadsheet-friendly publish index with title, core sentence, publish-ready flag, video paths, scores, and recommended action code.
- `publish_videos/`: a flat folder containing only publish-ready videos, named with the item index and title for quick review or uploader pickup.
- `batch_id.zip.sha256`: when `include_zip` is true, a sidecar checksum file for the generated zip package.

Validate an exported package before upload or sharing:

```http
POST /api/batches/{batch_id}/export/validate
```

```json
{"export_dir": "D:/relief_story_exports/batch_abc123", "save_report": true}
```

The validator checks the export manifest, publish indexes, `publish_videos/`, every publish-ready video path referenced by `publish_index.json`, plus each publish video's recorded size and sha256 checksum. With `save_report: true`, it writes `validation_report.json` into the export directory.

Validate the zip itself after transfer:

```http
POST /api/batches/{batch_id}/export/validate-zip
```

```json
{
  "zip_path": "D:/relief_story_exports/batch_abc123.zip",
  "expected_sha256": "...",
  "expected_size_bytes": 123456,
  "save_report": true
}
```

The zip validator checks file existence, internal zip CRC, and optional expected size/sha256. With `save_report: true`, it writes a `.validation.json` report next to the zip.

## ComfyUI Idempotency

Each ComfyUI submission now has a persistent record containing:

- `submission_key`
- workflow content fingerprint
- deterministic UUID v5 `prompt_id`
- unique `client_id`
- `prepared`, `accepted`, `unknown`, or `rejected` status

The record is saved before and after the network request. If the connection times out, the run fails at `comfyui` with an `unknown` submission instead of blindly enqueueing again.

Retrying the run performs recovery in this order:

1. Query `/api/jobs/{prompt_id}`.
2. Search `/queue` by `prompt_id` or `client_id`.
3. Search `/history` by `prompt_id` or `client_id`.
4. Re-submit with the same deterministic ID only when all checks confirm that the task is absent.

Already accepted submissions are skipped. If the final prompt or patched workflow changes, its fingerprint changes and a new prompt ID is generated, so a genuine revision is not mistaken for an old result.

## ComfyUI Precise Cancellation

When a run is cancelled while waiting for ComfyUI outputs, the Agent stops polling promptly and attempts to cancel only the accepted prompt IDs owned by that run:

1. Newer ComfyUI versions use `POST /api/jobs/{prompt_id}/cancel`.
2. If that endpoint explicitly returns `404` or `405`, the Agent falls back to `POST /queue` with `{"delete": [prompt_id]}`. This removes a pending legacy queue item but does not interrupt an unrelated running job.
3. Authentication, transport, and server errors are recorded in `comfyui_cancellations`; they do not prevent the local run from becoming `cancelled`.

The Agent never calls the global `/interrupt` endpoint automatically. Prompt IDs and per-job cancellation results remain in `GET /api/runs/{run_id}` and the run artifact manifest for later diagnosis.

## Model Runtime

All model stages now pass through one observable execution layer. The OpenAI-compatible SDK's internal retries are disabled so every actual attempt is visible in the run state.

Model responses are also checked against stage output contracts before the next stage runs. Missing or wrongly typed required fields fail the current stage with a readable error instead of drifting into a later, harder-to-debug failure:

- `chief_screenwriter`: `core_candidates` list and `draft_script` object;
- `deepseek_polish`: `polished_script` object;
- `gpt_prompt_writer`: `shots` list;
- `gpt_prompt_audit`: `passed` boolean;
- `gpt_prompt_reviser`: `shots` list.

Each `shots[]` item from `gpt_prompt_writer` or `gpt_prompt_reviser` must be an object with non-empty `time_range`, `description`, `image_prompt`, and `negative_prompt` fields, plus a `comfyui_inputs` object. This keeps incomplete GPT image2/LTX prompt payloads from reaching artifact export or ComfyUI submission.

Retryable failures:

- connection and timeout errors
- HTTP `408`, `409`, and `429`
- HTTP `5xx`
- malformed JSON responses

Configuration, authentication, permission, template, and business-validation failures are not automatically retried.

Each stage model config supports:

```json
{
  "model": "your-model",
  "timeout_seconds": 60,
  "max_attempts": 3,
  "initial_backoff_seconds": 1,
  "backoff_multiplier": 2,
  "max_backoff_seconds": 30,
  "retry_jitter_ratio": 0.2,
  "requests_per_minute": 30,
  "input_cost_per_million": 1.0,
  "output_cost_per_million": 4.0
}
```

`Retry-After` is honored for rate-limit responses, while the configured maximum backoff remains the hard upper bound. Requests using the same `base_url + model` share one thread-safe local rate-limit schedule across all scheduler workers. Different model keys remain independent, so Gemini, DeepSeek, and GPT calls do not block one another only because they share a process.

This limiter is process-local. A future deployment with multiple server processes or machines must use a shared limiter or provider-side quota coordinator to enforce one global RPM budget.

`GET /api/runs/{run_id}` includes:

- `model_attempts`: attempt number, status, duration, error type, HTTP status, request ID, retry delay, Token usage, and estimated cost
- `model_usage_summary`: successful requests, total attempts, internal retries, total Tokens, and estimated USD cost

Artifact output also includes `06_model_execution.json` with the same execution audit and aggregate usage.

## Model Profiles And Secrets

The model registry keeps reusable endpoint and model settings outside individual runs:

```json
{
  "profiles": {
    "gemini_writer": {
      "base_url": "https://YOUR_ENDPOINT/v1",
      "api_key_env": "GEMINI_API_KEY",
      "model": "YOUR_GEMINI_MODEL"
    }
  },
  "stages": {
    "chief_screenwriter": "gemini_writer"
  }
}
```

Security rules:

- Registry files must use `api_key_env`; plaintext `api_key` values are rejected.
- A direct API key submitted in a run request is memory-only and excluded from API responses, logs, run state, and persistent JSON.
- Durable or restartable runs should always use environment variable references.
- `GET /api/config/models` reports stage bindings and missing environment variables without returning secret values.

A run may select another registered profile without changing the server configuration:

```json
{
  "idea": "雨停之前",
  "model_profiles": {
    "chief_screenwriter": "gemini_writer",
    "deepseek_polish": "deepseek_editor",
    "gpt_prompt_writer": "gpt_visual",
    "gpt_prompt_audit": "gpt_visual",
    "gpt_prompt_reviser": "gpt_visual"
  }
}
```

`model_configs` remains available for per-run non-secret overrides such as temperature, timeout, retry policy, rate limit, and price metadata. Only explicitly supplied fields override the selected profile.

## API

- `GET /api/health`
- `GET /api/metrics`
- `GET /api/config/models`
- `POST /api/config/validate`
- `POST /api/config/validate-batch`
- `POST /api/config/diagnose`
- `POST /api/config/diagnose-batch`
- `GET /api/scheduler`
- `POST /api/batches/plan`
- `POST /api/comfyui/connect`
- `POST /api/comfyui/preview`
- `POST /api/smoke/comfyui`
- `POST /api/runs`
- `GET /api/runs`
- `GET /api/runs/{run_id}`
- `GET /api/runs/{run_id}/events`
- `GET /api/runs/{run_id}/artifacts`
- `POST /api/runs/{run_id}/refresh-comfyui`
- `POST /api/runs/{run_id}/approve`
- `POST /api/runs/{run_id}/retry`
- `POST /api/runs/{run_id}/cancel`
- `POST /api/batches`
- `GET /api/batches`
- `GET /api/batches/{batch_id}`
- `GET /api/batches/{batch_id}/artifacts`
- `GET /api/batches/{batch_id}/recovery-plan`
- `POST /api/batches/{batch_id}/recover`
- `POST /api/batches/{batch_id}/export`
- `POST /api/batches/{batch_id}/export/validate`
- `POST /api/batches/{batch_id}/export/validate-zip`
- `POST /api/batches/{batch_id}/retry`
- `POST /api/batches/{batch_id}/cancel`
- `POST /api/batches/{batch_id}/pause`
- `POST /api/batches/{batch_id}/resume`
