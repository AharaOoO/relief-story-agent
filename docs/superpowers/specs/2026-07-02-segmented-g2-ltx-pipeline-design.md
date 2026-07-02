# Segmented G2 and LTX Pipeline Design

## Status

Approved direction: one persisted story run contains multiple independently observable segment render jobs. Each story segment gets one G2-generated four-panel reference image and one LTX 2.3 video submission. ComfyUI submissions execute sequentially and completed clips are assembled in story order.

## Problem

The current implementation collapses the entire storyboard into one image and one ComfyUI prompt:

- `RunState` stores one `grid_image_asset`.
- `four_grid_asset` compiles one prompt from the full storyboard.
- LiteGraph submission produces one `ltx` workflow payload.
- Global story duration is injected into that payload, so a six-segment, 90-second story becomes one 90-second render.
- The four-panel selector samples only four shots, which can omit story segments.
- A fixed 600-second monitoring timeout marks the local run failed even when ComfyUI is still rendering.
- The UI does not expose the exact workflow, models, segment parameters, image inputs, patched API prompt, prompt ID, or remote queue state.

This behavior conflicts with the product requirement that every segment have its own reference image, prompt, duration, render job, output, and recovery state.

## Product Invariants

1. One finalized storyboard segment maps to exactly one `SegmentRenderState`.
2. Each segment has exactly one G2 four-panel image prompt and one accepted reference image before video submission.
3. A segment's LTX payload contains only that segment's prompt and local timeline.
4. Segment duration is derived from `time_range`; the full story duration is never injected into an individual segment.
5. ComfyUI receives at most one active segment from a story run at a time.
6. A completed image or video is never regenerated during an unrelated segment retry.
7. A monitoring timeout never converts a remotely queued or running prompt into a failed render.
8. The application never installs, selects, or changes workflow model files silently.
9. Before submission, users can see the workflow name, workflow path, model manifest, segment duration, FPS, frame count, local keyframe indices, seed, image, prompts, and expected output.
10. Every submitted API workflow is persisted as an artifact before the network request.
11. Story duration supports a convenient 0-5 minute control: `0` means derive duration from the finalized storyboard, while explicit values range from 15 to 300 seconds.

## Duration Control

Replace the fixed 90-second assumption with `target_duration_seconds`, validated from 0 through 300:

- `0`: automatic duration, derived from the finalized storyboard time ranges;
- `15-300`: explicit total duration in seconds;
- values from 1 through 14 are rejected because they cannot produce a useful multi-segment short;
- the existing request field remains readable during migration and maps to `target_duration_seconds`.

The desktop creation surface provides presets for `自动`, `30 秒`, `60 秒`, `90 秒`, `2 分钟`, `3 分钟`, `4 分钟`, and `5 分钟`, plus a numeric minute/second editor for exact values. A slider may supplement these controls but is never the only precision input.

When an explicit duration differs from the authored storyboard total, segment durations are proportionally retimed while preserving order and ensuring every segment receives at least one second. The final segment absorbs rounding so the sum exactly equals the selected target. All segment ranges, frame counts, local reference indices, manifests, and UI estimates are regenerated from the retimed plan before any paid G2 request.

## Storyboard Contract

The finalized storyboard remains an ordered list. Every shot must provide:

- `shot_id`
- `time_range`
- `description`
- `image_prompt`
- `negative_prompt`
- `comfyui_inputs.seed`
- `comfyui_inputs.strength`

Prompt-writing stages may additionally provide `grid_panel_prompts`, an array of four ordered strings describing opening, development, culmination, and exit moments within the same segment. Audit and revision stages validate that all four panels preserve character identity, direction, location, lighting, and action continuity.

For older or imported storyboards without `grid_panel_prompts`, a deterministic compiler derives four panel instructions from `description` and `image_prompt`. This compatibility path is explicit in artifacts as `grid_prompt_source: "derived"`; model-authored panels use `grid_prompt_source: "model"`.

## Persisted Data Model

Add `SegmentRenderState` to `RunState`:

```text
segment_id                 stable value such as shot-001
shot_id                    source storyboard identifier
order                      story order
time_range                 original global range
duration_seconds           parsed end minus start
fps                        copied from render configuration
frame_count                duration_seconds * fps + 1
local_frame_indices        four local indices within 0..duration*fps-1
positive_prompt            this segment only
negative_prompt            this segment only
grid_panel_prompts         exactly four strings
grid_image_prompt          exact G2 request prompt
grid_image_asset           generated/downloaded/uploaded image
grid_image_attempts        retries for this segment only
grid_image_checkpoint      per-segment image state
workflow_name              selected workflow filename
workflow_path              selected workflow path
workflow_sha256            immutable source fingerprint
workflow_api_artifact      exact patched API JSON path
workflow_models            loader node model manifest
submission                 one ComfyUISubmission
outputs                    outputs belonging to this prompt ID
status                     planned/image_generating/image_ready/
                           submitting/queued/running/completed/
                           failed/cancelled
error                      segment-scoped error
timestamps                 planned/submitted/started/completed
```

Add `VideoAssemblyState` containing ordered clip paths, concat manifest path, output path, status, and error.

Legacy single-image fields remain readable for old runs but new runs write only `segment_renders`. Loading an old run does not invent missing segment assets or silently resubmit work.

## Segment Planning

`build_segment_render_plan(final_storyboard, fps, workflow)` validates all ranges and creates one state per segment.

It also accepts `target_duration_seconds`. Automatic mode preserves storyboard ranges. Explicit mode proportionally retimes all segments and records both `authored_time_range` and `render_time_range` so users can inspect what changed.

For the current six-shot example the plan is:

| Segment | Global range | Local duration | Frame count |
|---|---:|---:|---:|
| 1 | 0-10s | 10s | 241 |
| 2 | 10-25s | 15s | 361 |
| 3 | 25-45s | 20s | 481 |
| 4 | 45-60s | 15s | 361 |
| 5 | 60-75s | 15s | 361 |
| 6 | 75-90s | 15s | 361 |

At 24 FPS, four reference indices are distributed across each local segment using `0`, one-third, two-thirds, and `duration * fps - 1`. For a 10-second segment this is `0,80,159,239`; for 15 seconds `0,120,239,359`; for 20 seconds `0,160,319,479`.

The LTX workflow still computes latent length as `duration * fps + 1`. Reference indices never use global story frame numbers.

## Stage 8: Per-Segment G2 Images

Stage 8 plans every segment first, then processes incomplete segment images in story order.

For each segment:

1. Compile one four-panel G2 prompt containing only that segment.
2. Persist the exact prompt before calling RunningHub.
3. Create and poll one G2 task using the selected `.cn` or `.ai` site.
4. Download and validate the image.
5. Save it under `segments/<order>-<segment_id>/four_grid.png`.
6. Upload it to ComfyUI using a deterministic filename.
7. Persist task ID, API site, aspect ratio, resolution, hash, dimensions, and upload result.
8. Emit segment-scoped events after every checkpoint.

The default implementation is sequential to keep cost and progress obvious. Existing image concurrency limits remain available for a future explicit batch option but are not used implicitly.

If segment 4 fails, retry resumes segment 4 and preserves images 1-3. Changing G2 site, aspect ratio, or resolution invalidates only the selected failed segment and its downstream video state.

## Stage 9: Execution Manifest

Stage 9 writes a human-readable execution manifest before any video submission. It includes:

- workflow filename, absolute path, SHA-256, and modification time
- targeted ComfyUI endpoint
- model loader node IDs, class types, selected filenames, and runtime availability
- one row per segment with prompts, image paths, duration, FPS, frame count, keyframe indices, seed, and strength
- planned queue order
- assembly output path

Missing node types or unavailable model filenames block submission with a precise node/model error. Model files are never installed or replaced automatically.

## Stage 10: Sequential ComfyUI Rendering

For each incomplete segment in order:

1. Load the immutable workflow and verify its SHA-256 still matches the manifest.
2. Fetch targeted `/object_info/{node_type}` data and validate node types and loader selections.
3. Build a segment-only LTX payload.
4. Patch the segment image filename, prompt JSON, seed, filename prefix, local duration, FPS, and local frame indices.
5. Persist the exact API prompt to the segment artifact directory.
6. Submit one `/prompt` request with deterministic prompt and client IDs.
7. Persist the accepted prompt ID before waiting.
8. Poll queue and history until completion, cancellation, or a terminal ComfyUI error.
9. Download outputs for that prompt ID and mark the segment complete.
10. Start the next segment only after the current segment reaches a terminal state.

Submission `extra_data` includes run ID, segment ID, segment order, workflow filename, source workflow fingerprint, duration, FPS, and artifact path. It also includes the source workflow metadata accepted by ComfyUI so queue/history entries carry useful provenance where the installed frontend supports it.

### Monitoring Semantics

`output_timeout_seconds` is a polling window, not a render failure deadline. When a window expires:

- if the prompt is queued or running, emit `segment_monitoring_extended` and continue without resubmission;
- if history reports execution error, fail that segment with the remote node error;
- if the prompt is absent from both queue and history, mark its status `unknown` and require reconciliation before retry;
- cancellation invokes remote interruption/deletion and records the result.

This prevents the local client from showing `failed` while ComfyUI is still consuming GPU.

## Video Assembly

After all segments complete, collect the primary video output for each segment in story order. The desktop sidecar bundles an FFmpeg provider through `imageio-ffmpeg`.

1. Write a concat manifest containing normalized absolute clip paths.
2. Attempt stream-copy concatenation because all clips come from the same workflow.
3. If stream copy rejects compatible-looking inputs, retry with H.264/AAC normalization.
4. Persist command metadata, return code, stderr tail, final file hash, duration probe, and output path.
5. Preserve every segment clip even if assembly fails.

Assembly failure is displayed separately from render failure and can be retried without G2 or ComfyUI work.

## API Surface

The run detail response exposes `segment_renders` and `video_assembly`.

Add:

- `GET /api/runs/{run_id}/render-plan`
- `GET /api/runs/{run_id}/segments/{segment_id}`
- `POST /api/runs/{run_id}/segments/{segment_id}/retry-image`
- `POST /api/runs/{run_id}/segments/{segment_id}/retry-video`
- `POST /api/runs/{run_id}/segments/{segment_id}/cancel`
- `POST /api/runs/{run_id}/assemble`

Retry endpoints reject completed work unless `force=true` is explicitly supplied. No endpoint accepts API keys in run payloads or returns secret values.

## Desktop UI

The ten top-level cooking stages remain unchanged. Stage 8 and stage 10 gain a segment execution table rather than another global settings block.

### Persistent Run Summary

Always show:

- workflow filename and verification state
- model readiness count
- story segments completed/total
- current segment and remote queue state
- total planned duration and completed duration
- G2 and ComfyUI site/endpoint
- assembly state
- selected total duration mode, authored duration, and planned render duration

### Segment Rows

Each row shows segment number, global time range, local duration, G2 image status, ComfyUI status, prompt ID, output status, and retry/cancel actions appropriate to its state.

Selecting a row opens an unframed detail panel with:

- four-panel G2 prompt and generated image preview
- positive/negative video prompts
- workflow filename, hash, and exact patched API JSON
- model filenames and node IDs
- resolution, FPS, frame count, local frame indices, seed, strength, sampler, CFG, and output prefix
- remote submission timestamps and queue/history state
- output video preview and open-folder action

Buttons display pending text and disable only conflicting actions. A failed row remains editable where recovery is valid; completed rows remain frozen by default.

## Events and Artifacts

Events use segment data rather than inventing more top-level stages:

- `segment_planned`
- `segment_grid_started`
- `segment_grid_completed`
- `segment_grid_failed`
- `segment_submission_prepared`
- `segment_submission_accepted`
- `segment_remote_running`
- `segment_monitoring_extended`
- `segment_completed`
- `segment_failed`
- `segment_cancelled`
- `assembly_started`
- `assembly_completed`
- `assembly_failed`

Every event includes `segment_id`, `order`, and safe public metadata. Artifacts are organized under `segments/001-shot-001`, `segments/002-shot-002`, and so on.

## Failure and Recovery Rules

- G2 failure stops before ComfyUI and preserves all completed segment images.
- Workflow/model preflight failure stops before `/prompt`.
- Submission transport uncertainty stores `unknown` and reconciles deterministic IDs before any retry.
- Remote execution errors attach the failing ComfyUI node details to the segment.
- Local restart resumes the first nonterminal segment.
- A segment video retry reuses its accepted G2 image.
- An image retry invalidates only that segment's patched workflow, submission, outputs, and assembly.
- Assembly retry never calls external model or image APIs.

## Migration and Compatibility

Existing completed runs remain readable. Existing failed runs with only one `grid_image_asset` are presented as legacy runs and are not automatically converted because the missing five images cannot be reconstructed without paid API calls.

New runs use schema version 2 segment state. API clients that do not understand `segment_renders` still receive existing top-level status, events, artifacts, and prompt IDs.

## Testing and Acceptance

### Unit and Contract Tests

- time-range parsing and local frame-index calculation
- one render state per finalized storyboard segment
- one G2 call and one image artifact per segment
- no segment omission when there are more than four shots
- segment-only LTX payload and deterministic prompt IDs
- targeted model availability validation
- sequential submission, including proof that segment 2 cannot submit before segment 1 completes
- monitoring-window extension without duplicate submission
- segment retry invalidation boundaries
- cancellation and unknown-state reconciliation
- FFmpeg assembly order and failure preservation
- API secret redaction

### Frontend Tests

- workflow/model summary rendering
- six segment rows for a six-shot storyboard
- exact duration/FPS/frame/model display
- pending, running, failed, completed, unknown, and cancelled states
- action feedback and segment-scoped retry/cancel payloads
- output video and artifact open actions

### Real Acceptance

Using the supplied six-segment storyboard and selected LTX workflow:

- six G2 image artifacts exist;
- six distinct ComfyUI prompt IDs are accepted one at a time;
- submitted durations are 10, 15, 20, 15, 15, and 15 seconds;
- each prompt references only its own image and prompt text;
- the UI exposes all workflow/model/render parameters before submission;
- local monitoring never reports failed while the remote prompt is queued or running;
- six clips and one assembled story video are discoverable from the asset library.
