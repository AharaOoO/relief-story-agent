# ComfyUI LTX 2.3 Guide

This project connects to the user's existing local ComfyUI package. It does not
generate nodes, does not install custom nodes, and does not replace the user's
workflow. The first supported production path is to read a user-provided LTX 2.3
workflow JSON, inject story data and the four-grid reference image, then submit
ComfyUI `/prompt`.

Short rule: the agent does not generate nodes.

## Supported Workflow Shapes

The agent supports two workflow shapes:

- `LiteGraph`: the frontend workflow JSON exported from ComfyUI.
- `API prompt JSON`: the backend prompt object accepted by ComfyUI `/prompt`.

For `LiteGraph`, the agent detects LTX injection points and converts the graph
to API prompt format. For `API prompt JSON`, use `placeholder_map_path` or
inline `placeholder_map` to tell the agent which node inputs should receive
prompt text, negative prompt text, seed, strength, or filename prefix.

LiteGraph analysis has two automatic adapter modes:

- `litegraph_ltx_auto_injection` is for the four-grid workflow shape that has an
  LTX JSON/string node. It patches the LTX payload, seed, filename prefix, and
  optional `TD_LTXVAddGuideFromGrid` image input.
- `litegraph_ltx_widget_patch` is for common integrated-package LTX workflows,
  including many `ComfyUI-LTXVideo` examples. It patches existing
  positive/negative prompt widgets, `RandomNoise` seeds, `LoadImage` filenames,
  and `SaveVideo`/`VHS_VideoCombine` filename prefixes.

Both modes preserve the user's graph topology. They do not create nodes,
install custom nodes, or change sampler settings.

During real submit, LiteGraph prompts are enriched with ComfyUI `/object_info`.
That runtime schema fills required widget values which may only exist in the
frontend JSON's `widgets_values`, including primitive defaults, loader defaults,
and dynamic combo children such as `resize_type.longer_size`. If a workflow's
COMBO model or LoRA filename is absent from the local package but a close
runtime option is available, the agent can reconcile the filename to the local
option before `/prompt`. If no confident match exists, the original value is
kept so ComfyUI reports the exact missing asset.

## Address Box Flow

Use this before any real generation:

```powershell
relief-story-agent connect-comfyui `
  --request "D:/relief_story_config/comfyui_connect.json" `
  --pretty
```

Equivalent API:

```http
POST /api/comfyui/connect
```

This call pings `/queue`, reports running/pending queue counts, analyzes the
workflow file, and reads `/object_info` when ComfyUI is reachable. The
`/object_info` check confirms that required custom node classes are available in
the user's currently running integrated package. It does not upload images and
does not enqueue video work.

If the user does not know which JSON file to pick from an integrated package,
scan the package first:

```powershell
relief-story-agent discover-comfyui-workflows `
  --search-root "D:/AI-Comfyui-onekey-V5/ComfyUI_windows_portable_nvidia/ComfyUI_windows_portable/ComfyUI" `
  --endpoint "127.0.0.1:8188/queue" `
  --filename-keyword "LTX" `
  --pretty
```

Use the `recommended.path` value as `workflow_api_path` when the returned
`adapter_mode` is `litegraph_ltx_auto_injection` or
`litegraph_ltx_widget_patch`.

## Four-grid Image

The LTX 2.3 four-grid flow expects a 2x2 reference sheet. The agent can:

- accept a manual image for smoke and manual override runs;
- generate the grid through an OpenAI-compatible image provider;
- validate dimensions, byte size, and mime type;
- upload the accepted image to ComfyUI `/upload/image`;
- inject the returned filename into the workflow `LoadImage` node.

For the common four-grid LiteGraph workflow, the important parts are:

- a `LoadImage` node for the four-grid image;
- an LTX JSON/string node for shot payload;
- a seed node;
- a video filename prefix node.

The workflow analyzer reports these injection points in `ltx_injection_points`.
For integrated-package widget workflows, it reports the patchable nodes in
`ltx_widget_patch_points` instead. These workflows may not expose a 2x2 grid
shape because they are ordinary LTX image/video workflows rather than the
special `TD_LTXVAddGuideFromGrid` graph.

## Preview Before Enqueue

Use preview to inspect what will be patched:

```http
POST /api/comfyui/preview
```

Preview returns a deterministic prompt id, content fingerprint, workflow format,
node count, and replacement summary. It does not contact ComfyUI.

## Smoke Runner

Dry-run:

```powershell
relief-story-agent smoke-comfyui `
  --request "D:/relief_story_config/smoke_request.json" `
  --dry-run
```

Real enqueue:

```powershell
relief-story-agent smoke-comfyui `
  --request "D:/relief_story_config/smoke_request.json"
```

Dry-run writes artifacts and patched workflow JSON without upload or enqueue.
Real smoke uploads, reads `/object_info`, patches, and submits `/prompt`. It
does not wait for video rendering and does not download final video files.

Recent local evidence:

```text
python -m relief_story_agent.smoke_comfyui --request "D:/relief_story_inputs/local_ltx_ready_smoke_request.real.json"
status=passed
ready=true
prompt_id=31037f9b-b8c8-5919-b717-fbe3c7e634eb
artifact_dir=D:\relief_story_smoke\comfyui_smoke_20260625T115742676759Z
```

The patched artifact from that run includes runtime-expanded fields such as
`resize_type.longer_size`, local LTX checkpoint aliases, text encoder aliases,
and LTX2.3 LoRA aliases accepted by the user's running ComfyUI.

## Common Errors

`workflow_path` or `workflow_api_path` does not exist:

- fix the local JSON path;
- avoid paths inside downloads folders if they will be moved later;
- run `relief-story-agent diagnose` again.

ComfyUI is not running:

- start the user's ComfyUI package;
- confirm `http://127.0.0.1:8188/queue` opens or returns JSON;
- run `POST /api/comfyui/connect` again.

`LoadImage` is not detected:

- confirm the workflow really uses a four-grid image;
- inspect `ltx_injection_points` or `ltx_widget_patch_points`;
- use manual `placeholder_map` only for API prompt JSON workflows.

Prompt submission fails:

- check custom nodes and model files in the ComfyUI console;
- confirm the workflow works manually inside ComfyUI;
- use smoke artifacts to compare patched workflow values.

Render runs out of VRAM:

- reduce resolution, frame count, or batch settings in the workflow;
- keep `comfyui-submission-concurrency` at `1`;
- run shorter smoke tests before a large batch.

Wrong or missing output:

- check `/history/{prompt_id}` in ComfyUI;
- run `relief-story-agent comfyui-outputs --endpoint "http://127.0.0.1:8188" --prompt-id "{prompt_id}" --pretty`;
- add `--wait --timeout-seconds 1200 --artifact-dir "D:/relief_story_outputs/manual_check" --download` when you want the Agent to wait and save rendered files;
- call `POST /api/comfyui/outputs` from a launcher or future UI when the user has pasted their local ComfyUI address and prompt id;
- call `POST /api/runs/{run_id}/refresh-comfyui`;
- inspect run artifacts and `comfyui_diagnostics`.

Standalone output refresh only reads ComfyUI `/history`, `/queue`, and `/view`.
It does not enqueue a prompt and does not rerun any model stage. This makes it a
safe post-render check for local ComfyUI bundles where users may keep the UI open
and render manually.

## Operational Rule

Do not edit the fixed agent pipeline order to solve ComfyUI issues. Fix the
workflow, model files, template prompts, or local resource limits, then retry
from the failed stage.
