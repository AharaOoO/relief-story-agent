# RunningHub Cloud Generation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add RunningHub advanced workflow API as Relief Story Agent generation mode 2 without weakening the local ComfyUI release evidence gate or committing secrets.

**Architecture:** Keep local ComfyUI as generation mode 1 and add RunningHub as a separate provider module with a small request model, redacted payload builder, direct submit/status/output helpers, CLI commands, and local API endpoints. Later UI work should call these endpoints rather than embedding RunningHub-specific HTTP logic in the frontend.

**Tech Stack:** Python 3.11+, Pydantic v2, httpx, FastAPI, pytest, RunningHub advanced workflow API, Windows PowerShell.

---

## File Map

- `relief_story_agent/runninghub.py`: RunningHub request models, payload builder, readiness check, submit/status/output calls.
- `relief_story_agent/api.py`: `/api/runninghub/*` endpoints.
- `relief_story_agent/cli.py`: `runninghub-*` commands.
- `relief_story_agent/local_runtime.py`: bootstrap endpoint map for future UI.
- `relief_story_agent/examples/runninghub_request.example.json`: non-secret request template.
- `relief_story_agent/tests/test_runninghub.py`: RunningHub TDD coverage.
- `docs/superpowers/specs/2026-06-27-runninghub-cloud-generation-design.md`: product and API design.
- `docs/LOCAL_DEPLOYMENT.md`, `PROJECT_HANDOFF.md`, `NEXT_SESSION_HANDOFF_REPORT.md`, `NEXT_SESSION_PROMPT.md`: operator handoff and current status.

## Task 1: Land Backend Starter Entry

Status: implemented on branch `codex/export-acceptance-evidence`.

- [x] **Step 1: Write failing tests for RunningHub payload and secret redaction**

Command:

```powershell
python -m pytest relief_story_agent/tests/test_runninghub.py -q
```

Expected before implementation: FAIL because `relief_story_agent.runninghub` does not exist.

- [x] **Step 2: Implement request models and payload builder**

Create `RunningHubWorkflowRequest`, `RunningHubNodeInfo`,
`RunningHubTaskRequest`, and `RunningHubTaskOutputsRequest`. Convert local
snake_case fields to RunningHub camelCase fields only at the boundary.

- [x] **Step 3: Add readiness check**

`check_runninghub_request()` returns `ready=false` when `RUNNINGHUB_API_KEY` is
missing and never returns the key value.

- [x] **Step 4: Add dry-run and live HTTP helpers**

`submit_runninghub_task(..., dry_run=True)` returns the official create payload
with `apiKey` redacted. Live helpers call:

```text
POST https://www.runninghub.ai/task/openapi/create
POST https://www.runninghub.ai/task/openapi/status
POST https://www.runninghub.ai/task/openapi/outputs
```

- [x] **Step 5: Add CLI/API/bootstrap entry points**

Commands:

```powershell
relief-story-agent runninghub-check --request relief_story_agent/examples/runninghub_request.example.json --pretty
relief-story-agent runninghub-submit --request relief_story_agent/examples/runninghub_request.example.json --dry-run --pretty
relief-story-agent runninghub-status --task-id "{task_id}" --pretty
relief-story-agent runninghub-outputs --task-id "{task_id}" --pretty
```

API endpoints:

```text
POST /api/runninghub/check
POST /api/runninghub/submit
POST /api/runninghub/status
POST /api/runninghub/outputs
```

- [x] **Step 6: Verify starter entry**

Run:

```powershell
python -m pytest relief_story_agent/tests/test_runninghub.py -q
python -m pytest relief_story_agent/tests/test_cli.py::test_cli_help_lists_core_local_commands relief_story_agent/tests/test_local_runtime.py::test_build_local_bootstrap_exposes_ui_ports_and_core_endpoints -q
```

Expected: all selected tests pass.

## Task 2: Real RunningHub Workflow Mapping

Status: planned, blocked on real RunningHub workflow details.

- [ ] **Step 1: Collect non-secret workflow configuration**

Ask the operator for:

```text
RunningHub workflowId
RunningHub node ids and field names for prompt, image/material URL, seed, duration, and output controls
Whether personal queue or instance type is required
Whether webhookUrl should be used
```

Do not ask for or store plaintext API keys in repo files.

- [ ] **Step 2: Create a machine-local request file outside git**

Write a local-only file such as:

```text
D:/relief_story_config/runninghub_request.local.json
```

It should contain `workflow_id`, `api_key_env`, and `node_info_list`, but no
plaintext key.

- [ ] **Step 3: Dry-run the mapped request**

Run:

```powershell
relief-story-agent runninghub-check --request "D:/relief_story_config/runninghub_request.local.json" --pretty
relief-story-agent runninghub-submit --request "D:/relief_story_config/runninghub_request.local.json" --dry-run --pretty
```

Expected: `ready=true`, redacted `apiKey`, correct `workflowId`, and every
mapped node field visible in `nodeInfoList`.

## Task 3: Live RunningHub Submit And Poll

Status: planned, blocked on `RUNNINGHUB_API_KEY` and a real mapped workflow.

- [ ] **Step 1: Set key in process environment**

```powershell
$env:RUNNINGHUB_API_KEY = "<user supplied RunningHub key>"
```

- [ ] **Step 2: Submit one real cloud task**

```powershell
relief-story-agent runninghub-submit `
  --request "D:/relief_story_config/runninghub_request.local.json" `
  --pretty
```

Expected: `status=submitted`, `task_id` is non-empty, and response contains no
plaintext API key.

- [ ] **Step 3: Poll task status**

```powershell
relief-story-agent runninghub-status --task-id "{task_id}" --pretty
```

Expected: `remote_status` progresses through documented RunningHub states such
as `CREATED`, `QUEUED`, `RUNNING`, `SUCCESS`, or `FAILED`.

- [ ] **Step 4: Fetch outputs**

```powershell
relief-story-agent runninghub-outputs --task-id "{task_id}" --pretty
```

Expected: output items include one or more file URLs. If the remote task fails,
record the exact non-secret response shape and add a regression test before
adjusting parser logic.

## Task 4: UI Design And Integration

Status: planned.

- [ ] **Step 1: Add a generation mode selector**

Use a segmented control with two modes:

```text
Local ComfyUI
RunningHub Cloud
```

The first screen should be the usable operations interface, not a landing page.

- [ ] **Step 2: Build RunningHub form**

Fields:

```text
workflowId
api_key_env, default RUNNINGHUB_API_KEY
nodeInfoList rows: node id, field name, field value, description
webhookUrl
usePersonalQueue
instanceType
```

Controls:

```text
Check
Dry Run
Submit
Poll Status
Fetch Outputs
```

- [ ] **Step 3: Wire UI to backend only**

The frontend should call local endpoints:

```text
/api/runninghub/check
/api/runninghub/submit
/api/runninghub/status
/api/runninghub/outputs
```

It should not call RunningHub directly from the browser and should not persist
plaintext keys.

- [ ] **Step 4: Add UI tests after UI code exists**

Use Playwright or the repo's chosen UI test stack. Verify:

```text
missing key shows setup blocker
dry-run payload redacts key
submit button is disabled until workflow id and node mapping exist
task id can be pasted and polled
output URLs render without overlapping layout
```

## Task 5: Cloud Output Import

Status: future work, not required for the first RunningHub backend entry.

- [ ] **Step 1: Decide artifact ownership**

Choose whether RunningHub output URLs stay as remote artifacts or are downloaded
into `D:/relief_story_runs` and then exported through the existing artifact
system.

- [ ] **Step 2: If downloading, add container validation**

Reuse the current video signature checks from local acceptance/export. Do not
count a URL as a local video until a downloaded file exists, is non-empty, and
has a recognized container signature.

- [ ] **Step 3: Add acceptance gate for cloud mode**

Add a separate `runninghub_cloud_generation` evidence row. Do not let it satisfy
local ComfyUI `single_run`, `batch_run`, or `comfyui_outputs` gates unless the
cloud output has been imported and validated as a local artifact.

## Current Completion Definition

Mode 2 starter is complete when:

- RunningHub tests pass.
- CLI help lists `runninghub-*` commands.
- Bootstrap exposes `/api/runninghub/*` endpoints.
- Example JSON contains no secret values.
- Full repo tests pass.
- Handoff docs clearly state that real RunningHub submit is still blocked on a
  real API key, workflow id, and node mapping.

Mode 2 production readiness requires an additional real cloud run with a real
task id, status polling, output URLs, and a documented import/export decision.
