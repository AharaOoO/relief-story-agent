# Execution Reliability Policy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persist structured failure records and make automatic recovery decisions use conservative retryability instead of string-only failed-stage guessing.

**Architecture:** Add a focused `failure_policy.py` classifier and `FailureRecord` model. The orchestrator records structured failures at terminal failure time, while artifact and recovery layers prefer `last_failure.retryable` and fall back to legacy inference only for old runs.

**Tech Stack:** Python 3.11+, Pydantic, pytest, FastAPI

---

## File Structure

- Create `relief_story_agent/failure_policy.py`: maps exceptions and stages to `FailureRecord` values.
- Modify `relief_story_agent/models.py`: add `FailureRecord`, `failure_records`, and `last_failure`.
- Modify `relief_story_agent/orchestrator.py`: record structured failure data in `_finish_failed`.
- Modify `relief_story_agent/artifacts.py`: expose failure data and use it for retryability and recommended action.
- Modify `relief_story_agent/recovery.py`: surface structured failure metadata in recovery plans.
- Modify `relief_story_agent/README.md`: document conservative recovery semantics.
- Add or modify tests in `tests/test_failure_policy.py`, `tests/test_orchestrator.py`, `tests/test_artifacts.py`, and `tests/test_recovery_plan.py`.

### Task 1: Add FailureRecord and Classifier

**Files:**
- Create: `relief_story_agent/failure_policy.py`
- Modify: `relief_story_agent/models.py`
- Test: `relief_story_agent/tests/test_failure_policy.py`

- [ ] **Step 1: Write failing classifier tests**

Create `tests/test_failure_policy.py` with tests like:

```python
import json

import httpx
import pytest

from relief_story_agent.failure_policy import classify_failure


def test_classifier_marks_timeout_as_retryable():
    record = classify_failure(
        "gpt_prompt_writer",
        httpx.TimeoutException("read timeout"),
    )

    assert record.stage == "gpt_prompt_writer"
    assert record.category == "timeout"
    assert record.code == "timeout"
    assert record.retryable is True
    assert record.exception_type == "TimeoutException"


def test_classifier_marks_rate_limit_as_retryable_throttling():
    request = httpx.Request("POST", "http://model.local/v1/chat/completions")
    exc = httpx.HTTPStatusError(
        "rate limited",
        request=request,
        response=httpx.Response(429, request=request),
    )

    record = classify_failure("chief_screenwriter", exc)

    assert record.category == "throttled"
    assert record.code == "http_429"
    assert record.http_status == 429
    assert record.retryable is True


def test_classifier_keeps_unknown_errors_manual_by_default():
    record = classify_failure("deepseek_polish", RuntimeError("surprising failure"))

    assert record.category == "unknown"
    assert record.retryable is False
    assert record.code == "unknown_error"


def test_classifier_marks_quality_gate_as_validation():
    record = classify_failure(
        "quality_gate",
        ValueError("deepseek_polish quality gate failed: ['too intense']"),
    )

    assert record.category == "validation"
    assert record.retryable is False
    assert record.code == "quality_gate_failed"


def test_classifier_marks_json_decode_as_non_retryable_contract_response():
    exc = json.JSONDecodeError("bad json", "not-json", 0)

    record = classify_failure("gpt_prompt_audit", exc)

    assert record.category == "contract"
    assert record.code == "malformed_json"
    assert record.retryable is False
```

- [ ] **Step 2: Verify RED**

Run:

```powershell
python -m pytest tests/test_failure_policy.py -q
```

Expected: FAIL because `relief_story_agent.failure_policy` does not exist.

- [ ] **Step 3: Add the model**

In `models.py`, add:

```python
class FailureRecord(BaseModel):
    stage: str
    category: Literal[
        "transient",
        "throttled",
        "timeout",
        "configuration",
        "validation",
        "contract",
        "external",
        "cancelled",
        "unknown",
    ] = "unknown"
    code: str = "unknown_error"
    retryable: bool = False
    source: str = ""
    message: str = ""
    exception_type: str = ""
    http_status: int | None = None
    attempt_number: int | None = None
    details: dict[str, Any] = Field(default_factory=dict)
    recorded_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
```

- [ ] **Step 4: Add minimal classifier**

Implement `classify_failure(stage: str, exc: Exception) -> FailureRecord` in `failure_policy.py`. Use helper functions for `http_status`, message normalization, and category decisions. Keep unknown errors non-retryable.

- [ ] **Step 5: Verify GREEN**

Run:

```powershell
python -m pytest tests/test_failure_policy.py -q
```

Expected: all classifier tests pass.

### Task 2: Persist Structured Failures on RunState

**Files:**
- Modify: `relief_story_agent/models.py`
- Modify: `relief_story_agent/orchestrator.py`
- Test: `relief_story_agent/tests/test_orchestrator.py`

- [ ] **Step 1: Write failing persistence test**

Add to `tests/test_orchestrator.py`:

```python
def test_failed_run_records_structured_failure_for_unknown_error():
    provider = FakeModelProvider.minimal_success()
    provider.responses.pop("deepseek_polish")
    store = InMemoryRunStore()
    orchestrator = StoryRunOrchestrator(provider=provider, store=store)

    run = orchestrator.create_run(RunRequest(idea="unknown failure", approval_mode="auto"))
    saved = store.get(run.run_id)

    assert saved.status == "failed"
    assert saved.failed_stage == "deepseek_polish"
    assert saved.last_failure is not None
    assert saved.last_failure.stage == "deepseek_polish"
    assert saved.last_failure.category == "unknown"
    assert saved.last_failure.retryable is False
    assert saved.failure_records[-1] == saved.last_failure
```

- [ ] **Step 2: Verify RED**

Run:

```powershell
python -m pytest tests/test_orchestrator.py::test_failed_run_records_structured_failure_for_unknown_error -q
```

Expected: FAIL because `RunState.last_failure` and `failure_records` do not exist.

- [ ] **Step 3: Add RunState fields**

In `RunState`, add:

```python
failure_records: list[FailureRecord] = Field(default_factory=list)
last_failure: FailureRecord | None = None
```

- [ ] **Step 4: Record failure in orchestrator**

In `orchestrator.py`, import `classify_failure`. In `_finish_failed`, after `failed_stage` is known, classify `exc`, append it to `run.failure_records`, assign `run.last_failure`, and keep existing `run.error` behavior.

- [ ] **Step 5: Verify GREEN**

Run:

```powershell
python -m pytest tests/test_orchestrator.py::test_failed_run_records_structured_failure_for_unknown_error -q
```

Expected: test passes.

### Task 3: Make Recovery Recommendations Use Structured Retryability

**Files:**
- Modify: `relief_story_agent/artifacts.py`
- Test: `relief_story_agent/tests/test_artifacts.py`

- [ ] **Step 1: Write failing artifact recommendation tests**

Add two tests:

```python
def test_batch_artifact_index_does_not_auto_retry_unknown_structured_failure(tmp_path):
    run = RunState(
        run_id="run_unknown_failure",
        request=RunRequest(idea="unknown", output_root=str(tmp_path)),
        status="failed",
        current_stage="failed",
        failed_stage="deepseek_polish",
        error="surprising failure",
        last_failure=FailureRecord(
            stage="deepseek_polish",
            category="unknown",
            code="unknown_error",
            retryable=False,
            message="surprising failure",
        ),
    )
    batch = BatchRunState(
        batch_id="batch_unknown",
        items=[BatchRunItem(index=0, run_id=run.run_id, idea="unknown", status="failed", current_stage="failed")],
    )

    index = read_batch_artifact_index(batch, [run])
    item = index["items"][0]

    assert item["retryable"] is False
    assert item["recommended_action"]["code"] == "manual_review"
    assert item["last_failure"]["category"] == "unknown"


def test_batch_artifact_index_retries_structured_timeout(tmp_path):
    run = RunState(
        run_id="run_timeout_failure",
        request=RunRequest(idea="timeout", output_root=str(tmp_path)),
        status="failed",
        current_stage="failed",
        failed_stage="gpt_prompt_writer",
        error="read timeout",
        last_failure=FailureRecord(
            stage="gpt_prompt_writer",
            category="timeout",
            code="timeout",
            retryable=True,
            message="read timeout",
        ),
    )
    batch = BatchRunState(
        batch_id="batch_timeout",
        items=[BatchRunItem(index=0, run_id=run.run_id, idea="timeout", status="failed", current_stage="failed")],
    )

    index = read_batch_artifact_index(batch, [run])
    item = index["items"][0]

    assert item["retryable"] is True
    assert item["retry_from_stage"] == "gpt_prompt_writer"
    assert item["recommended_action"]["code"] == "retry_from_stage"
```

- [ ] **Step 2: Verify RED**

Run:

```powershell
python -m pytest tests/test_artifacts.py -k "structured_failure" -q
```

Expected: FAIL because artifact index ignores structured failure data.

- [ ] **Step 3: Prefer structured retryability**

Update `_is_retryable_run` so `run.last_failure` wins:

```python
if run.last_failure is not None:
    return run.status == "failed" and run.last_failure.retryable and bool(retry_from_stage)
return run.status == "failed" and bool(retry_from_stage)
```

Include `last_failure` and `failure_records` in run artifact index items and manifests.

- [ ] **Step 4: Adjust recommended actions**

In `_recommended_action_for_run`, if `run.last_failure` exists and is not retryable, return manual/config/template/workflow recommendations by category before the generic retryable fallback.

- [ ] **Step 5: Verify GREEN**

Run:

```powershell
python -m pytest tests/test_artifacts.py -k "structured_failure" -q
```

Expected: selected tests pass.

### Task 4: Surface Failure Data in Recovery Plan and README

**Files:**
- Modify: `relief_story_agent/recovery.py`
- Modify: `relief_story_agent/README.md`
- Test: `relief_story_agent/tests/test_recovery_plan.py`

- [ ] **Step 1: Write failing recovery-plan test**

Add:

```python
def test_recovery_plan_exposes_structured_failure_and_holds_unknown(tmp_path):
    run = RunState(
        run_id="run_recovery_unknown",
        request=RunRequest(idea="unknown", output_root=str(tmp_path)),
        status="failed",
        current_stage="failed",
        failed_stage="deepseek_polish",
        last_failure=FailureRecord(
            stage="deepseek_polish",
            category="unknown",
            code="unknown_error",
            retryable=False,
            message="surprising failure",
        ),
    )
    batch = BatchRunState(
        batch_id="batch_recovery_unknown",
        items=[BatchRunItem(index=0, run_id=run.run_id, idea="unknown", status="failed", current_stage="failed")],
    )
    store = InMemoryRunStore()
    store.save(run)
    store.save_batch(batch)
    app = create_app(StoryRunOrchestrator(provider=FakeModelProvider.minimal_success(), store=store))
    client = TestClient(app)

    response = client.get("/api/batches/batch_recovery_unknown/recovery-plan")

    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["safe_to_auto_execute"] is False
    assert item["action_code"] == "manual_review"
    assert item["last_failure"]["category"] == "unknown"
```

- [ ] **Step 2: Verify RED**

Run:

```powershell
python -m pytest tests/test_recovery_plan.py::test_recovery_plan_exposes_structured_failure_and_holds_unknown -q
```

Expected: FAIL because recovery items do not expose `last_failure`.

- [ ] **Step 3: Add recovery data**

Update `_build_recovery_item` to copy `last_failure` and `failure_records` from artifact item data. Keep old fields unchanged.

- [ ] **Step 4: Document behavior**

In `README.md`, add a short section under recovery explaining:

- new runs persist `last_failure`;
- only transient, throttled, and timeout categories auto-retry;
- unknown failures are manual by default;
- old run files use legacy fallback until they fail again under the new system.

- [ ] **Step 5: Verify GREEN**

Run:

```powershell
python -m pytest tests/test_recovery_plan.py::test_recovery_plan_exposes_structured_failure_and_holds_unknown -q
```

Expected: test passes.

### Task 5: Full Verification

**Files:**
- No new production files beyond earlier tasks.

- [ ] **Step 1: Run focused tests**

Run:

```powershell
python -m pytest tests/test_failure_policy.py tests/test_orchestrator.py tests/test_artifacts.py tests/test_recovery_plan.py -q
```

Expected: all selected tests pass.

- [ ] **Step 2: Run full project tests**

Run:

```powershell
python -m pytest tests -q
```

Expected: all project tests pass.

- [ ] **Step 3: Run compile check**

Run:

```powershell
python -m compileall -q .
```

Expected: exit code 0.

- [ ] **Step 4: Report no git commit**

This workspace currently has no usable Git metadata. Do not fabricate a commit. Report changed files and verification results instead.
