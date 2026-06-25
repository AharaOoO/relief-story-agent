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

## 4. Check ComfyUI

Start ComfyUI, then test the local address box flow:

```powershell
relief-story-agent connect-comfyui `
  --request "D:/relief_story_config/comfyui_connect.json" `
  --pretty
```

This pings `/queue` and analyzes the workflow. It does not upload images, call
models, enqueue `/prompt`, wait for video, or download outputs.

## 5. Diagnose Before Spending Quota

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
Invoke-RestMethod "http://127.0.0.1:8891/api/runs/{run_id}"
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

## 10. Recovery Drill

Stop the API while a batch is queued or running. Start it again with the same
`--state-dir`, then inspect:

```powershell
Invoke-RestMethod "http://127.0.0.1:8891/api/batches/{batch_id}/recovery-plan"
Invoke-RestMethod "http://127.0.0.1:8891/api/scheduler"
```

Run safe recovery actions only after reviewing the plan:

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

The CLI uses direct local HTTP for these API calls and ignores environment proxy
settings, which avoids accidental proxy failures for `127.0.0.1`.

## 12. Record Acceptance

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
