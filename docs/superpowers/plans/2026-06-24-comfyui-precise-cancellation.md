# ComfyUI Precise Cancellation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make ComfyUI waits promptly cancellable and safely cancel only prompt IDs owned by the run.

**Architecture:** Add an interruptible polling signal and a job-level cancellation adapter in `comfyui.py`. Persist structured cancellation results through `RunState`, the orchestrator, and artifacts while preserving the existing pipeline order.

**Tech Stack:** Python 3.11+, httpx, Pydantic, pytest, FastAPI

---

### Task 1: Specify precise remote cancellation

**Files:**
- Modify: `relief_story_agent/tests/test_comfyui_outputs.py`
- Modify: `relief_story_agent/comfyui.py`
- Modify: `relief_story_agent/models.py`

- [ ] **Step 1: Write failing tests for the modern endpoint**

Test `cancel_prompt_jobs` with a mock transport and assert it posts to `/api/jobs/prompt_1/cancel`, returns a structured `job_api` result, and never calls `/interrupt`.

- [ ] **Step 2: Verify RED**

Run:

```powershell
python -m pytest relief_story_agent/tests/test_comfyui_outputs.py::test_cancel_prompt_jobs_uses_exact_modern_job_endpoint -q
```

Expected: collection or import failure because `cancel_prompt_jobs` does not exist.

- [ ] **Step 3: Add the cancellation result model**

Create `ComfyUICancellation` in `models.py` with `prompt_id`, `strategy`, `cancelled`, `remote_status`, `error`, and `checked_at`.

- [ ] **Step 4: Implement the modern request**

Implement `cancel_prompt_jobs` in `comfyui.py`. Treat any `2xx` response as a completed request and read the optional JSON `cancelled` boolean.

- [ ] **Step 5: Add and implement legacy fallback tests**

For modern `404` and `405`, assert one `POST /queue` request with `{"delete": ["prompt_1"]}`. For `500`, assert no fallback request.

- [ ] **Step 6: Run focused cancellation adapter tests**

Run:

```powershell
python -m pytest relief_story_agent/tests/test_comfyui_outputs.py -k "cancel_prompt_jobs" -q
```

Expected: all selected tests pass.

### Task 2: Make output polling interruptible

**Files:**
- Modify: `relief_story_agent/tests/test_comfyui_outputs.py`
- Modify: `relief_story_agent/comfyui.py`

- [ ] **Step 1: Write the callback cancellation test**

Pass a callback that returns `False` once and `True` on its next check. Assert `wait_for_prompt_outputs` raises `ComfyUIWaitCancelled` before a second history request.

- [ ] **Step 2: Verify RED**

Run:

```powershell
python -m pytest relief_story_agent/tests/test_comfyui_outputs.py::test_wait_for_prompt_outputs_stops_when_cancellation_is_requested -q
```

Expected: FAIL because the polling function has no cancellation callback.

- [ ] **Step 3: Implement cancellable polling**

Add `should_cancel` and `cancel_check_interval_seconds` keyword arguments. Check cancellation before collection and divide waits into slices no longer than one second.

- [ ] **Step 4: Verify polling tests**

Run:

```powershell
python -m pytest relief_story_agent/tests/test_comfyui_outputs.py -k "wait_for_prompt_outputs" -q
```

Expected: all selected tests pass.

### Task 3: Integrate cancellation with run execution

**Files:**
- Modify: `relief_story_agent/tests/test_scheduler.py`
- Modify: `relief_story_agent/orchestrator.py`
- Modify: `relief_story_agent/models.py`

- [ ] **Step 1: Write the scheduler-level failing test**

Run a real scheduler with a ComfyUI mock whose history remains empty. Request cancellation after `/prompt` is accepted. Assert the run becomes `cancelled`, retains its prompt ID, and records a `job_api` cancellation result.

- [ ] **Step 2: Verify RED**

Run:

```powershell
python -m pytest relief_story_agent/tests/test_scheduler.py::test_cancel_running_comfyui_wait_cancels_exact_remote_jobs -q
```

Expected: FAIL because the current worker remains in the ComfyUI wait.

- [ ] **Step 3: Wire the callback and adapter**

In `_run_comfyui`, pass a callback that reads the latest persisted `cancel_requested` value. Catch `ComfyUIWaitCancelled`, call `cancel_prompt_jobs`, persist the results, then raise `RunCancellationRequested`.

- [ ] **Step 4: Verify the scheduler test**

Run the new scheduler test and confirm it passes without any `/interrupt` request.

### Task 4: Persist the audit and document behavior

**Files:**
- Modify: `relief_story_agent/artifacts.py`
- Modify: `relief_story_agent/tests/test_artifacts.py`
- Modify: `relief_story_agent/README.md`

- [ ] **Step 1: Write the artifact failing assertion**

Create a run containing one `ComfyUICancellation`, write artifacts, and assert both the manifest and artifact index expose `comfyui_cancellations`.

- [ ] **Step 2: Implement artifact serialization**

Add `comfyui_cancellations` beside the existing prompt IDs, outputs, and diagnostics fields.

- [ ] **Step 3: Document cancellation compatibility**

Describe modern job-level cancellation, legacy pending deletion, local cancellation despite remote errors, and the explicit ban on automatic global `/interrupt`.

- [ ] **Step 4: Run project verification**

Run:

```powershell
python -m pytest relief_story_agent/tests/test_comfyui_outputs.py relief_story_agent/tests/test_scheduler.py relief_story_agent/tests/test_artifacts.py -q
python -m pytest relief_story_agent/tests -q
python -m compileall -q relief_story_agent
```

Expected: all Agent tests pass and compileall exits with code zero.
