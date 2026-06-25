# Thread-Safe Model Rate Limit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make model RPM spacing deterministic and thread-safe across background scheduler workers without serializing unrelated models.

**Architecture:** Keep rate limiting inside the shared `ModelCallExecutor`. Protect the timestamp for each `base_url + model` key with its own lock, and protect lock creation with a short registry lock.

**Tech Stack:** Python 3.11+, `threading`, pytest, Pydantic

---

### Task 1: Add deterministic concurrency regression tests

**Files:**
- Modify: `relief_story_agent/tests/test_model_runtime.py`

- [ ] **Step 1: Add a blocking test clock**

Add a helper that records active calls to `sleep`, exposes an event when sleeping begins, and blocks until the test releases it. Its `monotonic` method returns a protected logical clock, and every completed sleep advances that clock by the requested duration.

- [ ] **Step 2: Test same-key serialization**

Prime the executor with one request at logical time zero. Start the first worker and wait until it enters rate-limit sleep, then start a second worker. Assert before releasing the first worker that only one sleep call is active and, after both finish, that the helper never observed more than one concurrent sleeper.

- [ ] **Step 3: Run the same-key test and verify RED**

Run:

```powershell
python -m pytest relief_story_agent/tests/test_model_runtime.py::test_executor_serializes_rate_limit_waits_for_the_same_model_key -q
```

Expected: FAIL because the current unsynchronized executor allows two concurrent waits for the same key.

- [ ] **Step 4: Test different-key independence**

Prime two configurations that differ by model name. Start one worker per model and assert that both enter their waits before either is released. This prevents replacing the race with one global lock.

### Task 2: Implement per-key rate-limit locking

**Files:**
- Modify: `relief_story_agent/model_runtime.py`

- [ ] **Step 1: Add lock state**

Import `Lock` from `threading`. Initialize a registry lock and a dictionary of per-key locks in `ModelCallExecutor.__init__`.

- [ ] **Step 2: Add a lock lookup helper**

Add `_rate_limit_lock_for(key: str) -> Lock` that uses the registry lock to return one stable lock for each rate-limit key.

- [ ] **Step 3: Protect slot calculation**

In `_apply_rate_limit`, acquire the key lock before reading `_last_request_at`, sleeping, and recording the new timestamp. Keep the unlimited fast path outside the lock.

- [ ] **Step 4: Run focused tests and verify GREEN**

Run:

```powershell
python -m pytest relief_story_agent/tests/test_model_runtime.py -q
```

Expected: all model runtime tests pass.

### Task 3: Document and verify the reliability boundary

**Files:**
- Modify: `relief_story_agent/README.md`

- [ ] **Step 1: Update rate-limit documentation**

State that `base_url + model` spacing is shared safely by all scheduler workers in one process, while multiple server processes require a shared external limiter.

- [ ] **Step 2: Run the complete suite**

Run:

```powershell
python -m pytest -q
python -m compileall -q relief_story_agent
```

Expected: all tests pass and compileall exits with code zero.

- [ ] **Step 3: Review the changed files**

Confirm the implementation preserves pipeline order, does not add burst behavior, and keeps different model keys independent.
