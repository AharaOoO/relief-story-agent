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
- `templates/prompt_writer.default.md`
- `templates/prompt_audit.default.md`

Editable examples are also available under `relief_story_agent/examples/`.

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
  --pretty
relief-story-agent local-bootstrap --pretty
relief-story-agent local-doctor --server "http://127.0.0.1:8891" --pretty
```

`model-check` defaults to a no-quota dry-run that checks profile wiring, model
names, and environment variables. Once the keys are set, run the same command
with `--real-run` to send one tiny JSON probe per profile before spending quota
on a full short-video run.

When handing the install to another operator or another AI reviewer, collect a
single evidence bundle:

```powershell
relief-story-agent local-acceptance `
  --output-dir "D:/relief_story_acceptance" `
  --repo-root "D:/codex工作区" `
  --model-config "D:/relief_story_config/model_config.local.json" `
  --run-request "D:/relief_story_config/run_request.full-ltx.json" `
  --batch-request "D:/relief_story_config/batch_request.full-ltx.json" `
  --smoke-request "D:/relief_story_config/smoke_request.json" `
  --smoke-dry-run `
  --pretty
```

This runs `compileall`, full tests, optional `model-check`, run/batch
`diagnose`, and optional `smoke-comfyui`, stores raw stdout/stderr under
`command_outputs/`, and writes both JSON and Markdown acceptance reports.

To check the same local ComfyUI address a future UI box would collect, keep the
API server running and ask local doctor to ping `/queue`:

```powershell
relief-story-agent local-doctor `
  --server "http://127.0.0.1:8891" `
  --check-comfyui-connection `
  --comfyui-endpoint "127.0.0.1:8188/queue" `
  --pretty
```

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

Prepare a manual 2x2 four-grid image, then start with dry-run:

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

relief-story-agent run-artifacts `
  --server "http://127.0.0.1:8891" `
  --run-id "{run_id}" `
  --pretty

Invoke-RestMethod "http://127.0.0.1:8891/api/runs/{run_id}"
Invoke-RestMethod "http://127.0.0.1:8891/api/runs/{run_id}/audit"
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

relief-story-agent batch-artifacts `
  --server "http://127.0.0.1:8891" `
  --batch-id "{batch_id}" `
  --pretty
```

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

The export validator checks publish indexes, copied video files, zip checksum,
and the validation report.

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
  --smoke-request "D:/relief_story_config/smoke_request.json" `
  --smoke-dry-run `
  --pretty
```

The command writes `local_acceptance_summary.json`, raw command output files,
`acceptance_report.json`, and `ACCEPTANCE_REPORT.md`.

For manual evidence entry:

```powershell
relief-story-agent acceptance `
  --output-dir "D:/relief_story_acceptance" `
  --mode "local_e2e" `
  --status "manual_pending" `
  --include-default-matrix `
  --notes "Record exact run ids, batch ids, artifact dirs, video paths, and export paths."
```

Do not mark the software complete until the acceptance matrix has real evidence
for tests, dry smoke, real smoke, single run, batch run, restart recovery,
export validation, and fresh setup.
