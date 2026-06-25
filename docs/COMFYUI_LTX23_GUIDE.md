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

This call pings `/queue`, reports running/pending queue counts, and analyzes the
workflow file. It does not upload images and does not enqueue video work.

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
Real smoke uploads, patches, and submits `/prompt`. It does not wait for video
rendering and does not download final video files.

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
- inspect `ltx_injection_points`;
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
- call `POST /api/runs/{run_id}/refresh-comfyui`;
- inspect run artifacts and `comfyui_diagnostics`.

## Operational Rule

Do not edit the fixed agent pipeline order to solve ComfyUI issues. Fix the
workflow, model files, template prompts, or local resource limits, then retry
from the failed stage.
