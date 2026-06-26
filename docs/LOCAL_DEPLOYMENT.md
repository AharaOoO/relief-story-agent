# Local Deployment Guide

This guide is for a non-developer Windows machine that already has a local
ComfyUI package or can start one. The agent stays API-first: the CLI and HTTP
API prepare, validate, queue, resume, and export work; the user's existing
ComfyUI installation performs the LTX render.

## 1. Install

From the repository root:

```powershell
python -m pip install -e .
```

If Python is not on PATH, install Python 3.11 or newer first. Keep the repo in a
path the user can write to, and keep generated state/output outside the repo.

## 2. Configure Secrets

Use environment variables only. Do not write API keys into JSON files.

```powershell
$env:GEMINI_API_KEY = "your-gemini-key"
$env:DEEPSEEK_API_KEY = "your-deepseek-key"
$env:OPENAI_API_KEY = "your-openai-or-compatible-key"
```

The generated model registry references `GEMINI_API_KEY`, `DEEPSEEK_API_KEY`,
and `OPENAI_API_KEY` through `api_key_env`.

## 3. Prepare Local Config

Point the setup command at the user's existing LTX 2.3 workflow JSON:

```powershell
relief-story-agent setup `
  --output-dir "D:/relief_story_config" `
  --workflow-path "D:/ComfyUI/workflows/ltx23_four_grid.json" `
  --comfyui-endpoint "http://127.0.0.1:8188" `
  --output-root "D:/relief_story_runs" `
  --pretty
```

The setup command writes:

- `model_config.local.json`
- `comfyui_connect.json`
- `run_request.full-ltx.json`
- `batch_request.full-ltx.json`
- `smoke_request.json`
- `templates/prompt_writer.default.md`
- `templates/prompt_audit.default.md`

Editable examples are also available under `relief_story_agent/examples/`.

The HTTP equivalent for a local launcher or future UI is
`POST /api/local/setup-bundle`:

```json
{
  "output_dir": "D:/relief_story_config",
  "workflow_path": "D:/ComfyUI/workflows/ltx23_four_grid.json",
  "comfyui_endpoint": "127.0.0.1:8188/queue",
  "output_root": "D:/relief_story_runs"
}
```

It writes the same file bundle as `relief-story-agent setup`, normalizes common
ComfyUI address-box inputs, and never writes API keys. Model JSON files only
store environment variable names such as `GEMINI_API_KEY`. The response also
includes machine-readable `files`, `checks`, `next_commands`, and
`next_endpoints` fields so a launcher can show exactly which files were written
and which validation action should run next. `next_commands.doctor` uses the
normalized ComfyUI endpoint from the user's address box and the selected
workflow path. The generated `smoke_request.json` is wired for the same
workflow and endpoint; use `next_commands.smoke_dry_run` before
`next_commands.smoke_real_run`. `next_commands.local_acceptance` chains the
generated model config, run request, batch request, smoke request, and local
demo into one evidence-collection command. `checks.smoke_grid_image` tells a
launcher whether the manual smoke four-grid image is already present.
`next_commands.acceptance_status` reads the generated acceptance report and
lists the remaining blocking evidence. `next_commands.local_readiness` combines
local doctor, the ComfyUI address/workflow check, and the acceptance report into
one JSON status for a launcher or future UI.

Generated run and batch request files include an `execution_policy` safety
valve. It limits stage starts before they happen, which protects unattended
batches from spending model quota or GPU time in a runaway retry pattern. The
default bundle uses:

```json
{
  "execution_policy": {
    "max_total_stage_executions": 18,
    "max_stage_executions": {
      "chief_screenwriter": 2,
      "deepseek_polish": 2,
      "gpt_prompt_writer": 2,
      "gpt_prompt_audit": 2,
      "four_grid_asset": 3,
      "comfyui": 3
    }
  }
}
```

For batches, keep this under `defaults.execution_policy` unless a specific item
needs a different budget.

Preflight validation and `relief-story-agent diagnose` also check the total
budget before any model call or ComfyUI `/prompt` submission. If
`max_total_stage_executions` cannot cover the planned stages, diagnostics return
`fix_execution_policy` so the local launcher can ask the operator to raise the
budget first.

## 4. Check ComfyUI

Start ComfyUI, then scan the local integrated package or workflow folder for
usable workflow JSON candidates:

```powershell
relief-story-agent discover-comfyui-workflows `
  --search-root "D:/AI-Comfyui-onekey-V5/ComfyUI_windows_portable_nvidia/ComfyUI_windows_portable/ComfyUI" `
  --endpoint "127.0.0.1:8188/queue" `
  --filename-keyword "LTX" `
  --pretty
```

The HTTP equivalent for launchers and future UI shells is
`POST /api/comfyui/discover-workflows`. It reads local JSON files, classifies
adapter compatibility, and returns a `recommended` workflow when one can be
patched automatically. It does not upload, enqueue, or edit workflow files.

After choosing a candidate, test the local address box flow:

```powershell
relief-story-agent connect-comfyui `
  --request "D:/relief_story_config/comfyui_connect.json" `
  --pretty
```

The ComfyUI endpoint accepts common address-box input. For example,
`127.0.0.1:8188`, `http://127.0.0.1:8188/`, and
`http://127.0.0.1:8188/queue` are normalized to
`http://127.0.0.1:8188` before the agent pings `/queue`.
Local ComfyUI HTTP calls bypass environment proxy settings, so a Windows proxy
cannot accidentally turn `127.0.0.1` requests into proxy `502` errors.

This pings `/queue` and analyzes the workflow. It does not upload images, call
models, enqueue `/prompt`, wait for video, or download outputs.

## 5. Diagnose Before Spending Quota

Print the fixed stage contract when checking a local install or handing the
project to another operator:

```powershell
relief-story-agent pipeline-schema --pretty
relief-story-agent template-check `
  --writer-template "D:/relief_story_config/templates/prompt_writer.default.md" `
  --audit-template "D:/relief_story_config/templates/prompt_audit.default.md" `
  --pretty
relief-story-agent model-check `
  --model-config "D:/relief_story_config/model_config.local.json" `
  --run-request "D:/relief_story_config/run_request.full-ltx.json" `
  --pretty
relief-story-agent local-bootstrap --pretty
relief-story-agent local-doctor --server "http://127.0.0.1:8891" --pretty
```

`model-check` defaults to a no-quota dry-run that checks profile wiring, model
names, environment variables, and the run request's automatic four-grid image
provider when `--run-request` is supplied. Once the keys are set, run the same
command with `--real-run` to send one tiny JSON probe per text profile and one
minimal image probe before spending quota on a full short-video run.

`local-bootstrap` exposes both `endpoints.local_doctor` and
`comfyui.doctor_endpoint` for launcher/UI address-box flows. Use that doctor
endpoint with `check_comfyui_connection=true`, the pasted ComfyUI address, and
the selected workflow path before running smoke or batch work.

When handing the install to another operator or another AI reviewer, collect a
single evidence bundle:

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

This runs `compileall`, full tests, `pipeline-schema`, optional `model-check`,
run/batch `diagnose`, optional offline `local-demo`, optional `smoke-comfyui`, and
optional standalone ComfyUI output refresh/download evidence, stores
raw stdout/stderr under `command_outputs/`, and writes both JSON and Markdown
acceptance reports plus `acceptance_status.json`. When both model config and
run request are provided, the collected `model-check` evidence also covers the
configured image provider. Use `--model-check-real-run` only for the final
evidence pass after real model API keys are configured. When ComfyUI output
download evidence is collected, the reported video `local_path` must point to
an existing non-empty file with a recognized video container before that check
can pass; the validator checks container signatures instead of trusting the
filename extension. The `pipeline_schema` check must pass to prove the fixed
canonical stage order and invariants are still intact. Re-running `local-acceptance` in
the same output directory preserves
previously passed checks, such as `single_run`, `batch_run`, `restart_recovery`,
and `export`, unless the new run records the same check id again; existing
`run_id`, `batch_id`, and video paths are also carried forward.
Imported `smoke_result.json` and `local_demo_summary.json` evidence is parsed
before the top-level bundle status is set, so a not-ready source file marks
`local-acceptance` failed even when the command that produced it exited `0`.
Preserved `video_paths` from an existing report are also rechecked before the
top-level bundle status is set, so a stale or missing mp4 keeps the bundle
failed instead of only appearing later as an `acceptance-status` blocker.
For `single_run` acceptance, a passing `single_run` check must include at least
one recorded video path. If it does not, `acceptance-status` reports a
`video_files` blocker and `ready_for_release=false`. Existing `video_paths` are
rechecked on disk each time `acceptance-status` reads the report.

To query a generated report without reading Markdown manually:

```powershell
relief-story-agent acceptance-status `
  --report "D:/relief_story_acceptance/acceptance_report.json" `
  --pretty
```

HTTP equivalent for launchers and future UI shells:
`GET /api/local/acceptance-status?report_path=...`.
Generated reports and the status query always overlay the full release matrix.
A report created for only smoke, local-demo, or another narrow check stays
blocked until the missing release gates have evidence.
If the report's top-level status is not completed, `acceptance-status` also
returns an `overall_status` blocker even when individual checks are passing.

To query the whole local deployment state in one call, including the ComfyUI
address box value, selected workflow path, and acceptance evidence blockers:

```powershell
relief-story-agent local-readiness `
  --server "http://127.0.0.1:8891" `
  --acceptance-report "D:/relief_story_acceptance/acceptance_report.json" `
  --check-comfyui-connection `
  --comfyui-endpoint "127.0.0.1:8188/queue" `
  --comfyui-workflow-path "D:/ComfyUI/workflows/ltx23_four_grid.json" `
  --pretty
```

HTTP equivalent for launchers and future UI shells:
`GET /api/local/readiness?acceptance_report_path=...&check_comfyui_connection=true&comfyui_endpoint=...&comfyui_workflow_path=...`.

The response includes `ready_for_real_runs`, `ready_for_release`, a phase,
blocking checks, deduped `suggested_actions`, and a `ui_contract` that names the
ComfyUI address field and related endpoints.
`ready_for_real_runs` stays `false` until local doctor has no failures and no
warnings, so placeholder/missing model profiles, non-persistent state, or a
missing scheduler do not get reported as unattended-run ready.
Use `summary.real_run_blocking_count` for setup issues that block unattended
real runs and `summary.release_blocking_count` for all non-passing checks that
block release readiness.

For a quick no-key/no-GPU confidence check before touching real services, run:

```powershell
relief-story-agent local-demo `
  --output-dir "D:/relief_story_demo" `
  --batch-size 2 `
  --pretty
```

This writes `local_demo_summary.json`, a single completed fake-model run, a
completed fake-model batch, and `local_demo_restart_recovery.json` under the
chosen output directory. The restart drill reloads persisted state and confirms
the recovery plan can still identify a retryable item. It deliberately keeps
ComfyUI and image generation disabled, so treat it as an orchestration,
artifact, and recovery smoke check, not as proof that real videos render.

To check the same local ComfyUI address a future UI box would collect, keep the
API server running and ask local doctor to ping `/queue`:

```powershell
relief-story-agent local-doctor `
  --server "http://127.0.0.1:8891" `
  --check-comfyui-connection `
  --comfyui-endpoint "127.0.0.1:8188/queue" `
  --comfyui-workflow-path "D:/ComfyUI/workflows/ltx23_four_grid.json" `
  --pretty
```

When `--comfyui-workflow-path` is provided, local doctor checks not only that
`/queue` is reachable, but also that the selected workflow's node classes are
available in the running ComfyUI package.

Run local diagnostics before creating a real run:

```powershell
relief-story-agent diagnose `
  --request "D:/relief_story_config/run_request.full-ltx.json" `
  --model-config "D:/relief_story_config/model_config.local.json" `
  --check-comfyui-connection `
  --pretty
```

For batch:

```powershell
relief-story-agent diagnose `
  --request "D:/relief_story_config/batch_request.full-ltx.json" `
  --model-config "D:/relief_story_config/model_config.local.json" `
  --kind batch `
  --pretty
```

Exit code is `0` when `ready=true`; exit code is `1` when configuration is
blocked. Fix all suggested actions before real generation.

## 6. Run Smoke

Prepare a manual 2x2 four-grid image at the `manual_grid_image_path` recorded
in `D:/relief_story_config/smoke_request.json`, then start with dry-run:

```powershell
relief-story-agent smoke-comfyui `
  --request "D:/relief_story_config/smoke_request.json" `
  --dry-run
```

Searchable one-line form: `relief-story-agent smoke-comfyui --dry-run`.

The dry-run writes smoke artifacts but does not upload and does not enqueue.
After dry-run passes, run the real smoke:

```powershell
relief-story-agent smoke-comfyui `
  --request "D:/relief_story_config/smoke_request.json"
```

Real smoke uploads the four-grid image, patches the workflow, and queues
ComfyUI `/prompt`. It still does not wait for video rendering or download video.

If ComfyUI later finishes that prompt, check and optionally download the output
without submitting anything new:

```powershell
relief-story-agent comfyui-outputs `
  --endpoint "http://127.0.0.1:8188" `
  --prompt-id "{prompt_id_from_smoke_result}" `
  --artifact-dir "D:/relief_story_outputs/smoke_manual_check" `
  --download `
  --pretty
```

For a future launcher or UI, the equivalent endpoint is `POST /api/comfyui/outputs`.
The request accepts the user's local ComfyUI address, one or more `prompt_ids`,
`wait_for_completion`, `download_outputs`, and an `artifact_dir`.

## 7. Start The API

```powershell
relief-story-agent serve `
  --host 127.0.0.1 `
  --port 8891 `
  --state-dir "D:/relief_story_state" `
  --model-config "D:/relief_story_config/model_config.local.json" `
  --max-workers 2 `
  --comfyui-submission-concurrency 1
```

Keep the same `--state-dir` across restarts so queued/running work can be
recovered.

## 8. Create One Run

CLI:

```powershell
relief-story-agent run `
  --request "D:/relief_story_config/run_request.full-ltx.json" `
  --server "http://127.0.0.1:8891" `
  --preflight `
  --check-comfyui-connection `
  --pretty
```

HTTP equivalent:

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri "http://127.0.0.1:8891/api/runs?preflight=true&check_comfyui_connection=true" `
  -ContentType "application/json" `
  -InFile "D:/relief_story_config/run_request.full-ltx.json"
```

Poll:

```powershell
relief-story-agent runs `
  --server "http://127.0.0.1:8891" `
  --status running `
  --limit 20 `
  --pretty

relief-story-agent run-status `
  --server "http://127.0.0.1:8891" `
  --run-id "{run_id}" `
  --pretty

relief-story-agent run-events `
  --server "http://127.0.0.1:8891" `
  --run-id "{run_id}" `
  --after 0 `
  --pretty

relief-story-agent run-audit `
  --server "http://127.0.0.1:8891" `
  --run-id "{run_id}" `
  --pretty

relief-story-agent run-timeline `
  --server "http://127.0.0.1:8891" `
  --run-id "{run_id}" `
  --pretty

relief-story-agent run-artifacts `
  --server "http://127.0.0.1:8891" `
  --run-id "{run_id}" `
  --pretty

Invoke-RestMethod "http://127.0.0.1:8891/api/runs/{run_id}"
Invoke-RestMethod "http://127.0.0.1:8891/api/runs/{run_id}/audit"
Invoke-RestMethod "http://127.0.0.1:8891/api/runs/{run_id}/timeline"
Invoke-RestMethod "http://127.0.0.1:8891/api/runs/{run_id}/artifacts"
```

## 9. Create A Batch

Preview first:

```powershell
relief-story-agent batch-plan `
  --request "D:/relief_story_config/batch_request.full-ltx.json" `
  --server "http://127.0.0.1:8891" `
  --check-comfyui-connection `
  --pretty
```

HTTP equivalent:

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri "http://127.0.0.1:8891/api/batches/plan?check_comfyui_connection=true" `
  -ContentType "application/json" `
  -InFile "D:/relief_story_config/batch_request.full-ltx.json"
```

Then enqueue:

```powershell
relief-story-agent batch `
  --request "D:/relief_story_config/batch_request.full-ltx.json" `
  --server "http://127.0.0.1:8891" `
  --preflight `
  --check-comfyui-connection `
  --pretty
```

HTTP equivalent:

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri "http://127.0.0.1:8891/api/batches?preflight=true&check_comfyui_connection=true" `
  -ContentType "application/json" `
  -InFile "D:/relief_story_config/batch_request.full-ltx.json"
```

HTTP endpoint summary: `POST /api/batches`.

Track the batch:

```powershell
relief-story-agent batches `
  --server "http://127.0.0.1:8891" `
  --status running `
  --limit 20 `
  --pretty

relief-story-agent batch-status `
  --server "http://127.0.0.1:8891" `
  --batch-id "{batch_id}" `
  --pretty

relief-story-agent batch-health `
  --server "http://127.0.0.1:8891" `
  --batch-id "{batch_id}" `
  --pretty

relief-story-agent batch-timeline `
  --server "http://127.0.0.1:8891" `
  --batch-id "{batch_id}" `
  --pretty

relief-story-agent batch-artifacts `
  --server "http://127.0.0.1:8891" `
  --batch-id "{batch_id}" `
  --pretty
```

Use `batch-timeline` for launcher/UI progress cards: it reports total batch percent, each child run's active stage and stage percent, publish-ready video path, retryability, and recommended next action.

## 10. Recovery Drill

Stop the API while a batch is queued or running. Start it again with the same
`--state-dir`, then inspect:

```powershell
relief-story-agent recovery-plan `
  --server "http://127.0.0.1:8891" `
  --batch-id "{batch_id}" `
  --pretty

relief-story-agent scheduler `
  --server "http://127.0.0.1:8891" `
  --pretty

relief-story-agent batch-status `
  --server "http://127.0.0.1:8891" `
  --batch-id "{batch_id}" `
  --pretty
```

HTTP equivalent:

```powershell
Invoke-RestMethod "http://127.0.0.1:8891/api/batches/{batch_id}/recovery-plan"
Invoke-RestMethod "http://127.0.0.1:8891/api/scheduler"
```

Run safe recovery actions only after reviewing the plan:

```powershell
relief-story-agent recover-batch `
  --server "http://127.0.0.1:8891" `
  --batch-id "{batch_id}" `
  --dry-run `
  --pretty
```

HTTP equivalent:

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri "http://127.0.0.1:8891/api/batches/{batch_id}/recover" `
  -ContentType "application/json" `
  -Body '{"dry_run":true}'
```

## 11. Export And Validate

```powershell
relief-story-agent export-batch `
  --server "http://127.0.0.1:8891" `
  --batch-id "{batch_id}" `
  --export-root "D:/relief_story_exports" `
  --include-zip `
  --pretty
```

HTTP equivalent:

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri "http://127.0.0.1:8891/api/batches/{batch_id}/export" `
  -ContentType "application/json" `
  -Body '{"export_root":"D:/relief_story_exports","include_zip":true}'

Invoke-RestMethod `
  -Method Post `
  -Uri "http://127.0.0.1:8891/api/batches/{batch_id}/export/validate" `
  -ContentType "application/json" `
  -Body '{"export_dir":"D:/relief_story_exports/{batch_id}","save_report":true}'
```

The export validator checks publish indexes, copied video files, non-empty
publish videos with recognized container signatures, zip checksum, and the validation
report.

CLI validation:

```powershell
relief-story-agent validate-export `
  --server "http://127.0.0.1:8891" `
  --batch-id "{batch_id}" `
  --export-dir "D:/relief_story_exports/{batch_id}" `
  --save-report `
  --pretty

relief-story-agent validate-export-zip `
  --server "http://127.0.0.1:8891" `
  --batch-id "{batch_id}" `
  --zip-path "D:/relief_story_exports/{batch_id}.zip" `
  --save-report `
  --pretty
```

The CLI uses direct local HTTP for these API calls and ignores environment proxy
settings, which avoids accidental proxy failures for `127.0.0.1`.

## 12. Record Acceptance

For the repeatable local evidence bundle:

```powershell
relief-story-agent local-acceptance `
  --output-dir "D:/relief_story_acceptance" `
  --repo-root "D:/codex工作区" `
  --model-config "D:/relief_story_config/model_config.local.json" `
  --run-request "D:/relief_story_config/run_request.full-ltx.json" `
  --batch-request "D:/relief_story_config/batch_request.full-ltx.json" `
  --model-check-real-run `
  --smoke-request "D:/relief_story_config/smoke_request.json" `
  --smoke-dry-run `
  --comfyui-output-prompt-id "{prompt_id}" `
  --comfyui-output-artifact-dir "D:/relief_story_acceptance/comfyui_outputs" `
  --pretty
```

The command writes `local_acceptance_summary.json`, raw command output files,
`acceptance_report.json`, `acceptance_status.json`, and
`ACCEPTANCE_REPORT.md`. Existing passed checks in the same output directory are
carried forward so the final bundle can combine manual evidence entered earlier
with the fresh command outputs, while preserving the top-level run and batch ids.

For manual evidence entry:

```powershell
relief-story-agent acceptance `
  --output-dir "D:/relief_story_acceptance" `
  --mode "local_e2e" `
  --status "manual_pending" `
  --include-default-matrix `
  --notes "Record exact run ids, batch ids, artifact dirs, video paths, and export paths."
```

Generated reports always include the full release matrix; the flag remains
accepted for older command snippets and explicit manual checklists.

Do not mark the software complete until the acceptance matrix has real evidence
for tests, pipeline schema, dry smoke, real smoke, single run, batch run,
restart recovery, export validation, and fresh setup.
