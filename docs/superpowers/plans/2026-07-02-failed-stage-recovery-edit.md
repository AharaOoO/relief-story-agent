# Failed Stage Recovery Editing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a failed four-grid stage change its G2 site, aspect ratio, and resolution before retrying without rerunning or mutating completed upstream stages.

**Architecture:** Extend the typed retry request with a narrow `GridImageRetryOverride`, apply it atomically while queueing the failed stage, clear only G2/downstream checkpoint state, and append a non-secret audit revision. The live React page owns a recovery draft cloned from the frozen run request and enables stage 8 only when it is the actual failed stage.

**Tech Stack:** Python 3.12, Pydantic, FastAPI, React 19, TypeScript, TanStack Query, Vitest, pytest

---

### Task 1: Add and validate the retry override contract

**Files:**
- Modify: `relief_story_agent/models.py`
- Modify: `relief_story_agent/tests/test_retry_runs.py`

- [x] **Step 1: Write the failing model test**

```python
def test_retry_request_accepts_only_public_grid_image_override_fields():
    request = RunRetryRequest.model_validate({
        "from_stage": "four_grid_asset",
        "grid_image_override": {
            "runninghub_site": "cn",
            "aspect_ratio": "9:16",
            "resolution": "2k",
        },
    })
    assert request.grid_image_override.runninghub_site == "cn"
    assert "api_key" not in request.grid_image_override.model_dump()
```

- [x] **Step 2: Run the focused test and verify failure**

Run: `python -m pytest relief_story_agent/tests/test_retry_runs.py -q`

- [x] **Step 3: Add the narrow Pydantic model**

```python
class GridImageRetryOverride(BaseModel):
    runninghub_site: Literal["cn", "ai"]
    aspect_ratio: Literal["16:9", "9:16"]
    resolution: Literal["1k", "2k"]

class RunRetryRequest(BaseModel):
    from_stage: ...
    grid_image_override: GridImageRetryOverride | None = None
```

- [x] **Step 4: Run the focused test and verify pass**

Run the same pytest command and expect all tests in the file to pass.

### Task 2: Apply overrides safely while preserving upstream work

**Files:**
- Modify: `relief_story_agent/models.py`
- Modify: `relief_story_agent/orchestrator.py`
- Modify: `relief_story_agent/api.py`
- Modify: `relief_story_agent/tests/test_retry_runs.py`
- Modify: `relief_story_agent/tests/test_orchestrator.py`

- [x] **Step 1: Write failing orchestrator tests**

Create a failed `four_grid_asset` run with an existing image checkpoint, then assert that `queue_retry(..., RunRetryRequest(grid_image_override=...))`:

```python
assert queued.request.comfyui.grid_image.runninghub_site == "cn"
assert queued.request.comfyui.grid_image.aspect_ratio == "9:16"
assert queued.grid_image_asset is None
assert queued.grid_image_attempts == []
assert queued.grid_image_checkpoint == ""
assert queued.grid_image_replacements == []
assert queued.script == original_script
assert queued.retry_configuration_history[-1]["after"]["runninghub_site"] == "cn"
```

Also assert that an override is rejected when the run is not failed, the failed stage is different, or `from_stage` is not `four_grid_asset`.

- [x] **Step 2: Run focused tests and verify failure**

Run: `python -m pytest relief_story_agent/tests/test_retry_runs.py relief_story_agent/tests/test_orchestrator.py -q`

- [x] **Step 3: Implement atomic override application**

Add `_apply_grid_image_retry_override(run, retry_request)` and invoke it before changing run status in both `retry()` and `queue_retry()`. Copy the existing `GridImageConfig` with `model_copy(update=...)`, clear G2 checkpoint fields, append `retry_configuration_history`, and emit `retry_configuration_updated` with public configuration only.

- [x] **Step 4: Map state conflicts to HTTP 409**

Catch a dedicated `RetryConfigurationConflict` in the retry route and return a structured 409 response with code `retry_configuration_conflict`.

- [x] **Step 5: Run focused and API tests**

Run: `python -m pytest relief_story_agent/tests/test_retry_runs.py relief_story_agent/tests/test_orchestrator.py relief_story_agent/tests/test_api.py -q`

### Task 3: Add failed-stage recovery editing to the live UI

**Files:**
- Modify: `frontend/src/features/workbench/workbench.api.ts`
- Modify: `frontend/src/features/autopilot/StageWorkspace.tsx`
- Modify: `frontend/src/pages/AutopilotPage.tsx`
- Modify: `frontend/src/pages/AutopilotPage.test.tsx`
- Modify: `frontend/src/features/autopilot/StageWorkspace.test.tsx`
- Modify: `frontend/src/index.css`

- [x] **Step 1: Write failing frontend tests**

Assert that a run with `status: 'failed'` and `failed_stage: 'four_grid_asset'` enables the G2 controls, changing `.ai` to `.cn` does not change the frozen request object, and clicking `应用修改并重试本工序` calls:

```ts
retryRun(runId, {
  from_stage: 'four_grid_asset',
  grid_image_override: {
    runninghub_site: 'cn',
    aspect_ratio: '16:9',
    resolution: '2k',
  },
})
```

Assert that `按原配置重试` sends only `{ from_stage: 'four_grid_asset' }`, and non-failed stages remain disabled.

- [x] **Step 2: Run focused Vitest tests and verify failure**

Run: `npm test -- --run src/pages/AutopilotPage.test.tsx src/features/autopilot/StageWorkspace.test.tsx`

- [x] **Step 3: Update the API client contract**

Change `retryRun` to accept a typed payload object instead of a bare stage string and serialize it unchanged to the retry endpoint.

- [x] **Step 4: Implement the isolated recovery draft**

In `AutopilotPage`, clone `run.request.comfyui.grid_image` into local recovery state when a failed four-grid run loads. Pass values and `onChange` to `StageWorkspace`; enable controls only when the selected stage equals `run.failed_stage`.

- [x] **Step 5: Implement explicit recovery actions**

Render `应用修改并重试本工序` as the primary action and `按原配置重试` as secondary. Keep completed stages read-only and provide pending/success/error feedback through the existing mutation status region.

- [x] **Step 6: Run focused tests and verify pass**

Run the same Vitest command and expect all tests to pass.

### Task 4: Full verification and desktop deployment

**Files:**
- Build output: `frontend/dist`
- Build output: `desktop/electron/release/win-unpacked`

- [x] **Step 1: Run backend verification**

Run: `python -m pytest relief_story_agent/tests -q`

- [x] **Step 2: Run frontend verification**

Run: `npm run typecheck && npm run lint && npm test && npm run build`

- [x] **Step 3: Run Electron verification and package**

Run: `npm run check && npm test && npm run pack`

- [x] **Step 4: Deploy and smoke-test**

Close only processes launched from the named desktop test directory, replace `win-unpacked`, compare `app.asar` and sidecar SHA-256 hashes, launch the client, verify `/api/health`, and confirm the failed stage exposes both recovery actions without exposing secrets.
