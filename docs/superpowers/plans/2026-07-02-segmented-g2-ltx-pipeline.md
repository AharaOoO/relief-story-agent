# Segmented G2 and LTX Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the single 90-second G2/LTX submission with a 0-5 minute, per-segment pipeline that creates one G2 four-panel image and one sequential ComfyUI render per storyboard segment, exposes exact execution parameters, and assembles completed clips.

**Architecture:** Introduce persisted `SegmentRenderState` objects planned from finalized storyboard ranges. Stage 8 generates and uploads images segment by segment; stage 10 validates workflow models, persists exact API prompts, submits and monitors one ComfyUI job at a time, then invokes an FFmpeg-backed assembler. The frontend consumes segment state directly and presents a compact execution manifest with segment details and recovery actions.

**Tech Stack:** Python 3.12, Pydantic 2, FastAPI, httpx, imageio-ffmpeg, pytest, React 19, TypeScript, TanStack Query, Vitest, Electron, PyInstaller

---

## File Structure

**Create:**

- `relief_story_agent/segment_render.py` - duration parsing, retiming, local frame indices, segment prompt compilation, render-state planning.
- `relief_story_agent/workflow_models.py` - workflow fingerprinting and loader model availability manifest.
- `relief_story_agent/video_assembly.py` - ordered FFmpeg concat and normalized fallback.
- `relief_story_agent/tests/test_segment_render.py` - planner and duration tests.
- `relief_story_agent/tests/test_segment_pipeline.py` - per-segment G2 and sequential ComfyUI orchestration tests.
- `relief_story_agent/tests/test_workflow_models.py` - loader model validation tests.
- `relief_story_agent/tests/test_video_assembly.py` - concat command and failure-preservation tests.
- `frontend/src/features/autopilot/SegmentExecutionPanel.tsx` - stage 8/10 segment overview and detail panel.
- `frontend/src/features/autopilot/SegmentExecutionPanel.test.tsx` - segment visualization and actions.

**Modify:**

- `pyproject.toml` - add `imageio-ffmpeg` runtime dependency.
- `tools/desktop/Build-Desktop.ps1` - collect the bundled FFmpeg binary in the sidecar build.
- `relief_story_agent/models.py` - duration validation, segment state, assembly state, segment retry contracts.
- `relief_story_agent/output_contracts.py` - optional four-panel prompt contract validation.
- `relief_story_agent/prompt_templates.py` - request four within-segment panel prompts from writer/auditor/reviser.
- `relief_story_agent/grid_image.py` - compile one segment-only G2 four-panel prompt.
- `relief_story_agent/ltx_workflow.py` - build one local-timeline LTX payload.
- `relief_story_agent/comfyui.py` - prepare/submit exact segment workflow with provenance metadata.
- `relief_story_agent/orchestrator.py` - persist and execute segment state machine.
- `relief_story_agent/artifacts.py` - segment directory artifacts and execution manifest.
- `relief_story_agent/api.py` - render-plan and segment recovery endpoints.
- `relief_story_agent/config_validation.py` - block unavailable workflow models before paid calls.
- `frontend/src/features/run-composer/runRequest.builder.ts` - 0-auto through 300-second request contract.
- `frontend/src/features/run-composer/RunComposer.tsx` - duration presets and exact minute/second editor.
- `frontend/src/features/run-composer/runDraft.store.ts` - duration migration and persistence.
- `frontend/src/features/workbench/workbench.api.ts` - typed segment and assembly API contracts.
- `frontend/src/pages/AutopilotPage.tsx` - render-plan query, stage 8/10 segment panel, mutations.
- `frontend/src/index.css` - compact execution table/detail styles.

## Task 1: Add 0-5 Minute Duration Contract

**Files:**
- Modify: `relief_story_agent/models.py`
- Test: `relief_story_agent/tests/test_v2_contract.py`
- Modify: `frontend/src/features/run-composer/runRequest.builder.ts`
- Modify: `frontend/src/features/run-composer/runDraft.store.ts`
- Test: `frontend/src/features/run-composer/runRequest.builder.test.ts`
- Test: `frontend/src/features/run-composer/runDraft.store.migration.test.ts`

- [ ] **Step 1: Write failing backend duration tests**

```python
@pytest.mark.parametrize("value", [0, 15, 90, 300])
def test_creation_spec_accepts_supported_duration_values(value):
    assert CreationSpec(duration_seconds=value).duration_seconds == value

@pytest.mark.parametrize("value", [-1, 1, 14, 301])
def test_creation_spec_rejects_unsupported_duration_values(value):
    with pytest.raises(ValidationError):
        CreationSpec(duration_seconds=value)

def test_legacy_run_duration_migrates_into_creation_spec():
    request = RunRequest.model_validate({"duration_seconds": 180})
    assert request.creation_spec.duration_seconds == 180
```

- [ ] **Step 2: Run the backend tests and verify RED**

Run: `python -m pytest relief_story_agent/tests/test_v2_contract.py -q`

Expected: the invalid values are currently accepted.

- [ ] **Step 3: Implement one canonical duration field**

Use this validator and keep `RunRequest.duration_seconds` as a deprecated read-only migration input:

```python
class CreationSpec(BaseModel):
    duration_seconds: int = 90

    @field_validator("duration_seconds")
    @classmethod
    def _validate_duration(cls, value: int) -> int:
        if value == 0 or 15 <= value <= 300:
            return value
        raise ValueError("duration_seconds must be 0 (auto) or between 15 and 300")
```

Ensure all runtime code reads `request.creation_spec.duration_seconds`, not `request.duration_seconds`.

- [ ] **Step 4: Write failing frontend request and migration tests**

```ts
it.each([0, 15, 90, 300])('serializes duration %s', (durationSeconds) => {
  const request = buildRunRequest({ ...createRunDraft(), durationSeconds })
  expect(request.creation_spec.duration_seconds).toBe(durationSeconds)
})

it('migrates the existing 90-second draft without losing duration', () => {
  const migrated = migrateRunDraft({ version: 5, draft: { durationSeconds: 90 } })
  expect(migrated.durationSeconds).toBe(90)
})
```

- [ ] **Step 5: Run frontend tests and verify RED where validation is missing**

Run: `npm --prefix frontend test -- --run src/features/run-composer/runRequest.builder.test.ts src/features/run-composer/runDraft.store.migration.test.ts`

- [ ] **Step 6: Add `normalizeDurationSeconds` and bump draft storage version**

```ts
export function normalizeDurationSeconds(value: number): number {
  if (value === 0) return 0
  return Math.min(300, Math.max(15, Math.round(value)))
}
```

Use it in request building and draft migration. Preserve `0` exactly.

- [ ] **Step 7: Run backend and frontend focused tests and verify GREEN**

Run both commands from Steps 2 and 5.

- [ ] **Step 8: Commit**

```bash
git add relief_story_agent/models.py relief_story_agent/tests/test_v2_contract.py frontend/src/features/run-composer/runRequest.builder.ts frontend/src/features/run-composer/runRequest.builder.test.ts frontend/src/features/run-composer/runDraft.store.ts frontend/src/features/run-composer/runDraft.store.migration.test.ts
git commit -m "feat: support automatic through five minute durations"
```

## Task 2: Build the Segment Render Planner

**Files:**
- Create: `relief_story_agent/segment_render.py`
- Modify: `relief_story_agent/models.py`
- Create: `relief_story_agent/tests/test_segment_render.py`

- [ ] **Step 1: Write failing planner tests**

```python
def test_auto_duration_preserves_six_authored_ranges():
    states = build_segment_render_plan(SIX_SHOTS, target_duration_seconds=0, fps=24)
    assert [item.duration_seconds for item in states] == [10, 15, 20, 15, 15, 15]
    assert [item.frame_count for item in states] == [241, 361, 481, 361, 361, 361]
    assert states[0].local_frame_indices == [0, 80, 159, 239]
    assert states[2].local_frame_indices == [0, 160, 319, 479]

def test_explicit_duration_retimes_and_preserves_exact_total():
    states = build_segment_render_plan(SIX_SHOTS, target_duration_seconds=60, fps=24)
    assert sum(item.duration_seconds for item in states) == 60
    assert all(item.duration_seconds >= 1 for item in states)
    assert states[0].authored_time_range == "0-10s"
    assert states[-1].render_time_range.endswith("60s")

def test_every_shot_gets_one_stable_segment_id():
    states = build_segment_render_plan(SIX_SHOTS, target_duration_seconds=90, fps=24)
    assert [item.segment_id for item in states] == [f"shot-{i:03d}" for i in range(1, 7)]
```

- [ ] **Step 2: Run planner tests and verify RED**

Run: `python -m pytest relief_story_agent/tests/test_segment_render.py -q`

Expected: import failure because the planner does not exist.

- [ ] **Step 3: Add persisted segment and assembly models**

Add `WorkflowModelBinding`, `SegmentRenderState`, and `VideoAssemblyState` to `models.py`. Use the status literals and fields from the approved design. Add these defaults to `RunState`:

```python
segment_renders: list[SegmentRenderState] = Field(default_factory=list)
video_assembly: VideoAssemblyState = Field(default_factory=VideoAssemblyState)
segment_schema_version: int = 2
```

- [ ] **Step 4: Implement strict range parsing and proportional retiming**

```python
def parse_time_range(value: str) -> tuple[int, int]:
    match = re.fullmatch(r"\s*(\d+)\s*-\s*(\d+)\s*s?\s*", value)
    if not match:
        raise ValueError(f"Invalid time_range: {value}")
    start, end = map(int, match.groups())
    if end <= start:
        raise ValueError(f"time_range must increase: {value}")
    return start, end

def local_frame_indices(duration_seconds: int, fps: int) -> list[int]:
    last = duration_seconds * fps - 1
    return [0, round(last / 3), round(last * 2 / 3), last]
```

For explicit duration, use largest-remainder proportional allocation with a one-second minimum and assign the final rounding remainder deterministically.

- [ ] **Step 5: Implement `build_segment_render_plan`**

The function copies only safe shot fields, stores authored and render ranges, derives four grid panels when absent, and returns ordered `SegmentRenderState` instances with `status="planned"`.

- [ ] **Step 6: Run planner tests and verify GREEN**

Run: `python -m pytest relief_story_agent/tests/test_segment_render.py -q`

- [ ] **Step 7: Commit**

```bash
git add relief_story_agent/models.py relief_story_agent/segment_render.py relief_story_agent/tests/test_segment_render.py
git commit -m "feat: add persisted segment render plans"
```

## Task 3: Produce Four Panel Prompts Per Segment

**Files:**
- Modify: `relief_story_agent/output_contracts.py`
- Modify: `relief_story_agent/prompt_templates.py`
- Modify: `relief_story_agent/grid_image.py`
- Modify: `relief_story_agent/tests/test_prompt_templates.py`
- Modify: `relief_story_agent/tests/test_grid_image.py`
- Modify: `relief_story_agent/tests/test_prompt_workflow.py`

- [ ] **Step 1: Write failing prompt contract tests**

```python
def test_writer_contract_accepts_four_grid_panel_prompts():
    shot = valid_shot()
    shot["grid_panel_prompts"] = ["开场", "发展", "高潮", "收束"]
    assert require_shot_contract([shot], "gpt_prompt_writer")[0]["grid_panel_prompts"] == shot["grid_panel_prompts"]

def test_grid_prompt_is_scoped_to_one_segment():
    prompt = compile_segment_four_grid_prompt(valid_shot(), max_chars=4000)
    assert "2×2" in prompt
    assert all(label in prompt for label in ("左上", "右上", "左下", "右下"))
    assert "其他分段" not in prompt
```

- [ ] **Step 2: Run prompt tests and verify RED**

Run: `python -m pytest relief_story_agent/tests/test_prompt_templates.py relief_story_agent/tests/test_grid_image.py relief_story_agent/tests/test_prompt_workflow.py -q`

- [ ] **Step 3: Extend writer, audit, and reviser templates**

Require `grid_panel_prompts` to contain four chronological moments within the same segment. Explicitly forbid combining different storyboard segments into one G2 request. Keep imported legacy outputs valid by allowing the field to be absent.

- [ ] **Step 4: Implement deterministic compatibility panels**

```python
def grid_panel_prompts_for_shot(shot: Mapping[str, Any]) -> tuple[list[str], str]:
    supplied = shot.get("grid_panel_prompts")
    if isinstance(supplied, list) and len(supplied) == 4 and all(str(x).strip() for x in supplied):
        return [str(x).strip() for x in supplied], "model"
    base = str(shot.get("image_prompt") or shot.get("description") or "").strip()
    return [
        f"开场建立：{base}",
        f"动作发展：{base}",
        f"情绪高潮：{base}",
        f"镜头收束：{base}",
    ], "derived"
```

- [ ] **Step 5: Implement `compile_segment_four_grid_prompt`**

The prompt must state one segment, one 2x2 image, chronological panel order, consistent identity/location/lighting/camera axis, no panel labels or text rendered into the image, and include aspect ratio intent.

- [ ] **Step 6: Run prompt tests and verify GREEN**

Run the command from Step 2.

- [ ] **Step 7: Commit**

```bash
git add relief_story_agent/output_contracts.py relief_story_agent/prompt_templates.py relief_story_agent/grid_image.py relief_story_agent/tests/test_prompt_templates.py relief_story_agent/tests/test_grid_image.py relief_story_agent/tests/test_prompt_workflow.py
git commit -m "feat: generate one four panel prompt per segment"
```

## Task 4: Generate and Upload One G2 Image Per Segment

**Files:**
- Modify: `relief_story_agent/orchestrator.py`
- Modify: `relief_story_agent/artifacts.py`
- Create: `relief_story_agent/tests/test_segment_pipeline.py`
- Modify: `relief_story_agent/tests/test_retry_runs.py`

- [ ] **Step 1: Write a failing six-image orchestration test**

Use a fake image provider that records prompts and returns unique PNG bytes. Assert:

```python
run = orchestrator.run(make_six_shot_request())
assert len(provider.calls) == 6
assert len(run.segment_renders) == 6
assert all(segment.grid_image_asset for segment in run.segment_renders)
assert len({segment.grid_image_asset.sha256 for segment in run.segment_renders}) == 6
assert [segment.status for segment in run.segment_renders] == ["image_ready"] * 6
assert "shot 2" not in provider.calls[0].prompt
```

- [ ] **Step 2: Run the test and verify RED**

Run: `python -m pytest relief_story_agent/tests/test_segment_pipeline.py -q`

Expected: the current implementation makes one provider call and writes one asset.

- [ ] **Step 3: Replace global stage-8 logic with segment checkpoints**

In `_run_four_grid_asset`:

```python
if not run.segment_renders:
    run.segment_renders = build_segment_render_plan(
        storyboard,
        target_duration_seconds=run.request.creation_spec.duration_seconds,
        fps=24,
    )
for segment in run.segment_renders:
    if segment.grid_image_checkpoint == "workflow_patched":
        continue
    self._acquire_segment_grid_asset(run, segment, config)
```

Persist after prompt compilation, image acquisition, validation, upload, and workflow preview. Use `segments/{order:03d}-{segment_id}` directories and deterministic filenames containing run and segment IDs.

- [ ] **Step 4: Emit segment-scoped image events**

Every event data payload includes `segment_id`, `order`, `task_id`, and public provider metadata. Never include API keys or authorization headers.

- [ ] **Step 5: Restrict recovery invalidation to one segment**

Add `segment_id` to `GridImageRetryOverride`. Clear image/submission/output/assembly fields only for that segment. Preserve completed siblings.

- [ ] **Step 6: Run segment and retry tests and verify GREEN**

Run: `python -m pytest relief_story_agent/tests/test_segment_pipeline.py relief_story_agent/tests/test_retry_runs.py -q`

- [ ] **Step 7: Commit**

```bash
git add relief_story_agent/orchestrator.py relief_story_agent/artifacts.py relief_story_agent/tests/test_segment_pipeline.py relief_story_agent/tests/test_retry_runs.py
git commit -m "feat: generate G2 assets per segment"
```

## Task 5: Validate Workflow Models and Persist Exact Execution Manifest

**Files:**
- Create: `relief_story_agent/workflow_models.py`
- Create: `relief_story_agent/tests/test_workflow_models.py`
- Modify: `relief_story_agent/config_validation.py`
- Modify: `relief_story_agent/artifacts.py`
- Modify: `relief_story_agent/tests/test_config_validation.py`

- [ ] **Step 1: Write failing model manifest tests**

```python
def test_model_manifest_reports_available_loader_values():
    manifest = build_workflow_model_manifest(WORKFLOW, OBJECT_INFO)
    assert manifest[0].node_id == "151"
    assert manifest[0].selected == "ltx-2.3-22b.safetensors"
    assert manifest[0].available is True

def test_missing_model_blocks_submission_with_node_details():
    with pytest.raises(WorkflowModelUnavailable) as exc:
        validate_workflow_models(WORKFLOW, OBJECT_INFO_WITHOUT_SELECTED_MODEL)
    assert exc.value.details[0]["node_id"] == "151"
```

- [ ] **Step 2: Run model tests and verify RED**

Run: `python -m pytest relief_story_agent/tests/test_workflow_models.py -q`

- [ ] **Step 3: Implement loader discovery**

Recognize model-bearing inputs from runtime object info instead of hardcoding only LTX nodes. Record node ID, title, class type, input name, selected filename, available choices, and availability. Fingerprint the source workflow with SHA-256.

- [ ] **Step 4: Add preflight blocking check**

`config_validation.py` uses targeted object info and returns `comfyui_workflow_models` with exact missing model/node details. The check runs before stage 8 so paid G2 requests do not start when video models are unavailable.

- [ ] **Step 5: Write `execution_manifest.json`**

Include public run configuration, workflow identity, model manifest, duration mode, authored/planned durations, and all segment parameters. Redact `api_key`, authorization headers, and environment values.

- [ ] **Step 6: Run model and config tests and verify GREEN**

Run: `python -m pytest relief_story_agent/tests/test_workflow_models.py relief_story_agent/tests/test_config_validation.py -q`

- [ ] **Step 7: Commit**

```bash
git add relief_story_agent/workflow_models.py relief_story_agent/tests/test_workflow_models.py relief_story_agent/config_validation.py relief_story_agent/tests/test_config_validation.py relief_story_agent/artifacts.py
git commit -m "feat: verify workflow models before rendering"
```

## Task 6: Prepare One Exact LTX Workflow Per Segment

**Files:**
- Modify: `relief_story_agent/ltx_workflow.py`
- Modify: `relief_story_agent/comfyui.py`
- Modify: `relief_story_agent/tests/test_ltx_workflow.py`
- Modify: `relief_story_agent/tests/test_comfyui_mapping.py`
- Modify: `relief_story_agent/tests/test_comfyui_idempotency.py`

- [ ] **Step 1: Write failing segment payload tests**

```python
payload = build_segment_ltx_payload(segment)
assert payload["duration_seconds"] == 10
assert payload["fps"] == 24
assert payload["frame_indices"] == "0,80,159,239"
assert len(payload["shots"]) == 1
assert payload["shots"][0]["shot_id"] == 1
```

Also assert that the saved API prompt references only the segment image filename and uses `run_id/segment_id` in the output prefix.

- [ ] **Step 2: Run LTX and ComfyUI tests and verify RED**

Run: `python -m pytest relief_story_agent/tests/test_ltx_workflow.py relief_story_agent/tests/test_comfyui_mapping.py relief_story_agent/tests/test_comfyui_idempotency.py -q`

- [ ] **Step 3: Add `build_segment_ltx_payload`**

Build prompt, negative prompt, local frame indices, four strengths, local duration, FPS, one shot, and provenance. Do not call the global balanced-shot selector.

- [ ] **Step 4: Add `prepare_segment_workflow`**

Return `PlannedComfyUIWorkflow` with submission key `segment:{segment_id}`, deterministic prompt/client IDs, exact patched API JSON, replacements, and public provenance.

- [ ] **Step 5: Extend `/prompt` payload metadata**

```python
payload = {
    "prompt": workflow,
    "prompt_id": prompt_id,
    "client_id": client_id,
    "extra_data": {
        "relief_story_agent": provenance,
        "extra_pnginfo": {"workflow": source_litegraph_workflow},
    },
}
```

Keep compatibility for non-segment callers by making `extra_data` optional.

- [ ] **Step 6: Persist workflow API JSON before submission**

Write `workflow_api.json`, `ltx_payload.json`, and `submission_metadata.json` atomically to the segment directory before POST `/prompt`.

- [ ] **Step 7: Run focused tests and verify GREEN**

Run the command from Step 2.

- [ ] **Step 8: Commit**

```bash
git add relief_story_agent/ltx_workflow.py relief_story_agent/comfyui.py relief_story_agent/tests/test_ltx_workflow.py relief_story_agent/tests/test_comfyui_mapping.py relief_story_agent/tests/test_comfyui_idempotency.py
git commit -m "feat: prepare exact LTX workflow per segment"
```

## Task 7: Execute and Monitor ComfyUI Segments Sequentially

**Files:**
- Modify: `relief_story_agent/orchestrator.py`
- Modify: `relief_story_agent/comfyui.py`
- Modify: `relief_story_agent/tests/test_segment_pipeline.py`
- Modify: `relief_story_agent/tests/test_comfyui_outputs.py`
- Modify: `relief_story_agent/tests/test_scheduler.py`

- [ ] **Step 1: Write a failing strict-sequencing test**

Use a fake ComfyUI transport that blocks segment 1 history until released. Assert no `/prompt` request for segment 2 occurs while segment 1 is queued or running. After segment 1 completes, assert segment 2 submits.

- [ ] **Step 2: Write a failing monitoring-window test**

```python
run = orchestrator.run(request_with_output_timeout(0.01))
assert run.status == "running"
assert run.segment_renders[0].status in {"queued", "running"}
assert len(prompt_posts) == 1
assert any(event.event_type == "segment_monitoring_extended" for event in run.events)
```

- [ ] **Step 3: Run segment/output/scheduler tests and verify RED**

Run: `python -m pytest relief_story_agent/tests/test_segment_pipeline.py relief_story_agent/tests/test_comfyui_outputs.py relief_story_agent/tests/test_scheduler.py -q`

- [ ] **Step 4: Replace global submit/wait with a segment loop**

For each nonterminal segment: reconcile deterministic submission, prepare if needed, submit once, persist accepted ID, poll queue/history, download outputs, mark complete, then continue. Maintain top-level `comfyui_prompt_ids` and `comfyui_outputs` as flattened compatibility views.

- [ ] **Step 5: Extend monitoring rather than fail active work**

When a wait window expires, inspect diagnostics. Continue polling when the prompt is present in queue/history as active. Set `unknown` only when absent from both. Never POST `/prompt` again for `accepted`, `queued`, `running`, or `unknown` without reconciliation.

- [ ] **Step 6: Implement remote cancellation per segment**

Cancel only the selected prompt ID and record `ComfyUICancellation`. If the running ComfyUI endpoint supports only global interrupt, expose that impact in the response before invoking it.

- [ ] **Step 7: Run focused tests and verify GREEN**

Run the command from Step 3.

- [ ] **Step 8: Commit**

```bash
git add relief_story_agent/orchestrator.py relief_story_agent/comfyui.py relief_story_agent/tests/test_segment_pipeline.py relief_story_agent/tests/test_comfyui_outputs.py relief_story_agent/tests/test_scheduler.py
git commit -m "feat: render ComfyUI segments sequentially"
```

## Task 8: Assemble Completed Segment Videos

**Files:**
- Modify: `pyproject.toml`
- Modify: `tools/desktop/Build-Desktop.ps1`
- Create: `relief_story_agent/video_assembly.py`
- Create: `relief_story_agent/tests/test_video_assembly.py`
- Modify: `relief_story_agent/orchestrator.py`

- [ ] **Step 1: Write failing assembler tests**

```python
def test_assembler_preserves_story_order(tmp_path, fake_runner):
    result = assemble_segment_videos([clip2, clip1], output_path, order=[2, 1], runner=fake_runner)
    manifest = Path(result.concat_manifest_path).read_text(encoding="utf-8")
    assert manifest.index(str(clip2)) < manifest.index(str(clip1))

def test_failed_assembly_preserves_all_clips(tmp_path, failing_runner):
    result = assemble_segment_videos(CLIPS, output_path, runner=failing_runner)
    assert result.status == "failed"
    assert all(path.exists() for path in CLIPS)
```

- [ ] **Step 2: Run assembler tests and verify RED**

Run: `python -m pytest relief_story_agent/tests/test_video_assembly.py -q`

- [ ] **Step 3: Add `imageio-ffmpeg` and desktop collection**

Add `imageio-ffmpeg>=0.5` to dependencies. Resolve the executable with `imageio_ffmpeg.get_ffmpeg_exe()`. Update PyInstaller invocation with the package's data/binary collection so the desktop sidecar works offline.

- [ ] **Step 4: Implement stream-copy and normalized fallback**

First run `ffmpeg -f concat -safe 0 -i concat.txt -c copy`. If it fails, run H.264/AAC normalization to a temporary file and atomically replace the final output on success. Capture stderr tail and return code in `VideoAssemblyState`.

- [ ] **Step 5: Invoke assembly after all segments complete**

Select one primary video output per segment, validate count/order, emit assembly events, persist state, and refresh terminal artifacts. Assembly retry must call only this function.

- [ ] **Step 6: Run assembler and segment tests and verify GREEN**

Run: `python -m pytest relief_story_agent/tests/test_video_assembly.py relief_story_agent/tests/test_segment_pipeline.py -q`

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml tools/desktop/Build-Desktop.ps1 relief_story_agent/video_assembly.py relief_story_agent/tests/test_video_assembly.py relief_story_agent/orchestrator.py
git commit -m "feat: assemble ordered segment videos"
```

## Task 9: Add Segment APIs and Artifact Discovery

**Files:**
- Modify: `relief_story_agent/models.py`
- Modify: `relief_story_agent/api.py`
- Modify: `relief_story_agent/orchestrator.py`
- Modify: `relief_story_agent/artifacts.py`
- Modify: `relief_story_agent/tests/test_api.py`
- Modify: `relief_story_agent/tests/test_artifacts.py`

- [ ] **Step 1: Write failing API tests**

Test render-plan listing, segment detail, image retry, video retry, cancellation, and assembly. Assert unknown segment returns 404, invalid state returns 409, completed segment retry requires `force=true`, and serialized responses contain no secret fields.

- [ ] **Step 2: Run API/artifact tests and verify RED**

Run: `python -m pytest relief_story_agent/tests/test_api.py relief_story_agent/tests/test_artifacts.py -q`

- [ ] **Step 3: Add narrow request contracts**

```python
class SegmentImageRetryRequest(BaseModel):
    runninghub_site: Literal["cn", "ai"] | None = None
    aspect_ratio: Literal["16:9", "9:16"] | None = None
    resolution: Literal["1k", "2k"] | None = None
    force: bool = False

class SegmentActionRequest(BaseModel):
    force: bool = False
```

- [ ] **Step 4: Add routes from the approved design**

Routes call orchestrator methods and return persisted state. Use 409 with stable error codes for conflicts. Segment retry queues from stage 8 or 10 while preserving sibling segment checkpoints.

- [ ] **Step 5: Expose segment artifacts**

Artifact listing includes kind, segment ID, order, prompt ID, local path, existence, and media type for image prompt, G2 image, workflow API JSON, model manifest, clip, concat manifest, and final video.

- [ ] **Step 6: Run API/artifact tests and verify GREEN**

Run the command from Step 2.

- [ ] **Step 7: Commit**

```bash
git add relief_story_agent/models.py relief_story_agent/api.py relief_story_agent/orchestrator.py relief_story_agent/artifacts.py relief_story_agent/tests/test_api.py relief_story_agent/tests/test_artifacts.py
git commit -m "feat: expose segment render recovery APIs"
```

## Task 10: Build Duration and Segment Execution UI

**Files:**
- Modify: `frontend/src/features/run-composer/RunComposer.tsx`
- Modify: `frontend/src/features/run-composer/RunComposer.test.tsx`
- Modify: `frontend/src/features/workbench/workbench.api.ts`
- Create: `frontend/src/features/autopilot/SegmentExecutionPanel.tsx`
- Create: `frontend/src/features/autopilot/SegmentExecutionPanel.test.tsx`
- Modify: `frontend/src/pages/AutopilotPage.tsx`
- Modify: `frontend/src/pages/AutopilotPage.test.tsx`
- Modify: `frontend/src/index.css`

- [ ] **Step 1: Write failing duration UI tests**

Assert preset options include auto, 30, 60, 90, 120, 180, 240, and 300 seconds; exact minute/second editing clamps to 15-300 unless auto is selected; selecting auto serializes zero.

- [ ] **Step 2: Write failing segment panel tests**

Given six segment states, assert six rows render with exact ranges/durations. Selecting segment 3 reveals its G2 image, prompts, workflow/model names, 20 seconds, 24 FPS, 481 frames, `0,160,319,479`, seed, prompt ID, and output. Assert pending actions show progress text and invalid actions are disabled.

- [ ] **Step 3: Run frontend tests and verify RED**

Run: `npm --prefix frontend test -- --run src/features/run-composer/RunComposer.test.tsx src/features/autopilot/SegmentExecutionPanel.test.tsx src/pages/AutopilotPage.test.tsx`

- [ ] **Step 4: Implement compact duration controls**

Use a preset select or menu plus minute/second numeric inputs. Keep the control in the primary creation row. Display `自动按分镜` for zero and a live planned total label after preflight.

- [ ] **Step 5: Add typed API models and mutations**

Define `SegmentRenderState`, `WorkflowModelBinding`, `VideoAssemblyState`, and request payload types matching backend fields. Add query functions for render plan/detail and mutation functions for retry/cancel/assemble.

- [ ] **Step 6: Implement `SegmentExecutionPanel`**

Use a dense table/list, not repeated decorative cards. Each row has stable columns for segment, time, G2, ComfyUI, output, and actions. The selected row opens one detail region. Use Lucide icons with tooltips for open, retry, cancel, and reveal actions.

- [ ] **Step 7: Integrate stages 8 and 10**

`AutopilotPage` renders the panel for both stages, defaults selection to current/failed segment, polls while any segment is nonterminal, and shows assembly separately. Keep existing stage navigation and recovery actions for legacy runs.

- [ ] **Step 8: Add restrained responsive styles**

Maintain the current light beach/glass visual language, use 8px-or-less row/detail radii, stable grid tracks, no nested cards, and mobile horizontal scrolling for the execution table. Ensure long paths/model names wrap without overlapping actions.

- [ ] **Step 9: Run frontend tests, typecheck, lint, and build**

Run:

```bash
npm --prefix frontend test -- --run
npm --prefix frontend run typecheck
npm --prefix frontend run lint
npm --prefix frontend run build
```

- [ ] **Step 10: Commit**

```bash
git add frontend/src/features/run-composer/RunComposer.tsx frontend/src/features/run-composer/RunComposer.test.tsx frontend/src/features/workbench/workbench.api.ts frontend/src/features/autopilot/SegmentExecutionPanel.tsx frontend/src/features/autopilot/SegmentExecutionPanel.test.tsx frontend/src/pages/AutopilotPage.tsx frontend/src/pages/AutopilotPage.test.tsx frontend/src/index.css
git commit -m "feat: visualize segment rendering and duration"
```

## Task 11: Migration, Full Verification, and Desktop Deployment

**Files:**
- Modify: `relief_story_agent/tests/test_persistent_store.py`
- Modify: `relief_story_agent/tests/test_recovery_plan.py`
- Modify: `desktop/electron/tests/*` only if packaging expectations change
- Build output: `frontend/dist`
- Build output: `desktop/electron/sidecar/bin/relief-story-agent-api.exe`
- Build output: `desktop/electron/release/win-unpacked`

- [ ] **Step 1: Add legacy-run migration tests**

Assert old JSON state with one `grid_image_asset` loads as `segment_schema_version=1`, remains inspectable, and is not automatically converted or charged. Assert new state resumes the first nonterminal segment without duplicating accepted prompt IDs.

- [ ] **Step 2: Run persistence and recovery tests**

Run: `python -m pytest relief_story_agent/tests/test_persistent_store.py relief_story_agent/tests/test_recovery_plan.py -q`

- [ ] **Step 3: Run complete backend verification**

Run: `python -m pytest relief_story_agent/tests -q`

Expected: zero failures.

- [ ] **Step 4: Run complete frontend and Electron verification**

Run:

```bash
npm --prefix frontend test -- --run
npm --prefix frontend run typecheck
npm --prefix frontend run lint
npm --prefix frontend run build
npm --prefix desktop/electron run check
npm --prefix desktop/electron test
```

- [ ] **Step 5: Build desktop sidecar and package**

Run:

```powershell
powershell -ExecutionPolicy Bypass -File tools/desktop/Build-Desktop.ps1 -SkipInstaller -SkipDependencyInstall
npm --prefix desktop/electron run pack
```

Confirm the packaged sidecar can resolve the bundled FFmpeg executable without network access.

- [ ] **Step 6: Run a non-paid real-workflow preflight**

With the supplied LTX workflow and six-shot storyboard, verify the plan reports six segments, six planned G2 calls, durations `10,15,20,15,15,15`, six exact workflow artifact paths, and all configured loader models. Do not call G2 or `/prompt` during this check.

- [ ] **Step 7: Run one short paid acceptance after explicit confirmation**

Use a 15-second two-segment test, show the exact estimated API operations before submission, then verify two G2 images, two sequential ComfyUI prompt IDs, two clips, one assembled video, and no local-failed/remote-running contradiction.

- [ ] **Step 8: Deploy the verified client**

Stop only processes launched from `C:\Users\dcf\Desktop\Relief Story Agent 最新客户端\win-unpacked`, replace the packaged directory, compare sidecar and `app.asar` SHA-256 hashes, launch the client, and verify `/api/health` plus the render-plan endpoint.

- [ ] **Step 9: Commit any verification-only fixture updates**

```bash
git add relief_story_agent/tests/test_persistent_store.py relief_story_agent/tests/test_recovery_plan.py desktop/electron/tests
git commit -m "test: cover segmented desktop recovery"
```

## Acceptance Checklist

- [ ] `0` duration means automatic storyboard duration.
- [ ] Explicit duration supports every integer from 15 through 300 seconds.
- [ ] A six-shot storyboard creates six segment render states.
- [ ] Every segment gets one G2 four-panel image and one ComfyUI prompt ID.
- [ ] ComfyUI submissions are strictly sequential.
- [ ] Segment durations and local frame indices match the execution manifest.
- [ ] Workflow source, hash, models, parameters, prompts, images, queue state, and outputs are visible before and during execution.
- [ ] Missing models block before G2 charges.
- [ ] Monitoring timeout cannot mark active remote work failed.
- [ ] Retry and cancellation are segment-scoped.
- [ ] Completed clips survive later failures.
- [ ] Final assembly preserves segment order.
- [ ] Legacy runs remain readable without automatic paid migration.
- [ ] No API key or secret value appears in state, events, artifacts, logs, or UI.

