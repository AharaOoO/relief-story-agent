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

`GET /api/pipeline/schema` returns the machine-readable stage contract used by
runs, retries, recovery, diagnostics, and future UI shells. The same contract is
available from the CLI:

```powershell
relief-story-agent pipeline-schema --pretty
```

Before spending model quota on a changed writer/audit template, validate its
required placeholders and fingerprint:

```powershell
relief-story-agent template-check `
  --writer-template "D:/relief_story_config/templates/prompt_writer.default.md" `
  --audit-template "D:/relief_story_config/templates/prompt_audit.default.md" `
  --pretty
```

Before a full generation run, verify the model registry and secrets. The default
mode does not call any model:

```powershell
relief-story-agent model-check `
  --model-config "D:/relief_story_config/model_config.local.json" `
  --run-request "D:/relief_story_config/run_request.full-ltx.json" `
  --pretty
```

Passing `--run-request` includes that request's automatic four-grid image
provider in the readiness result. After API keys and model names are correct,
add `--real-run` to send a tiny JSON-only probe to each configured text profile
and one minimal image probe to the image provider:

```powershell
relief-story-agent model-check `
  --model-config "D:/relief_story_config/model_config.local.json" `
  --run-request "D:/relief_story_config/run_request.full-ltx.json" `
  --real-run `
  --pretty
```

The server exposes the same contract for launchers and future UI shells:
`POST /api/config/model-check`.

For UI integration, `GET /api/local/bootstrap` returns the local API base URL,
recommended UI origin, allowed CORS origins, default ComfyUI endpoint, and core
endpoint paths. The bootstrap contract includes `local_doctor` and
`comfyui.doctor_endpoint`, so a launcher can ping the user's pasted ComfyUI
address before enqueueing work. The default API port is `8891`; the recommended
local UI dev origin is `http://127.0.0.1:5173`. The CLI can print the same
contract before the server starts:

```powershell
relief-story-agent local-bootstrap --pretty
relief-story-agent local-doctor --server "http://127.0.0.1:8891" --pretty
```

When the API server is running, `GET /api/local/readiness` and
`relief-story-agent local-readiness` combine bootstrap, local doctor, the
user-entered ComfyUI address, the selected workflow path, and optional
acceptance-report blockers into one machine-readable setup status. Use it for a
future UI "check my local setup" button before real runs.

For a local launcher or future UI setup screen, call
`POST /api/local/setup-bundle` with `output_dir`, `workflow_path`,
`comfyui_endpoint`, and `output_root`. It generates the same config files as
`relief-story-agent setup`, normalizes ComfyUI address-box inputs, and writes no
API keys.

When the API server is running, `local-doctor` can also ping the exact ComfyUI
address a local launcher or future UI collects:

```powershell
relief-story-agent local-doctor `
  --server "http://127.0.0.1:8891" `
  --check-comfyui-connection `
  --comfyui-endpoint "127.0.0.1:8188/queue" `
  --comfyui-workflow-path "D:/ComfyUI/workflows/ltx23_four_grid.json" `
  --pretty
```

With `--comfyui-workflow-path`, the doctor also asks ComfyUI whether the
selected workflow's node classes are installed, which is the backend contract a
future UI workflow picker can use before enqueueing a batch.

For a machine-readable local acceptance snapshot that another reviewer can
inspect later, run:

```powershell
relief-story-agent local-acceptance `
  --output-dir "D:/relief_story_acceptance" `
  --repo-root "D:/codex工作区" `
  --model-config "D:/relief_story_config/model_config.local.json" `
  --run-request "D:/relief_story_config/run_request.full-ltx.json" `
  --batch-request "D:/relief_story_config/batch_request.full-ltx.json" `
  --local-demo `
  --model-check-real-run `
  --smoke-request "D:/relief_story_config/smoke_request.json" `
  --smoke-dry-run `
  --comfyui-output-prompt-id "{prompt_id}" `
  --comfyui-output-artifact-dir "D:/relief_story_acceptance/comfyui_outputs" `
  --pretty
```

This writes command stdout/stderr files, `local_acceptance_summary.json`,
`acceptance_report.json`, `acceptance_status.json`, and
`ACCEPTANCE_REPORT.md`. Optional config/request arguments add `model-check`, run
diagnose, batch diagnose, smoke, and standalone ComfyUI output-download
evidence to the same report. When both model config and run request are
provided, local acceptance passes the run request into `model-check` so the
four-grid image provider is covered by the model readiness evidence. Use
`--model-check-real-run` in the final evidence pass so the same report records
the real text-model and image-provider probes. When `--comfyui-output-prompt-id`
is used with download evidence, the reported video `local_path` must exist on
disk and be non-empty before the ComfyUI output check can pass. If an
`acceptance_report.json` already exists in the output directory, passed checks
from that report are preserved unless the new local-acceptance run records the
same check id again; existing `run_id`, `batch_id`, and video paths are carried
forward too.

You can also run the offline skeleton demo by itself:

```powershell
relief-story-agent local-demo `
  --output-dir "D:/relief_story_demo" `
  --batch-size 2 `
  --pretty
```

`local-demo` uses the built-in fake model provider and disables ComfyUI/image
generation. It proves the local orchestration skeleton can create run artifacts
and a completed batch summary, then reload persisted state for a restart
recovery-plan drill without API keys or GPU. It is not a real model/video
acceptance run.

Preflight validation for a run request:

```http
POST /api/config/validate
POST /api/config/validate-batch
POST /api/config/diagnose
POST /api/config/diagnose-batch
```

This checks model API-key environment variables, prompt template paths/placeholders, the ComfyUI workflow file, placeholder-map targets, `output_root` write access, and `execution_policy` budgets before a real run or batch is queued. It does not enqueue anything.

Use `validate` when you need a strict pass/fail gate. Use `diagnose` when building a launcher or UI: it returns `ready`, check counts, the raw checks, and `suggested_actions` such as `configure_model_environment`, `fix_prompt_template`, `fix_comfyui_workflow`, `start_or_check_comfyui`, `fix_output_root`, and `fix_execution_policy`.

`local-doctor` also returns `fix_model_profiles` when model profile values still
look like setup placeholders such as `YOUR_MODEL` or `YOUR_PROVIDER_ENDPOINT`.

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

The same diagnostic checks can run from the unified CLI before the API server is
started. This reads local request/config files only; it does not enqueue work or
call text/image models.

Single run:

```powershell
relief-story-agent diagnose `
  --request "D:/relief_story_config/run_request.full-ltx.json" `
  --model-config "D:/relief_story_config/model_config.local.json" `
  --check-comfyui-connection `
  --pretty
```

Batch:

```powershell
relief-story-agent diagnose `
  --request "D:/relief_story_config/batch_request.full-ltx.json" `
  --model-config "D:/relief_story_config/model_config.local.json" `
  --kind batch `
  --pretty
```

`--kind auto` is the default and treats files with `items[]` as batch requests.
The command exits `0` when `ready=true` and exits `1` when configuration is
blocked, so Windows launchers and install scripts can stop before spending
model quota or submitting to ComfyUI.

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

For a reusable multi-model deployment, copy `relief_story_agent/examples/model_config.local.example.json`, set the referenced environment variables, and pass the copied registry at startup:

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

Local API operator commands:

```powershell
relief-story-agent run `
  --request "D:/relief_story_config/run_request.full-ltx.json" `
  --server "http://127.0.0.1:8891" `
  --preflight `
  --check-comfyui-connection `
  --pretty

relief-story-agent run-status `
  --run-id "{run_id}" `
  --pretty

relief-story-agent runs `
  --status failed `
  --parent-batch-id "{batch_id}" `
  --limit 20 `
  --pretty

relief-story-agent run-events `
  --run-id "{run_id}" `
  --after 0 `
  --pretty

relief-story-agent run-audit `
  --run-id "{run_id}" `
  --pretty

relief-story-agent run-timeline `
  --run-id "{run_id}" `
  --pretty

relief-story-agent run-artifacts `
  --run-id "{run_id}" `
  --pretty

relief-story-agent batch-plan `
  --request "D:/relief_story_config/batch_request.full-ltx.json" `
  --server "http://127.0.0.1:8891" `
  --check-comfyui-connection `
  --pretty

relief-story-agent batch `
  --request "D:/relief_story_config/batch_request.full-ltx.json" `
  --server "http://127.0.0.1:8891" `
  --preflight `
  --check-comfyui-connection `
  --pretty

relief-story-agent batch-status `
  --batch-id "{batch_id}" `
  --pretty

relief-story-agent batches `
  --status completed `
  --limit 20 `
  --pretty

relief-story-agent batch-artifacts `
  --batch-id "{batch_id}" `
  --pretty

relief-story-agent batch-timeline `
  --batch-id "{batch_id}" `
  --pretty

relief-story-agent batch-health `
  --batch-id "{batch_id}" `
  --pretty

relief-story-agent scheduler --pretty

relief-story-agent export-batch `
  --batch-id "{batch_id}" `
  --export-root "D:/relief_story_exports" `
  --include-zip `
  --pretty

relief-story-agent recovery-plan `
  --batch-id "{batch_id}" `
  --pretty

relief-story-agent recover-batch `
  --batch-id "{batch_id}" `
  --dry-run `
  --action-code retry_from_stage `
  --pretty

relief-story-agent validate-export `
  --batch-id "{batch_id}" `
  --export-dir "D:/relief_story_exports/{batch_id}" `
  --save-report `
  --pretty

relief-story-agent validate-export-zip `
  --batch-id "{batch_id}" `
  --zip-path "D:/relief_story_exports/{batch_id}.zip" `
  --save-report `
  --pretty
```

These commands call the local API server and print the JSON response. They use
direct local HTTP without environment proxy settings so `127.0.0.1` launchers do
not accidentally route through a system proxy.

Generate a local starter bundle for a non-developer machine:

```powershell
relief-story-agent setup `
  --output-dir "D:/relief_story_config" `
  --workflow-path "D:/ComfyUI/workflows/ltx23_four_grid.json" `
  --comfyui-endpoint "http://127.0.0.1:8188" `
  --output-root "D:/relief_story_runs" `
  --pretty
```

`--comfyui-endpoint` accepts the same address-box input a local UI would. Values
such as `127.0.0.1:8188`, `http://127.0.0.1:8188/`, and
`http://127.0.0.1:8188/queue` are normalized to `http://127.0.0.1:8188`
inside generated config files.

The setup command writes `model_config.local.json`, `comfyui_connect.json`, `run_request.full-ltx.json`, `batch_request.full-ltx.json`, `smoke_request.json`, and editable prompt templates under `templates/`. It never writes API keys; generated model config files reference `GEMINI_API_KEY`, `DEEPSEEK_API_KEY`, and `OPENAI_API_KEY` environment variables.
Its JSON response keeps the legacy top-level file path keys and also includes `files`, `checks`, `next_commands`, and `next_endpoints` for local launchers and future UI shells. `checks.smoke_grid_image` reports whether the manual smoke image is in place. `next_commands.smoke_dry_run` and `next_commands.smoke_real_run` use the generated smoke request, while `next_commands.local_acceptance` collects a repeatable local evidence bundle and `next_commands.acceptance_status` lists the remaining blocking evidence.
`next_commands.local_readiness` runs the combined setup status query with the
generated acceptance report path, ComfyUI endpoint, and workflow path.

Copyable deployment examples live in `relief_story_agent/examples/`:

- `start_server.example.ps1`
- `run_request.example.json`
- `batch_request.example.json`
- `comfyui_connect.example.json`
- `smoke_request.example.json`
- `model_config.local.example.json`
- `run_request.full-ltx.example.json`
- `batch_request.full-ltx.example.json`
- `examples/templates/prompt_writer.default.md`
- `examples/templates/prompt_audit.default.md`

For a realistic local LTX setup, copy the full examples into a writable config
directory, edit the ComfyUI workflow path and model names, then run:

```powershell
relief-story-agent diagnose `
  --request "D:/relief_story_config/run_request.full-ltx.json" `
  --model-config "D:/relief_story_config/model_config.local.json" `
  --check-comfyui-connection `
  --pretty
```

Operator guides:

- `docs/LOCAL_DEPLOYMENT.md`
- `docs/COMFYUI_LTX23_GUIDE.md`
- `docs/TEMPLATE_GUIDE.md`

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
the returned filename into the detected `LoadImage` node, fetches `/object_info`,
patches runtime-required widget values, submits `/prompt`, and records the
returned `prompt_id`.

For LiteGraph workflows, real mode uses `/object_info` to fill required widget
inputs that the frontend JSON often stores only in `widgets_values`. This covers
dynamic combo inputs such as `resize_type.longer_size`, primitive defaults,
loader defaults, and local model/LoRA COMBO names when the selected workflow
uses a filename alias that differs from the user's integrated package.

This tool does not call text models, does not generate the four-grid image,
does not wait for render completion, and does not download final videos.

Latest local smoke evidence:

```text
python -m relief_story_agent.smoke_comfyui --request "D:/relief_story_inputs/local_ltx_ready_smoke_request.real.json"
status=passed
ready=true
prompt_id=31037f9b-b8c8-5919-b717-fbe3c7e634eb
artifact_dir=D:\relief_story_smoke\comfyui_smoke_20260625T115742676759Z
```

## Acceptance Evidence

Use the acceptance writer after real local checks to produce a stable report
that another reviewer or agent can inspect:

```powershell
relief-story-agent acceptance `
  --output-dir "D:/relief_story_acceptance" `
  --mode "local_e2e" `
  --status "manual_pending" `
  --check "full_tests=pass:361 passed" `
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

To collect compile/test output and optional smoke evidence automatically, use
`relief-story-agent local-acceptance`. It preserves raw command output under
`command_outputs/`, renders the same acceptance report format, and writes a
machine-readable `acceptance_status.json` with blocking checks and suggested
actions.
For JSON-producing checks such as `model-check` and `diagnose`, a zero exit code
is not enough: `ready=false` or `valid=false` marks the check and generated
acceptance status as failed.

To inspect an existing report from scripts, another AI reviewer, or a future UI,
use:

```powershell
relief-story-agent acceptance-status `
  --report "D:/relief_story_acceptance/acceptance_report.json" `
  --pretty
```

The local API exposes the same read-only status at
`GET /api/local/acceptance-status?report_path=...`.

## ComfyUI / LTX 2.3 Workflows

To scan a user's existing ComfyUI integrated package or workflow folder before
they know the exact JSON path, use:

```powershell
relief-story-agent discover-comfyui-workflows `
  --search-root "D:/AI-Comfyui-onekey-V5/ComfyUI_windows_portable_nvidia/ComfyUI_windows_portable/ComfyUI" `
  --endpoint "127.0.0.1:8188/queue" `
  --filename-keyword "LTX" `
  --pretty
```

Launchers and future UI shells can call `POST /api/comfyui/discover-workflows`
with `search_roots[]`. The response ranks local workflow JSON files, reports
adapter compatibility, and returns a `recommended` workflow when a LiteGraph LTX
workflow can be patched automatically. Discovery only reads files; it does not
upload images, enqueue prompts, or edit workflow files.

Discovery can now recommend two automatic LiteGraph modes:

- `litegraph_ltx_auto_injection`: the four-grid workflow shape with an LTX JSON
  text node, optional `TD_LTXVAddGuideFromGrid`, seed, and filename prefix.
- `litegraph_ltx_widget_patch`: common integrated-package LTX graphs such as
  `ComfyUI-LTXVideo` examples. The agent patches existing positive/negative
  prompt widgets, `RandomNoise` seed widgets, `LoadImage` filenames, and
  `SaveVideo`/`VHS_VideoCombine` filename prefixes. It does not create nodes,
  install custom nodes, or rewrite sampler settings. Runtime COMBO model/LoRA
  filenames are only reconciled against `/object_info` options when the workflow
  value is not available locally and a close local asset alias exists.

For launcher, desktop-shell, or future UI flows where the user fills one local ComfyUI address box first, call:

```http
POST /api/comfyui/connect
```

Example payload:

```json
{
  "endpoint": "127.0.0.1:8188/queue",
  "workflow_api_path": "D:/ComfyUI/workflows/ltx23_four_grid.json",
  "timeout_seconds": 5
}
```

Endpoint input is normalized before use, so `127.0.0.1:8188`,
`http://127.0.0.1:8188/`, and `http://127.0.0.1:8188/queue` all target the
same local ComfyUI root.
ComfyUI HTTP calls bypass environment proxy settings, so localhost requests stay
inside the user's local integrated package instead of being routed through a
system proxy.

The endpoint pings ComfyUI `/queue`, reports running and pending queue counts,
and, when `workflow_api_path` is supplied, analyzes the local workflow with the
same LTX/placeholder logic used by real runs. For a reachable ComfyUI server it
also reads `/object_info` and verifies that every workflow `class_type` is
available in the runtime. It returns `ready`, `connected`, `checks`,
`suggested_actions`, `suggested_config`, and workflow details such as
`adapter_mode`, `grid_shape`, `ltx_injection_points`, and
`ltx_widget_patch_points`. It does not upload images, call models, enqueue
`/prompt`, wait for rendering, or download outputs.

If runtime node classes are missing, the response includes a failed
`comfyui_node_types` check and a suggested action
`install_or_enable_comfyui_nodes`.

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
- ComfyUI frontend LiteGraph JSON: first tries `litegraph_ltx_auto_injection`, which detects the LTX prompt JSON node, converts the graph to API prompt format, expands KJNodes `SetNode/GetNode` pairs into direct links, fills the LTX payload, seed, optional four-grid image, and output filename prefix, then queues one prompt for the whole short. If that JSON-node shape is not present, it tries `litegraph_ltx_widget_patch` for integrated-package LTX graphs with ordinary prompt widgets.

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

Use `execution_policy` as a per-run safety valve for unattended local batches.
It is checked before each stage starts, so it stops at a safe boundary without
killing an active model request or ComfyUI job:

```json
{
  "execution_policy": {
    "max_total_stage_executions": 18,
    "max_stage_executions": {
      "gpt_prompt_audit": 2,
      "four_grid_asset": 3,
      "comfyui": 3
    }
  }
}
```

Put the same object under batch `defaults` to apply it to every child run. When
the policy blocks a stage, the run records `execution_policy_blocked`,
`last_failure.code=execution_policy_exhausted`, and a non-retryable failure.
Preflight validation and `relief-story-agent diagnose` also check that
`max_total_stage_executions` can cover the planned pipeline stages. If the
budget is too low, diagnostics return `fix_execution_policy` before model quota
or ComfyUI GPU time is spent.

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

CLI equivalent:

```powershell
relief-story-agent recovery-plan --batch-id "{batch_id}" --pretty
relief-story-agent recover-batch --batch-id "{batch_id}" --dry-run --pretty
relief-story-agent batch-health --batch-id "{batch_id}" --pretty
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

Batch diagnostic endpoints (`/timeline`, `/artifacts`, `/recovery-plan`, and `/health`) tolerate missing child run state files when the batch state still exists. Missing children are returned as `inspect_missing_run` items instead of hiding the whole batch behind a 404, which makes restart and local file-damage drills easier to debug.

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

CLI equivalent:

```powershell
relief-story-agent scheduler --pretty
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

CLI equivalent:

```powershell
relief-story-agent run-status --run-id "{run_id}" --pretty
relief-story-agent run-events --run-id "{run_id}" --after 12 --pretty
relief-story-agent runs --status failed --parent-batch-id "{batch_id}" --limit 20 --pretty
```

Run list entries include `queue_priority`, so launchers can show why one item is waiting behind another.

Batch listing:

```http
GET /api/batches
GET /api/batches?status=completed&limit=20
```

CLI equivalent:

```powershell
relief-story-agent batches --status completed --limit 20 --pretty
relief-story-agent batch-status --batch-id "{batch_id}" --pretty
relief-story-agent batch-timeline --batch-id "{batch_id}" --pretty
relief-story-agent batch-health --batch-id "{batch_id}" --pretty
```

Batch list entries include compact child `items` with each child run's `queue_priority`, status, stage, and error. For a UI progress surface, `GET /api/batches/{batch_id}/timeline` aggregates every child run's timeline into one response with batch percent, per-item active stage, stage percent, publish-ready video path, retryability, recommended action, and links to artifacts, health, and recovery-plan endpoints.

Events are persisted with each run and include ordered `sequence` numbers. Current event types include `run_queued`, `run_claimed`, `stage_started`, `stage_completed`, `approval_queued`, `retry_queued`, `cancel_requested`, `comfyui_cancellation_requested`, `run_completed`, `run_failed`, and `run_cancelled`.

Artifact discovery:

```http
GET /api/runs/{run_id}/artifacts
GET /api/batches/{batch_id}/artifacts
POST /api/batches/{batch_id}/export
```

CLI equivalent:

```powershell
relief-story-agent run-artifacts --run-id "{run_id}" --pretty
relief-story-agent batch-artifacts --batch-id "{batch_id}" --pretty
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

CLI equivalent:

```powershell
relief-story-agent validate-export `
  --batch-id "{batch_id}" `
  --export-dir "D:/relief_story_exports/{batch_id}" `
  --save-report `
  --pretty
```

```json
{"export_dir": "D:/relief_story_exports/batch_abc123", "save_report": true}
```

The validator checks the export manifest, publish indexes, `publish_videos/`, every publish-ready video path referenced by `publish_index.json`, plus each publish video's recorded size and sha256 checksum. With `save_report: true`, it writes `validation_report.json` into the export directory.

Validate the zip itself after transfer:

```http
POST /api/batches/{batch_id}/export/validate-zip
```

CLI equivalent:

```powershell
relief-story-agent validate-export-zip `
  --batch-id "{batch_id}" `
  --zip-path "D:/relief_story_exports/{batch_id}.zip" `
  --save-report `
  --pretty
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

## Standalone ComfyUI Output Refresh

When you already have a ComfyUI `prompt_id`, you can query outputs without
re-running models and without submitting another workflow. This is useful after
a smoke real-run, after a server restart, or from a future UI button that only
needs to check/download rendered files from the user's local ComfyUI package.

CLI:

```powershell
relief-story-agent comfyui-outputs `
  --endpoint "http://127.0.0.1:8188" `
  --prompt-id "{prompt_id}" `
  --artifact-dir "D:/relief_story_outputs/manual_check" `
  --download `
  --pretty
```

Wait until ComfyUI history has files:

```powershell
relief-story-agent comfyui-outputs `
  --endpoint "http://127.0.0.1:8188" `
  --prompt-id "{prompt_id}" `
  --wait `
  --timeout-seconds 1200 `
  --poll-interval-seconds 5 `
  --artifact-dir "D:/relief_story_outputs/manual_check" `
  --download `
  --pretty
```

API:

```http
POST /api/comfyui/outputs
```

```json
{
  "endpoint": "http://127.0.0.1:8188",
  "prompt_ids": ["{prompt_id}"],
  "wait_for_completion": false,
  "download_outputs": true,
  "artifact_dir": "D:/relief_story_outputs/manual_check"
}
```

The response includes `ready`, media counts, `actual_outputs`, downloaded
`local_path` values, and timeout diagnostics when waiting does not finish. This
endpoint only reads ComfyUI `/history`, `/queue`, and `/view`; it does not call
large models, patch workflows, or enqueue prompts.

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
- `GET /api/local/bootstrap`
- `GET /api/local/doctor`
- `GET /api/local/readiness`
- `GET /api/local/acceptance-status`
- `POST /api/local/setup-bundle`
- `GET /api/config/models`
- `POST /api/config/validate`
- `POST /api/config/validate-batch`
- `POST /api/config/diagnose`
- `POST /api/config/diagnose-batch`
- `GET /api/scheduler`
- `POST /api/batches/plan`
- `POST /api/comfyui/connect`
- `POST /api/comfyui/discover-workflows`
- `POST /api/comfyui/preview`
- `POST /api/comfyui/outputs`
- `POST /api/smoke/comfyui`
- `POST /api/runs`
- `GET /api/runs`
- `GET /api/runs/{run_id}`
- `GET /api/runs/{run_id}/events`
- `GET /api/runs/{run_id}/timeline`
- `GET /api/runs/{run_id}/artifacts`
- `POST /api/runs/{run_id}/refresh-comfyui`
- `POST /api/runs/{run_id}/approve`
- `POST /api/runs/{run_id}/retry`
- `POST /api/runs/{run_id}/cancel`
- `POST /api/batches`
- `GET /api/batches`
- `GET /api/batches/{batch_id}`
- `GET /api/batches/{batch_id}/timeline`
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
