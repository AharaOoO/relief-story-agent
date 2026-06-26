# Relief Story Agent Completion Roadmap Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finish the non-UI backend path from local configuration to real model generation, real LTX 2.3 video output, batch recovery, export validation, and a release-ready acceptance evidence bundle.

**Architecture:** Keep the existing API-first backend. Do not replace the scheduler, ComfyUI adapter, model runtime, or artifact system unless a failing test proves a defect. Use the user's local ComfyUI package and user-provided workflow; patch declared inputs only, never auto-generate a ComfyUI node graph.

**Tech Stack:** Python 3.11+, FastAPI, Pydantic v2, httpx, Pillow, pytest, OpenAI-compatible model APIs, ComfyUI, LTX 2.3 workflow JSON, Windows PowerShell.

---

## Current Non-Negotiables

- Preserve this stage order:

```text
chief_screenwriter
-> deepseek_polish
-> quality_gate
-> gpt_prompt_writer
-> gpt_prompt_audit
-> gpt_prompt_reviser (最多一次)
-> final_prompts
-> four_grid_asset
-> artifacts
-> comfyui
```

- Do not prioritize UI.
- Do not call large models in smoke runner.
- Do not auto-generate ComfyUI node graphs.
- Do not claim completion without a real local video file and batch/export evidence.
- Do not use `git add .`.

## File Map

- `PROJECT_HANDOFF.md`: single source of truth for new sessions.
- `NEXT_SESSION_PROMPT.md`: short prompt that points new sessions to the handoff.
- `docs/LOCAL_DEPLOYMENT.md`: operator deployment guide.
- `relief_story_agent/README.md`: package-level API/CLI guide.
- `relief_story_agent/local_runtime.py`: bootstrap, doctor, local-readiness contracts.
- `relief_story_agent/api.py`: FastAPI routes.
- `relief_story_agent/cli.py`: unified CLI.
- `relief_story_agent/model_config.py`, `model_probe.py`, `model_runtime.py`: model config and real probe.
- `relief_story_agent/orchestrator.py`: fixed pipeline execution.
- `relief_story_agent/comfyui.py`, `ltx_workflow.py`, `comfyui_outputs.py`: ComfyUI integration.
- `relief_story_agent/local_acceptance.py`, `acceptance.py`: acceptance evidence.
- `relief_story_agent/tests/`: TDD coverage.

## Task 1: Verify Repository Baseline

**Files:** No edits expected.

- [ ] **Step 1: Confirm branch and worktree**

Run:

```powershell
git status --short --branch
git pull --ff-only
```

Expected:

```text
## master...origin/master
Already up to date.
```

- [ ] **Step 2: Run compile and tests**

Run:

```powershell
python -m compileall -q relief_story_agent
python -m pytest relief_story_agent/tests -q
```

Expected: compile exits `0`; pytest exits `0`.

- [ ] **Step 3: If tests fail, write a regression test before fixing code**

For each failure caused by a real bug, add or adjust the narrowest test in the existing test module, run that test to confirm failure, then implement the smallest fix.

Example command shape:

```powershell
python -m pytest relief_story_agent/tests/test_local_runtime.py::test_name -q
```

- [ ] **Step 4: Commit only if a fix was necessary**

```powershell
git add relief_story_agent tests docs PROJECT_HANDOFF.md NEXT_SESSION_PROMPT.md
git commit -m "fix: stabilize baseline before real acceptance"
git push
```

Use narrower paths if unrelated files appear.

## Task 2: Collect Real Model Credentials And Generate Local Config

**Files:**

- Modify only if necessary: `relief_story_agent/examples/model_config.local.example.json`
- Generated outside repo: `D:/relief_story_config/*`

- [ ] **Step 1: Ask user for model endpoint values**

Required values:

```text
Gemini-compatible base_url, model, GEMINI_API_KEY env value
DeepSeek-compatible base_url, model, DEEPSEEK_API_KEY env value
GPT text base_url, model, OPENAI_API_KEY env value
Image model base_url, model, image API key env value
ComfyUI endpoint
LTX 2.3 workflow path
Output root
```

- [ ] **Step 2: Set environment variables in the current PowerShell session**

Use the values supplied by the user:

```powershell
$env:GEMINI_API_KEY = "<user supplied>"
$env:DEEPSEEK_API_KEY = "<user supplied>"
$env:OPENAI_API_KEY = "<user supplied>"
```

Do not write secret values into repo files.

- [ ] **Step 3: Generate local config bundle**

```powershell
relief-story-agent setup `
  --output-dir "D:/relief_story_config" `
  --workflow-path "<user supplied LTX workflow json>" `
  --comfyui-endpoint "<user supplied ComfyUI endpoint>" `
  --output-root "D:/relief_story_runs" `
  --pretty
```

Expected files:

```text
D:/relief_story_config/model_config.local.json
D:/relief_story_config/run_request.full-ltx.json
D:/relief_story_config/batch_request.full-ltx.json
D:/relief_story_config/smoke_request.json
D:/relief_story_config/templates/prompt_writer.default.md
D:/relief_story_config/templates/prompt_audit.default.md
```

- [ ] **Step 4: Edit generated non-secret model config**

Open `D:/relief_story_config/model_config.local.json` and replace placeholder model/base URL values. Keep only `api_key_env` names, never plaintext keys.

- [ ] **Step 5: Check readiness**

```powershell
relief-story-agent local-readiness `
  --server "http://127.0.0.1:8891" `
  --acceptance-report "D:/relief_story_acceptance/acceptance_report.json" `
  --check-comfyui-connection `
  --comfyui-endpoint "<user supplied ComfyUI endpoint>" `
  --comfyui-workflow-path "<user supplied LTX workflow json>" `
  --pretty
```

Expected before real acceptance: `ready_for_real_runs=true` after local runtime, ComfyUI, model profiles, state, scheduler, and env vars are correct; `ready_for_release=false` until acceptance evidence exists.

## Task 3: Real Model Probe

**Files:**

- Modify only on failure with TDD:
  - `relief_story_agent/model_probe.py`
  - `relief_story_agent/model_runtime.py`
  - `relief_story_agent/tests/test_model_probe.py`
  - `relief_story_agent/tests/test_model_runtime.py`

- [ ] **Step 1: Run dry model check**

```powershell
relief-story-agent model-check `
  --model-config "D:/relief_story_config/model_config.local.json" `
  --pretty
```

Expected: `ready=true`.

- [ ] **Step 2: Run real model probe**

```powershell
relief-story-agent model-check `
  --model-config "D:/relief_story_config/model_config.local.json" `
  --real-run `
  --pretty
```

Expected: `ready=true`, every selected profile returns a small valid JSON response.

- [ ] **Step 3: If a provider response shape breaks parsing, write a failing test**

Add a fixture-style test in `relief_story_agent/tests/test_model_probe.py` that captures the exact provider response shape without secrets.

Run:

```powershell
python -m pytest relief_story_agent/tests/test_model_probe.py::test_provider_response_shape_name -q
```

Expected: FAIL before implementation.

- [ ] **Step 4: Implement the minimal parser/runtime fix**

Keep the existing model profile and output contract boundaries. Do not bypass stage contracts.

- [ ] **Step 5: Verify and commit**

```powershell
python -m pytest relief_story_agent/tests/test_model_probe.py relief_story_agent/tests/test_model_runtime.py -q
git diff --check
git add relief_story_agent/model_probe.py relief_story_agent/model_runtime.py relief_story_agent/tests/test_model_probe.py relief_story_agent/tests/test_model_runtime.py
git commit -m "fix: support real model probe response"
git push
```

Only commit files that changed.

## Task 4: Single Real End-To-End Run

**Files:**

- Modify only on failure with TDD:
  - `relief_story_agent/orchestrator.py`
  - `relief_story_agent/comfyui.py`
  - `relief_story_agent/comfyui_outputs.py`
  - `relief_story_agent/artifacts.py`
  - related tests under `relief_story_agent/tests/`

- [ ] **Step 1: Start API with persistent state and real model config**

```powershell
relief-story-agent serve `
  --host 127.0.0.1 `
  --port 8891 `
  --state-dir "D:/relief_story_state" `
  --model-config "D:/relief_story_config/model_config.local.json" `
  --max-workers 1 `
  --comfyui-submission-concurrency 1
```

- [ ] **Step 2: Diagnose the run request**

```powershell
relief-story-agent diagnose `
  --request "D:/relief_story_config/run_request.full-ltx.json" `
  --model-config "D:/relief_story_config/model_config.local.json" `
  --check-comfyui-connection `
  --pretty
```

Expected: `ready=true`.

- [ ] **Step 3: Create the run**

```powershell
relief-story-agent run `
  --request "D:/relief_story_config/run_request.full-ltx.json" `
  --server "http://127.0.0.1:8891" `
  --preflight `
  --check-comfyui-connection `
  --pretty
```

Record returned `run_id`.

- [ ] **Step 4: Poll status and artifacts**

```powershell
relief-story-agent run-status --server "http://127.0.0.1:8891" --run-id "{run_id}" --pretty
relief-story-agent run-timeline --server "http://127.0.0.1:8891" --run-id "{run_id}" --pretty
relief-story-agent run-artifacts --server "http://127.0.0.1:8891" --run-id "{run_id}" --pretty
```

Expected:

```text
status=completed
final storyboard exists
grid image exists
ComfyUI prompt id exists
downloaded local video path exists, is non-empty, and has a recognized video container
```

- [ ] **Step 5: If ComfyUI finishes but outputs are not recorded, test output refresh**

```powershell
relief-story-agent comfyui-outputs `
  --endpoint "<user supplied ComfyUI endpoint>" `
  --prompt-id "{prompt_id}" `
  --artifact-dir "D:/relief_story_outputs/manual_check" `
  --download `
  --pretty
```

If this works but run artifacts do not, write a failing test in `relief_story_agent/tests/test_comfyui_outputs.py` or `test_artifacts.py` before changing production code.

- [ ] **Step 6: Record single-run acceptance**

```powershell
relief-story-agent acceptance `
  --output-dir "D:/relief_story_acceptance" `
  --mode "single_run" `
  --status "completed" `
  --run-id "{run_id}" `
  --video-path "{local_mp4_path}" `
  --check "single_run=pass:run {run_id} completed with {local_mp4_path}" `
  --include-default-matrix `
  --pretty
```

Do not mark project complete yet.

## Task 5: Real Batch Run

**Files:**

- Modify only on failure with TDD:
  - `relief_story_agent/scheduler.py`
  - `relief_story_agent/recovery.py`
  - `relief_story_agent/batch_timeline.py`
  - `relief_story_agent/artifacts.py`
  - related tests

- [ ] **Step 1: Ensure batch request has at least 3 items**

Open `D:/relief_story_config/batch_request.full-ltx.json` and confirm `items.length >= 3`. Prefer 5 items for final proof.

- [ ] **Step 2: Plan batch**

```powershell
relief-story-agent batch-plan `
  --request "D:/relief_story_config/batch_request.full-ltx.json" `
  --server "http://127.0.0.1:8891" `
  --check-comfyui-connection `
  --pretty
```

Expected: visible item order, validation details, no enqueue.

- [ ] **Step 3: Create batch**

```powershell
relief-story-agent batch `
  --request "D:/relief_story_config/batch_request.full-ltx.json" `
  --server "http://127.0.0.1:8891" `
  --preflight `
  --check-comfyui-connection `
  --pretty
```

Record `batch_id`.

- [ ] **Step 4: Poll batch**

```powershell
relief-story-agent batch-status --server "http://127.0.0.1:8891" --batch-id "{batch_id}" --pretty
relief-story-agent batch-timeline --server "http://127.0.0.1:8891" --batch-id "{batch_id}" --pretty
relief-story-agent batch-health --server "http://127.0.0.1:8891" --batch-id "{batch_id}" --pretty
relief-story-agent batch-artifacts --server "http://127.0.0.1:8891" --batch-id "{batch_id}" --pretty
```

Expected: completed items have publish-ready outputs; failures have explicit failed stage and recommended action.

- [ ] **Step 5: If one failed item blocks the batch incorrectly, write a failing scheduler/batch test**

Use an existing fake provider pattern in `relief_story_agent/tests/test_batch_runs.py` or `test_scheduler.py`. Run the narrow test to see it fail before implementation.

- [ ] **Step 6: Record batch acceptance**

```powershell
relief-story-agent acceptance `
  --output-dir "D:/relief_story_acceptance" `
  --mode "batch_run" `
  --status "manual_pending" `
  --batch-id "{batch_id}" `
  --check "batch_run=pass:batch {batch_id} produced item summaries and publish-ready outputs" `
  --include-default-matrix `
  --pretty
```

Use `manual_pending` until restart recovery and export also pass.

## Task 6: Restart Recovery Drill

**Files:**

- Modify only on failure with TDD:
  - `relief_story_agent/scheduler.py`
  - `relief_story_agent/storage.py`
  - `relief_story_agent/recovery.py`
  - related tests

- [ ] **Step 1: Start a batch or use a running/queued batch**

Use the `batch_id` from Task 5.

- [ ] **Step 2: Stop the API process**

Use Ctrl+C in the server terminal.

- [ ] **Step 3: Restart API with the same state directory**

```powershell
relief-story-agent serve `
  --host 127.0.0.1 `
  --port 8891 `
  --state-dir "D:/relief_story_state" `
  --model-config "D:/relief_story_config/model_config.local.json" `
  --max-workers 1 `
  --comfyui-submission-concurrency 1
```

- [ ] **Step 4: Inspect recovery**

```powershell
relief-story-agent recovery-plan --server "http://127.0.0.1:8891" --batch-id "{batch_id}" --pretty
relief-story-agent scheduler --server "http://127.0.0.1:8891" --pretty
relief-story-agent batch-status --server "http://127.0.0.1:8891" --batch-id "{batch_id}" --pretty
```

Expected: no lost batch, no missing child run crash, explicit recovery actions.

- [ ] **Step 5: Dry-run safe recovery**

```powershell
relief-story-agent recover-batch `
  --server "http://127.0.0.1:8891" `
  --batch-id "{batch_id}" `
  --dry-run `
  --pretty
```

Expected: safe actions listed in `would_execute`, manual blockers listed in `skipped`.

- [ ] **Step 6: Record recovery acceptance**

```powershell
relief-story-agent acceptance `
  --output-dir "D:/relief_story_acceptance" `
  --mode "restart_recovery" `
  --status "manual_pending" `
  --batch-id "{batch_id}" `
  --check "restart_recovery=pass:batch {batch_id} survived restart and recovery-plan was queryable" `
  --include-default-matrix `
  --pretty
```

Keep final status pending until all checks pass.

## Task 7: Export And Validate

**Files:**

- Modify only on failure with TDD:
  - `relief_story_agent/artifacts.py`
  - `relief_story_agent/tests/test_artifacts.py`

- [ ] **Step 1: Export batch**

```powershell
relief-story-agent export-batch `
  --server "http://127.0.0.1:8891" `
  --batch-id "{batch_id}" `
  --export-root "D:/relief_story_exports" `
  --include-zip `
  --pretty
```

Expected:

```text
export_dir present
publish_index.json present
publish_index.csv present
publish_videos folder present with non-empty publish videos with recognized containers
zip_path present
sha256 sidecar present
```

- [ ] **Step 2: Validate directory**

```powershell
relief-story-agent validate-export `
  --server "http://127.0.0.1:8891" `
  --batch-id "{batch_id}" `
  --export-dir "D:/relief_story_exports/{batch_id}" `
  --save-report `
  --pretty
```

Expected: `valid=true`.

- [ ] **Step 3: Validate zip**

```powershell
relief-story-agent validate-export-zip `
  --server "http://127.0.0.1:8891" `
  --batch-id "{batch_id}" `
  --zip-path "D:/relief_story_exports/{batch_id}.zip" `
  --save-report `
  --pretty
```

Expected: `valid=true`.

- [ ] **Step 4: If validation fails for a real export structure, write a failing artifact test**

Use `tmp_path` and existing helpers in `relief_story_agent/tests/test_artifacts.py`.

- [ ] **Step 5: Record export acceptance**

```powershell
relief-story-agent acceptance `
  --output-dir "D:/relief_story_acceptance" `
  --mode "export" `
  --status "manual_pending" `
  --batch-id "{batch_id}" `
  --check "export=pass:publish index, videos, zip, sha256, validation reports exist" `
  --include-default-matrix `
  --pretty
```

## Task 8: Final Local Acceptance Bundle

**Files:**

- Modify only on failure with TDD:
  - `relief_story_agent/local_acceptance.py`
  - `relief_story_agent/acceptance.py`
  - `relief_story_agent/tests/test_local_acceptance.py`
  - `relief_story_agent/tests/test_acceptance.py`

- [ ] **Step 1: Run local acceptance**

```powershell
relief-story-agent local-acceptance `
  --output-dir "D:/relief_story_acceptance" `
  --repo-root "D:/codex工作区" `
  --model-config "D:/relief_story_config/model_config.local.json" `
  --run-request "D:/relief_story_config/run_request.full-ltx.json" `
  --batch-request "D:/relief_story_config/batch_request.full-ltx.json" `
  --local-demo `
  --smoke-request "D:/relief_story_config/smoke_request.json" `
  --comfyui-output-prompt-id "{prompt_id}" `
  --comfyui-output-artifact-dir "D:/relief_story_acceptance/comfyui_outputs" `
  --pretty
```

Expected generated files:

```text
D:/relief_story_acceptance/command_outputs/
D:/relief_story_acceptance/local_acceptance_summary.json
D:/relief_story_acceptance/acceptance_report.json
D:/relief_story_acceptance/acceptance_status.json
D:/relief_story_acceptance/ACCEPTANCE_REPORT.md
```

- [ ] **Step 2: Query acceptance status**

```powershell
relief-story-agent acceptance-status `
  --report "D:/relief_story_acceptance/acceptance_report.json" `
  --pretty
```

Expected for final completion: `ready_for_release=true`.

- [ ] **Step 3: Query local-readiness**

```powershell
relief-story-agent local-readiness `
  --server "http://127.0.0.1:8891" `
  --acceptance-report "D:/relief_story_acceptance/acceptance_report.json" `
  --check-comfyui-connection `
  --comfyui-endpoint "<user supplied ComfyUI endpoint>" `
  --comfyui-workflow-path "<user supplied LTX workflow json>" `
  --pretty
```

Expected for final completion: `ready_for_real_runs=true` and `ready_for_release=true`.

- [ ] **Step 4: Final verification**

```powershell
git diff --check
python -m compileall -q relief_story_agent
python -m pytest relief_story_agent/tests -q
```

Expected: all exit `0`.

- [ ] **Step 5: Update handoff and commit**

Update `PROJECT_HANDOFF.md` with exact evidence:

```text
model-check --real-run result
single run_id and video path
batch_id and item count
restart recovery result
export paths and validation result
acceptance_status ready_for_release=true
pytest count
```

Commit:

```powershell
git add PROJECT_HANDOFF.md docs/LOCAL_DEPLOYMENT.md relief_story_agent
git commit -m "docs: record final local acceptance evidence"
git push
```

Use narrower paths if only docs changed.

## Completion Definition

The non-UI backend can be called complete only when all of these have evidence:

- Full tests pass.
- `model-check --real-run` passes for Gemini, DeepSeek, GPT text, and image provider.
- Single run completes with a local video file.
- Batch of at least 3, preferably 5, items completes or produces safe, explicit blockers.
- Restart recovery drill works with persistent state.
- Batch export and zip validation pass.
- `acceptance-status` reports `ready_for_release=true`.
- `local-readiness` reports `ready_for_release=true`.
- `PROJECT_HANDOFF.md` records exact commands, IDs, artifact directories, and video paths.
