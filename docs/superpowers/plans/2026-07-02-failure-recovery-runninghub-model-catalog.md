# Failure Recovery and RunningHub Model Catalog Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make failed and downstream unfinished stages editable, expose every official domestic/international RunningHub LLM through a polished searchable picker, and fix the 15-300 second quality-gate contract.

**Architecture:** The backend owns a deterministic official model snapshot, validates site-specific models, and applies typed retry overrides only to unfinished stages while preserving successful outputs. The frontend owns a recovery draft derived from the frozen run request and submits only unfinished-stage changes. A reusable accessible `ModelCombobox` renders recommendations and the complete selected-site catalog.

**Tech Stack:** Python 3.11, FastAPI, Pydantic v2, pytest, React 19, TypeScript, TanStack Query, Vitest, Testing Library, Electron.

---

## File Structure

- Modify `relief_story_agent/content.py`: align the writer prompt with 15-300 seconds.
- Modify `relief_story_agent/quality.py`: align local script validation with 15-300 seconds.
- Modify `relief_story_agent/provider_catalog.py`: own complete site catalogs and stage recommendations.
- Modify `relief_story_agent/models.py`: define typed retry configuration overrides.
- Modify `relief_story_agent/orchestrator.py`: validate/apply/audit unfinished-stage recovery changes.
- Modify `relief_story_agent/tests/test_content_rules.py`: duration regression coverage.
- Modify `relief_story_agent/tests/test_provider_catalog.py`: exact catalog and cross-site coverage.
- Modify `relief_story_agent/tests/test_retry_runs.py`: retry override permission matrix and preservation coverage.
- Create `frontend/src/features/autopilot/ModelCombobox.tsx`: searchable grouped listbox.
- Create `frontend/src/features/autopilot/ModelCombobox.test.tsx`: interaction and accessibility tests.
- Create `frontend/src/features/autopilot/recoveryDraft.ts`: recovery state and payload construction.
- Create `frontend/src/features/autopilot/recoveryDraft.test.ts`: all-stage frozen/editable matrix tests.
- Modify `frontend/src/features/autopilot/StageWorkspace.tsx`: consume recovery draft and custom controls.
- Modify `frontend/src/pages/AutopilotPage.tsx`: initialize/discard/submit recovery changes.
- Modify `frontend/src/features/workbench/workbench.api.ts`: provider-catalog and retry payload types.
- Modify `frontend/src/features/run-composer/runRequest.builder.ts`: complete offline fallback catalogs plus recommendations.
- Modify `frontend/src/index.css`: model-picker and recovery-state visual styling.
- Modify `frontend/src/pages/AutopilotPage.test.tsx`: failed-stage editing integration coverage.
- Modify `frontend/src/features/autopilot/StageWorkspace.test.tsx`: complete model/site control coverage.

### Task 1: Finish the Duration Contract Bugfix

**Files:**
- Modify: `relief_story_agent/content.py`
- Modify: `relief_story_agent/quality.py`
- Test: `relief_story_agent/tests/test_content_rules.py`

- [ ] **Step 1: Add failing regression tests**

Add tests that build a 150-second prompt and validate scripts at 150 and 301 seconds:

```python
def test_quality_gate_accepts_supported_duration_above_120_seconds():
    gate = QualityGate()
    script = {
        "duration_seconds": 150,
        "core_sentence": "疲惫的人也可以暂时停下来。",
        "beats": [{"name": name} for name in gate.required_beats],
    }
    assert gate.check_script_object(script).passed


def test_quality_gate_rejects_duration_above_five_minutes():
    gate = QualityGate()
    script = {
        "duration_seconds": 301,
        "core_sentence": "疲惫的人也可以暂时停下来。",
        "beats": [{"name": name} for name in gate.required_beats],
    }
    assert "duration_out_of_range" in gate.check_script_object(script).issues
```

- [ ] **Step 2: Verify the regressions fail for the expected legacy constraints**

Run: `python -m pytest relief_story_agent/tests/test_content_rules.py -q`

Expected: the 150-second script fails and the prompt still contains `60-120 秒`.

- [ ] **Step 3: Apply the minimal contract fix**

Use the current request bounds in `QualityGate.check_script_object`:

```python
duration = int(script.get("duration_seconds") or 0)
if duration and not 15 <= duration <= 300:
    issues.append("duration_out_of_range")
```

Change the writer instruction to `15-300 秒` and explicitly require the target duration.

- [ ] **Step 4: Verify the focused tests pass**

Run: `python -m pytest relief_story_agent/tests/test_content_rules.py -q`

Expected: `8 passed`.

- [ ] **Step 5: Commit the bugfix**

```powershell
git add relief_story_agent/content.py relief_story_agent/quality.py relief_story_agent/tests/test_content_rules.py
git commit -m "fix: honor five minute script duration contract"
```

### Task 2: Replace Curated Restrictions with Complete Site Catalogs

**Files:**
- Modify: `relief_story_agent/provider_catalog.py`
- Modify: `relief_story_agent/tests/test_provider_catalog.py`
- Modify: `relief_story_agent/tests/test_runninghub_llm.py`

- [ ] **Step 1: Add failing catalog tests**

Cover exact counts, representative site-only IDs, all-stage selection, and cross-site rejection:

```python
def test_provider_catalog_exposes_complete_official_snapshots():
    catalog = build_provider_catalog()["runninghub"]
    assert len(catalog["cn"]["models"]) == 20
    assert len(catalog["ai"]["models"]) == 42
    assert "anthropic/claude-sonnet-5" not in catalog["cn"]["models"]
    assert "anthropic/claude-sonnet-5" in catalog["ai"]["models"]


@pytest.mark.parametrize("stage", MODEL_STAGE_IDS)
def test_any_domestic_catalog_model_is_allowed_for_each_model_stage(stage):
    assert validate_runninghub_model(
        site="cn",
        model="minimax/minimax-m2.7",
        stage=stage,
    ) == "minimax/minimax-m2.7"
```

- [ ] **Step 2: Verify the catalog tests fail against the curated lists**

Run: `python -m pytest relief_story_agent/tests/test_provider_catalog.py relief_story_agent/tests/test_runninghub_llm.py -q`

Expected: missing `models`, wrong counts, and stage restriction failures.

- [ ] **Step 3: Implement complete catalogs and recommendations**

Replace `_CURATED_MODELS` with:

```python
RUNNINGHUB_MODELS: dict[RunningHubSite, tuple[str, ...]] = {
    "cn": (
        "glm-5.2", "glm-5.1", "glm-5-turbo", "glm-5",
        "qwen/qwen3.7-max", "glm-5v-turbo", "qwen/qwen3.7-plus",
        "deepseek/deepseek-v4-pro", "qwen/qwen3.6-plus",
        "bytedance/doubao-seed-evolving", "bytedance/doubao-seed-2.1-pro",
        "bytedance/doubao-seed-2.1-turbo", "bytedance/doubao-seed-2.0-pro",
        "bytedance/doubao-seed-2.0-code", "deepseek/deepseek-v4-flash",
        "qwen/qwen3.6-flash", "bytedance/doubao-seed-2.0-lite",
        "bytedance/doubao-seed-2.0-mini", "minimax/minimax-m2.7",
        "qwen/qwen3.6-max-preview",
    ),
    "ai": (
        "google/gemini-3.1-flash-lite-preview", "google/gemini-3.5-flash",
        "openai/gpt-5.5", "openai/gpt-5.5-pro", "openai/gpt-5.4-pro",
        "anthropic/claude-opus-4.8", "anthropic/claude-opus-4.7", "glm-5.2",
        "anthropic/claude-opus-4.6", "openai/gpt-5.4", "openai/gpt-5.3-codex",
        "glm-5.1", "glm-5-turbo", "anthropic/claude-sonnet-4.6", "glm-5",
        "anthropic/claude-sonnet-5", "qwen/qwen3.7-max", "glm-5v-turbo",
        "qwen/qwen3.7-plus", "deepseek/deepseek-v4-pro", "xai/grok-4.3",
        "qwen/qwen3.6-plus", "google/gemini-3.1-pro-preview",
        "bytedance/doubao-seed-evolving", "bytedance/doubao-seed-2.1-pro",
        "anthropic/claude-sonnet-4.5", "bytedance/doubao-seed-2.1-turbo",
        "anthropic/claude-opus-4.5", "bytedance/doubao-seed-2.0-pro",
        "bytedance/doubao-seed-2.0-code", "deepseek/deepseek-v4-flash",
        "qwen/qwen3.6-flash", "openai/gpt-5.4-mini", "openai/gpt-5.4-nano",
        "google/gemini-3-flash-preview", "google/gemini-2.5-flash",
        "bytedance/doubao-seed-2.0-lite", "bytedance/doubao-seed-2.0-mini",
        "minimax/minimax-m2.7", "anthropic/claude-haiku-4.5",
        "qwen/qwen3.6-max-preview", "google/gemini-2.5-pro",
    ),
}

RUNNINGHUB_RECOMMENDED_MODELS: dict[RunningHubSite, dict[str, tuple[str, ...]]] = {
    "cn": {
        "chief_screenwriter": ("qwen/qwen3.7-plus", "qwen/qwen3.7-max"),
        "deepseek_polish": ("deepseek/deepseek-v4-pro", "deepseek/deepseek-v4-flash"),
        "quality_gate": ("deepseek/deepseek-v4-flash", "deepseek/deepseek-v4-pro"),
        "gpt_prompt_writer": ("qwen/qwen3.7-max", "qwen/qwen3.7-plus"),
        "gpt_prompt_audit": ("deepseek/deepseek-v4-pro", "deepseek/deepseek-v4-flash"),
        "gpt_prompt_reviser": ("qwen/qwen3.7-plus", "qwen/qwen3.7-max"),
    },
    "ai": {
        "chief_screenwriter": ("google/gemini-3.5-flash", "anthropic/claude-sonnet-5"),
        "deepseek_polish": ("deepseek/deepseek-v4-pro", "anthropic/claude-sonnet-5"),
        "quality_gate": ("deepseek/deepseek-v4-flash", "openai/gpt-5.5"),
        "gpt_prompt_writer": ("openai/gpt-5.5", "google/gemini-3.5-flash"),
        "gpt_prompt_audit": ("openai/gpt-5.4-mini", "deepseek/deepseek-v4-pro"),
        "gpt_prompt_reviser": ("openai/gpt-5.4-mini", "openai/gpt-5.5"),
    },
}
```

`validate_runninghub_model()` must validate against `RUNNINGHUB_MODELS[site]`; `stage` only validates that the stage identifier is supported. `build_provider_catalog()` returns `models`, `recommended_by_stage`, `source_url`, and `snapshot_date`.

- [ ] **Step 4: Keep transport tests site-specific**

Update RunningHub provider tests to prove `.cn` uses `https://llm.runninghub.cn/v1` plus `RUNNINGHUB_CN_SHARED_API_KEY`, while `.ai` uses `https://llm.runninghub.ai/v1` plus `RUNNINGHUB_AI_SHARED_API_KEY`.

- [ ] **Step 5: Run focused backend tests**

Run: `python -m pytest relief_story_agent/tests/test_provider_catalog.py relief_story_agent/tests/test_runninghub_llm.py relief_story_agent/tests/test_model_config_registry.py -q`

Expected: all pass.

- [ ] **Step 6: Commit the catalog contract**

```powershell
git add relief_story_agent/provider_catalog.py relief_story_agent/tests/test_provider_catalog.py relief_story_agent/tests/test_runninghub_llm.py
git commit -m "feat: expose complete RunningHub LLM catalogs"
```

### Task 3: Add Typed Unfinished-Stage Retry Overrides

**Files:**
- Modify: `relief_story_agent/models.py`
- Modify: `relief_story_agent/orchestrator.py`
- Modify: `relief_story_agent/tests/test_retry_runs.py`
- Modify: `relief_story_agent/tests/test_api.py`

- [ ] **Step 1: Add failing permission-matrix tests**

Build a failed run at `quality_gate` with completed events for stages 1-2. Assert:

```python
retry = RunRetryRequest(
    from_stage="quality_gate",
    model_config_overrides={
        "quality_gate": StageModelConfig(
            provider_mode="runninghub",
            runninghub_site="cn",
            model="glm-5.2",
        ),
        "gpt_prompt_writer": StageModelConfig(
            provider_mode="runninghub",
            runninghub_site="cn",
            model="qwen/qwen3.7-max",
        ),
    },
    prompt_overrides={"quality_gate": "new gate prompt"},
)
queued = orchestrator.queue_retry(run.run_id, retry)
assert queued.request.model_configs["quality_gate"].model == "glm-5.2"
assert queued.prompt_snapshot["quality_gate"] == "new gate prompt"
assert queued.script == original_script
```

Also assert an override for completed `chief_screenwriter` raises `RetryConfigurationConflict` and does not mutate persisted state.

- [ ] **Step 2: Verify focused retry tests fail**

Run: `python -m pytest relief_story_agent/tests/test_retry_runs.py -q`

Expected: Pydantic rejects the new fields or no override is applied.

- [ ] **Step 3: Define typed override models**

Add to `models.py`:

```python
ModelStageId = Literal[
    "chief_screenwriter",
    "deepseek_polish",
    "quality_gate",
    "gpt_prompt_writer",
    "gpt_prompt_audit",
    "gpt_prompt_reviser",
]

RecoverableStage = Literal[
    "chief_screenwriter",
    "deepseek_polish",
    "quality_gate",
    "gpt_prompt_writer",
    "gpt_prompt_audit",
    "gpt_prompt_reviser",
    "final_prompts",
    "four_grid_asset",
    "artifacts",
    "comfyui",
]


class ComfyUIRetryOverride(BaseModel):
    model_config = ConfigDict(extra="forbid")
    endpoint: str | None = None
    workflow_api_path: str | None = None
    output_timeout_seconds: float | None = Field(default=None, gt=0)


class RunRetryRequest(BaseModel):
    from_stage: RecoverableStage | None = None
    model_config_overrides: dict[ModelStageId, StageModelConfig] = Field(default_factory=dict)
    prompt_overrides: dict[ModelStageId, str] = Field(default_factory=dict)
    grid_image_override: GridImageRetryOverride | None = None
    comfyui_override: ComfyUIRetryOverride | None = None
```

- [ ] **Step 4: Apply overrides atomically before queueing**

Implement `_apply_retry_configuration_overrides(run, retry_request)`:

```python
completed = {
    event.stage
    for event in run.events
    if event.event_type == "stage_completed" and event.stage
}
failed_index = stage_order.index(run.failed_stage)
for stage in overridden_stages:
    if stage in completed or stage_order.index(stage) < failed_index:
        raise RetryConfigurationConflict(
            f"stage {stage} completed successfully and cannot be changed"
        )
```

Validate every RunningHub model with `validate_runninghub_model`, apply model/prompt/G2/ComfyUI values to the run request, append one redacted history revision, and then queue from the actual failed stage.

- [ ] **Step 5: Broaden G2 override permission safely**

Allow `grid_image_override` when `four_grid_asset` is unfinished and does not precede the failed stage. Preserve the existing asset reset logic when stage 8 itself had already attempted work.

- [ ] **Step 6: Add structured API conflict coverage**

Assert `/api/runs/{run_id}/retry` returns the existing `retry_configuration_conflict` response for completed-stage edits and accepts valid downstream edits.

- [ ] **Step 7: Run backend recovery suites**

Run: `python -m pytest relief_story_agent/tests/test_retry_runs.py relief_story_agent/tests/test_api.py relief_story_agent/tests/test_persistent_store.py -q`

Expected: all pass.

- [ ] **Step 8: Commit retry overrides**

```powershell
git add relief_story_agent/models.py relief_story_agent/orchestrator.py relief_story_agent/tests/test_retry_runs.py relief_story_agent/tests/test_api.py
git commit -m "feat: edit unfinished stages before retry"
```

### Task 4: Build the Frontend Recovery Draft and Editing Matrix

**Files:**
- Create: `frontend/src/features/autopilot/recoveryDraft.ts`
- Create: `frontend/src/features/autopilot/recoveryDraft.test.ts`
- Modify: `frontend/src/features/workbench/workbench.api.ts`
- Modify: `frontend/src/pages/AutopilotPage.tsx`
- Modify: `frontend/src/pages/AutopilotPage.test.tsx`

- [ ] **Step 1: Add failing all-stage state tests**

Define and test:

```typescript
expect(stageEditingState('chief_screenwriter', statuses, 'failed', 'quality_gate')).toBe('frozen')
expect(stageEditingState('quality_gate', statuses, 'failed', 'quality_gate')).toBe('editable')
expect(stageEditingState('gpt_prompt_writer', statuses, 'failed', 'quality_gate')).toBe('editable')
expect(stageEditingState('four_grid_asset', statuses, 'failed', 'quality_gate')).toBe('editable')
expect(stageEditingState('comfyui', statuses, 'failed', 'quality_gate')).toBe('editable')
```

Loop over every failed-stage index to prove only earlier completed stages freeze.

- [ ] **Step 2: Verify the matrix tests fail**

Run: `npm test -- --run src/features/autopilot/recoveryDraft.test.ts`

Expected: module or behavior missing.

- [ ] **Step 3: Implement recovery draft helpers**

Export:

```typescript
export type RecoveryDraft = {
  stageModels: Partial<Record<ModelStageId, StageModelDraft>>
  stagePrompts: Partial<Record<ModelStageId, string>>
  gridImage: GridImageRetryOverride
  comfyui: {
    endpoint: string
    workflow_api_path: string
    output_timeout_seconds: number
  }
}

export type StageEditingState = 'frozen' | 'editable' | 'automatic'
export function stageEditingState(
  stageId: string,
  statuses: Record<string, AutopilotStageStatus>,
  runStatus: string,
  failedStage?: string,
): StageEditingState
export function createRecoveryDraft(run: RunDetail): RecoveryDraft
export function buildRecoveryRetryPayload(original: RunDetail, draft: RecoveryDraft, statuses: Record<string, AutopilotStageStatus>): RunRetryPayload
```

The payload includes only changed, unfinished stage settings.

- [ ] **Step 4: Update API types**

Add `model_config_overrides`, `prompt_overrides`, and `comfyui_override` to `RunRetryPayload`; update `ProviderCatalog` to use `models` and `recommended_by_stage`.

- [ ] **Step 5: Integrate the recovery lifecycle**

In `AutopilotPage`:

- initialize local recovery draft when a failed run loads;
- compute editing state per selected stage;
- preserve the draft after API errors;
- add `放弃修改` and `保存未完成工序并从失败处重试` actions;
- invalidate run/timeline/artifacts/render-plan after successful retry.

- [ ] **Step 6: Add integration tests**

Test failure at stages 1, 3, 6, 8, and 10. Assert completed controls are disabled, failed/downstream controls are enabled, payload excludes completed stages, and an API failure retains typed edits.

- [ ] **Step 7: Run frontend recovery tests**

Run: `npm test -- --run src/features/autopilot/recoveryDraft.test.ts src/pages/AutopilotPage.test.tsx`

Expected: all pass.

- [ ] **Step 8: Commit recovery UI state**

```powershell
git add frontend/src/features/autopilot/recoveryDraft.ts frontend/src/features/autopilot/recoveryDraft.test.ts frontend/src/features/workbench/workbench.api.ts frontend/src/pages/AutopilotPage.tsx frontend/src/pages/AutopilotPage.test.tsx
git commit -m "feat: unlock unfinished stages after failure"
```

### Task 5: Add the Custom Complete-Catalog Model Combobox

**Files:**
- Create: `frontend/src/features/autopilot/ModelCombobox.tsx`
- Create: `frontend/src/features/autopilot/ModelCombobox.test.tsx`
- Modify: `frontend/src/features/autopilot/StageWorkspace.tsx`
- Modify: `frontend/src/features/autopilot/StageWorkspace.test.tsx`
- Modify: `frontend/src/features/run-composer/runRequest.builder.ts`
- Modify: `frontend/src/index.css`

- [ ] **Step 1: Add failing component interaction tests**

Test open/close, search, recommendation ordering, provider groups, click selection, disabled state, site isolation, and keyboard controls:

```typescript
await user.click(screen.getByRole('combobox', { name: '本工序模型' }))
await user.type(screen.getByRole('searchbox'), 'sonnet-5')
await user.click(screen.getByRole('option', { name: 'anthropic/claude-sonnet-5' }))
expect(onChange).toHaveBeenCalledWith('anthropic/claude-sonnet-5')
```

- [ ] **Step 2: Verify component tests fail**

Run: `npm test -- --run src/features/autopilot/ModelCombobox.test.tsx`

Expected: module missing.

- [ ] **Step 3: Implement `ModelCombobox`**

Use a button with `role="combobox"`, a search input, `role="listbox"`, grouped `role="option"` rows, outside-click handling, and active-index keyboard navigation. Map `glm-*` to Zhipu/GLM and `qwen/*` to Alibaba/Qwen.

- [ ] **Step 4: Replace native site/model selects**

In `StageWorkspace`:

- use a styled segmented site control for `.cn`/`.ai`;
- read `catalog.runninghub[site].models` with complete static fallback;
- pass `recommended_by_stage[stage]` to the combobox;
- reset the selected model to the target site's first recommendation when switching sites;
- use the same component for setup and recovery editing.

- [ ] **Step 5: Add stage 10 recovery fields**

When `comfyui` is editable, show endpoint, workflow path, and timeout controls plus the existing desktop workflow picker. Keep these fields hidden behind the stage workspace/advanced-settings visual language.

- [ ] **Step 6: Style the custom controls**

Add stable dimensions, glass surfaces, focus-visible rings, selected/error/disabled states, sticky provider labels, bounded popup height, responsive behavior, and no native expanded select for RunningHub site/model selection.

- [ ] **Step 7: Run component and page tests**

Run: `npm test -- --run src/features/autopilot/ModelCombobox.test.tsx src/features/autopilot/StageWorkspace.test.tsx src/pages/AutopilotPage.test.tsx`

Expected: all pass.

- [ ] **Step 8: Commit the model picker**

```powershell
git add frontend/src/features/autopilot/ModelCombobox.tsx frontend/src/features/autopilot/ModelCombobox.test.tsx frontend/src/features/autopilot/StageWorkspace.tsx frontend/src/features/autopilot/StageWorkspace.test.tsx frontend/src/features/run-composer/runRequest.builder.ts frontend/src/index.css
git commit -m "feat: add complete RunningHub model picker"
```

### Task 6: Full Verification and Desktop Deployment

**Files:**
- Verify: entire repository
- Build: `frontend/dist`
- Build: `desktop/electron/sidecar/bin/relief-story-agent-api.exe`
- Package: `desktop/electron/release/win-unpacked`

- [ ] **Step 1: Run the complete backend suite**

Run: `python -m pytest`

Expected: all tests pass with zero failures.

- [ ] **Step 2: Run the complete frontend suite and static checks**

Run separately:

```powershell
npm test -- --run
npm run typecheck
npm run lint
npm run build
```

Expected: all commands exit 0.

- [ ] **Step 3: Run Electron checks**

Run separately in `desktop/electron`:

```powershell
npm run check
npm test
```

Expected: all commands exit 0.

- [ ] **Step 4: Build and package the desktop client**

```powershell
powershell -ExecutionPolicy Bypass -File tools/desktop/Build-Desktop.ps1 -SkipInstaller -SkipDependencyInstall
npm --prefix desktop/electron run pack
```

Expected: sidecar and `win-unpacked/Relief Story Agent.exe` are regenerated.

- [ ] **Step 5: Verify packaged runtime without paid calls**

Launch the packaged client, verify `/api/health`, inspect the provider catalog counts, and confirm the packaged sidecar contains `imageio_ffmpeg`. Do not submit RunningHub or ComfyUI work.

- [ ] **Step 6: Deploy and hash-check the desktop copy**

Copy `win-unpacked` to `C:\Users\dcf\Desktop\Relief Story Agent 最新客户端\win-unpacked`, then compare SHA-256 for the main executable, `app.asar`, frontend index, and sidecar.

- [ ] **Step 7: Confirm the worktree contains no uncommitted source changes**

Run: `git status --short`

Expected: no source or test files are listed. Build outputs may exist only in ignored directories.
