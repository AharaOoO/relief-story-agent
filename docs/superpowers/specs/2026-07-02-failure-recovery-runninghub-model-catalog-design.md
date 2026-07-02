# Failure Recovery and RunningHub Model Catalog Design

## 1. Objective

This change fixes three connected usability failures in the desktop autopilot:

1. The script quality gate must honor the current `15-300` second duration contract instead of the legacy `60-120` second range.
2. A failed run must keep every unfinished stage editable. Only stages that completed successfully are frozen.
3. Each of the first six model stages must expose every LLM currently listed for the selected RunningHub site through a polished searchable model picker.

The work must preserve completed outputs, keep domestic and international credentials isolated, and never silently rerun an earlier completed stage.

## 2. Confirmed Product Decisions

- Model picker direction: **Option A**.
- The picker is a custom glass-style combobox, not a browser-native expanded `<select>`.
- It supports search, keyboard navigation, recommended models at the top, provider grouping, and the full selected-site catalog.
- When a run fails, completed stages remain read-only. The failed stage and every later unfinished configurable stage remain editable.
- Saving recovery changes queues the run from the failed stage. It does not restart from stage 1.
- Domestic and international RunningHub sites never share models, Base URLs, or API keys.

## 3. Root Cause Already Confirmed

Run `run_dc8711c85d94` requested 150 seconds and produced a 150-second script. The model quality audit passed. The local rule failed because `QualityGate.check_script_object()` still enforced `60 <= duration <= 120`.

The built-in chief-screenwriter prompt also still described the product as a 60-120 second generator. Both constraints must use the current 15-300 second contract.

## 4. Stage Editing State Machine

The ten stages remain sequential:

1. `chief_screenwriter`
2. `deepseek_polish`
3. `quality_gate`
4. `gpt_prompt_writer`
5. `gpt_prompt_audit`
6. `gpt_prompt_reviser`
7. `final_prompts`
8. `four_grid_asset`
9. `artifacts`
10. `comfyui`

For a live run, each stage has one of these editing states:

| Execution state | Editing state | UI treatment |
| --- | --- | --- |
| completed/skipped successfully | frozen | lock icon, archived values, controls disabled |
| running | frozen during execution | spinner, controls disabled |
| failed | editable | error treatment, controls enabled, recovery explanation |
| pending after a failed stage | editable when the stage has settings | edit treatment, controls enabled |
| pending during a healthy running task | frozen | waiting treatment |
| automatic stage with no user settings | no editor | diagnostics and retry context only |

The frontend must derive this per stage. It must not pass one global `readOnly` flag to the entire run.

### 4.1 Editable recovery surfaces

- Stages 1-6: provider mode, RunningHub site, model, and prompt template.
- Stage 8: RunningHub G2 site, aspect ratio, and resolution.
- Stage 10: ComfyUI endpoint, workflow path, safe timeout controls, and workflow-model validation through the advanced settings drawer.
- Stages 7 and 9: no artificial editor because they have no user-owned configuration; the UI explains that they will be rebuilt from upstream outputs.

## 5. Retry Override Contract

Extend `RunRetryRequest` with explicit, typed recovery overrides:

```json
{
  "from_stage": "quality_gate",
  "model_stage_overrides": {
    "quality_gate": {
      "provider_mode": "runninghub",
      "runninghub_site": "cn",
      "model": "deepseek/deepseek-v4-flash"
    }
  },
  "prompt_overrides": {
    "quality_gate": "..."
  },
  "grid_image_override": null,
  "comfyui_override": null
}
```

Backend rules:

1. The run must be `failed` or `cancelled` in a recoverable state.
2. `from_stage` remains the actual failed stage unless an existing recovery policy explicitly permits another stage.
3. An override is rejected when its target stage has a successful completion event.
4. An override is rejected when its target stage precedes the failed stage.
5. An override is accepted for the failed stage or a later unfinished stage.
6. Accepted model configuration is revalidated against the selected site's model catalog.
7. Completed outputs and artifacts before the failed stage remain unchanged.
8. Outputs at and after the failed stage are invalidated by the existing retry-tail logic.
9. Every accepted change appends a `retry_configuration_history` record containing timestamp, stage, and redacted before/after values.
10. API keys are never included in retry payloads or audit history.

The existing G2 retry override becomes one member of this general recovery contract instead of a special UI-only exception.

## 6. RunningHub Transport Contract

RunningHub LLM calls remain OpenAI-compatible chat completions:

| Site | Base URL | Credential |
| --- | --- | --- |
| Domestic | `https://llm.runninghub.cn/v1` | `RUNNINGHUB_CN_SHARED_API_KEY` |
| International | `https://llm.runninghub.ai/v1` | `RUNNINGHUB_AI_SHARED_API_KEY` |

The request uses `POST /chat/completions` through the OpenAI-compatible client with:

- `Authorization: Bearer <site enterprise shared key>`
- the exact selected model identifier
- user prompt messages
- configured temperature and timeout

Consumer/member task keys remain separate:

- `RUNNINGHUB_CN_API_KEY` and `RUNNINGHUB_AI_API_KEY` are for G2/model-task APIs.
- They must never be substituted for enterprise shared LLM keys.

## 7. Catalog Data Shape

The backend provider catalog separates complete availability from recommendations:

```json
{
  "runninghub": {
    "cn": {
      "base_url": "https://llm.runninghub.cn/v1",
      "api_key_env": "RUNNINGHUB_CN_SHARED_API_KEY",
      "source_url": "https://www.runninghub.cn/call-api/llm/models",
      "snapshot_date": "2026-07-02",
      "models": ["...all domestic models..."],
      "recommended_by_stage": {"quality_gate": ["deepseek/deepseek-v4-flash"]}
    }
  }
}
```

Runtime page scraping is deliberately excluded. The desktop must start offline and the model list must be deterministic and testable. A release updates the official snapshot when RunningHub changes its catalog.

Validation accepts any model in the chosen site's complete list. Stage recommendations affect sorting only; they do not restrict selection.

## 8. Official Domestic Catalog Snapshot

Source: <https://www.runninghub.cn/call-api/llm/models>

The official page reports 20 models on 2026-07-02:

- `glm-5.2`
- `glm-5.1`
- `glm-5-turbo`
- `glm-5`
- `qwen/qwen3.7-max`
- `glm-5v-turbo`
- `qwen/qwen3.7-plus`
- `deepseek/deepseek-v4-pro`
- `qwen/qwen3.6-plus`
- `bytedance/doubao-seed-evolving`
- `bytedance/doubao-seed-2.1-pro`
- `bytedance/doubao-seed-2.1-turbo`
- `bytedance/doubao-seed-2.0-pro`
- `bytedance/doubao-seed-2.0-code`
- `deepseek/deepseek-v4-flash`
- `qwen/qwen3.6-flash`
- `bytedance/doubao-seed-2.0-lite`
- `bytedance/doubao-seed-2.0-mini`
- `minimax/minimax-m2.7`
- `qwen/qwen3.6-max-preview`

## 9. Official International Catalog Snapshot

Source: <https://www.runninghub.ai/call-api/llm/models>

The official page reports 42 models on 2026-07-02:

- `google/gemini-3.1-flash-lite-preview`
- `google/gemini-3.5-flash`
- `openai/gpt-5.5`
- `openai/gpt-5.5-pro`
- `openai/gpt-5.4-pro`
- `anthropic/claude-opus-4.8`
- `anthropic/claude-opus-4.7`
- `glm-5.2`
- `anthropic/claude-opus-4.6`
- `openai/gpt-5.4`
- `openai/gpt-5.3-codex`
- `glm-5.1`
- `glm-5-turbo`
- `anthropic/claude-sonnet-4.6`
- `glm-5`
- `anthropic/claude-sonnet-5`
- `qwen/qwen3.7-max`
- `glm-5v-turbo`
- `qwen/qwen3.7-plus`
- `deepseek/deepseek-v4-pro`
- `xai/grok-4.3`
- `qwen/qwen3.6-plus`
- `google/gemini-3.1-pro-preview`
- `bytedance/doubao-seed-evolving`
- `bytedance/doubao-seed-2.1-pro`
- `anthropic/claude-sonnet-4.5`
- `bytedance/doubao-seed-2.1-turbo`
- `anthropic/claude-opus-4.5`
- `bytedance/doubao-seed-2.0-pro`
- `bytedance/doubao-seed-2.0-code`
- `deepseek/deepseek-v4-flash`
- `qwen/qwen3.6-flash`
- `openai/gpt-5.4-mini`
- `openai/gpt-5.4-nano`
- `google/gemini-3-flash-preview`
- `google/gemini-2.5-flash`
- `bytedance/doubao-seed-2.0-lite`
- `bytedance/doubao-seed-2.0-mini`
- `minimax/minimax-m2.7`
- `anthropic/claude-haiku-4.5`
- `qwen/qwen3.6-max-preview`
- `google/gemini-2.5-pro`

## 10. Model Picker UI

Create a reusable `ModelCombobox` instead of expanding a native select.

### 10.1 Visual behavior

- Closed state matches the existing pale glass input shell, border, shadow, radius, type scale, and focus ring.
- The site control uses the same custom segmented-pill language as the rest of the autopilot.
- The popup uses a restrained glass panel with an opaque enough surface for legibility.
- No nested decorative cards.
- Provider group labels are compact and sticky while scrolling.
- The selected model has a check icon and tinted row.

### 10.2 Interaction behavior

- Search by complete ID, provider, or model suffix.
- Recommended models appear first under `本工序推荐`.
- All models then appear grouped as Alibaba/Qwen, Anthropic, ByteDance, DeepSeek, Google, MiniMax, OpenAI, xAI, and Zhipu/GLM.
- `ArrowUp`, `ArrowDown`, `Enter`, `Escape`, `Home`, and `End` work.
- Clicking outside closes the popup.
- Switching site immediately selects the stage's default recommendation for that site.
- A model from the previous site is never retained invisibly.
- Loading and empty-search states are visible.

## 11. Frontend Recovery Flow

When a run fails:

1. Focus the failed stage, but allow the user to inspect every stage.
2. Build a recovery draft from the frozen run request and prompt snapshot.
3. Mark completed stages read-only.
4. Enable editors for the failed and later unfinished configurable stages.
5. Track dirty changes without altering archived run data immediately.
6. Show `放弃修改` and `保存未完成工序并从失败处重试` actions.
7. Submit only changed recovery fields.
8. Keep buttons busy and show precise progress/error feedback.
9. After success, invalidate run, timeline, artifacts, and render-plan queries.

## 12. Error Handling

- Wrong-site models return a structured 422/409 error naming the site and model.
- Attempting to modify a completed stage returns `retry_configuration_conflict`.
- Missing enterprise shared keys retain the existing explicit key-type explanation.
- Catalog load failure falls back to the built-in snapshot already shipped in the backend; the UI never becomes an empty native select.
- Retry submission failure preserves the local recovery draft so the user can correct it.
- The quality-gate error message should distinguish local rules from model rejection.

## 13. Testing and Acceptance

### Backend

- 150-second scripts pass the local duration rule; 301-second scripts fail.
- Built-in writer prompt no longer claims a 60-120 second product limit.
- Domestic catalog contains exactly the 20 listed domestic models.
- International catalog contains exactly the 42 listed international models.
- No international-only model appears in the domestic catalog.
- Every catalog model is accepted for every one of the first six stages on its own site.
- Cross-site selection is rejected.
- Domestic and international transports use their own Base URL and shared-key environment variable.
- Recovery overrides accept failed/later unfinished stages and reject completed/earlier stages.
- Audit history contains redacted before/after configuration.
- Previous completed artifacts survive retry preparation.

### Frontend

- Failure at each of the ten stages produces the correct editable/frozen matrix.
- Stages 1-6 use the custom combobox and complete site catalog.
- Search, grouping, recommendations, keyboard behavior, and site switching are tested.
- Failed-stage edits remain present after a retry API error.
- G2 and ComfyUI recovery controls appear only when those stages are unfinished.
- No native expanded model select remains in the autopilot stage workspace.

### Release

- Full Python, frontend, and Electron suites pass.
- Production frontend build and `win-unpacked` packaging pass.
- Packaged sidecar responds to `/api/health`.
- No paid RunningHub or real ComfyUI submission is made during automated verification.

## 14. Out of Scope

- Automatic scraping of RunningHub webpages at desktop startup.
- Storing API keys inside run JSON or retry audit data.
- Reopening or mutating a successfully completed stage in the same run.
- Changing the G2 task API or ComfyUI segmented rendering architecture beyond recovery configuration support.
