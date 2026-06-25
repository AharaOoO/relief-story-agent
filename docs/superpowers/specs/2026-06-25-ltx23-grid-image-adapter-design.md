# LTX 2.3 Four-Grid Image Adapter Design

## Objective

Extend the existing short-video agent with a production-oriented four-grid image
asset stage for the supplied LTX 2.3 ComfyUI workflow.

The selected mode is dual-source:

- `auto`: generate the four-grid reference image through a configurable image
  provider, initially GPT Image 2.
- `manual_override`: use a local image supplied by the user and skip generation.

Both modes produce the same validated `GridImageAsset`, so upload, workflow
patching, persistence, retry, and audit behavior remain identical.

## Confirmed Workflow Facts

The supplied workflow is:

`C:\Users\dcf\Downloads\AI代码侠土豆-LTX-2.3 4宫格V3.0 红果短剧特调版 半自动(带运镜版).json`

UTF-8 corrected path:

`C:\Users\dcf\Downloads\AI代码侠土豆-LTX-2.3 4宫格V3.0 红果短剧特调版 半自动(带运镜版).json`

Read-only analysis established:

- Format: ComfyUI LiteGraph JSON
- Nodes: 60
- Links: 64
- Converted API nodes: 39
- LTX JSON input: node `202`, widget `text`
- Random seed: node `37`, widget `noise_seed`
- Output prefix: node `79`, widget `filename_prefix`
- Four-grid image: node `196`, widget `image`
- Grid guide: node `221`, type `TD_LTXVAddGuideFromGrid`
- Grid shape: 2 columns by 2 rows

The current adapter already injects nodes `202`, `37`, and `79`. It does not
yet provide or upload the image required by node `196`.

## Pipeline Position

The creative stage order remains unchanged:

```text
chief_screenwriter
-> deepseek_polish
-> quality_gate
-> gpt_prompt_writer
-> gpt_prompt_audit
-> gpt_prompt_reviser (at most once)
-> four_grid_asset
-> artifacts
-> comfyui
```

`four_grid_asset` is an execution stage, not another writing or review stage.
It consumes the approved final storyboard and cannot alter the script,
storyboard, prompts, or audit result.

## Architecture

### 1. Grid Image Configuration

Add `GridImageConfig` to `RunRequest` through `ComfyUIRunConfig`:

```text
mode: auto | manual_override
manual_image_path: optional local path
provider: openai_compatible
base_url: provider endpoint
api_key_env: environment variable name
model: configurable, default gpt-image-2
size: configurable image size
quality: configurable quality
output_format: png | jpeg | webp
timeout_seconds
max_attempts
```

Secrets remain excluded from serialized run state. The default mode is `auto`
when the detected workflow requires a grid image. A non-empty
`manual_image_path` takes precedence regardless of configured mode.

### 2. Provider Boundary

Create a focused image-provider interface:

```python
class GridImageProvider(Protocol):
    def generate(
        self,
        *,
        prompt: str,
        config: GridImageConfig,
    ) -> GeneratedImage:
        ...
```

The first implementation calls an OpenAI-compatible image endpoint. Model API
details remain isolated from orchestration. Tests use a deterministic fake
provider that returns real image bytes.

### 3. Prompt Compilation

The provider receives one concise four-grid prompt compiled from the final
storyboard. It must:

- select exactly four balanced timeline keyframes;
- preserve chronological order: top-left, top-right, bottom-left,
  bottom-right;
- include stable character identity, wardrobe, scene geography, camera side,
  and each frame's action state;
- request one clean 2x2 contact sheet with equal cells;
- prohibit borders containing text, captions, labels, watermarks, duplicated
  cells, and extra panels;
- stay within a configurable character limit suitable for GPT Image 2.

The compiler uses existing finalized image prompts. It does not ask another
language model to rewrite them, preventing a new unreviewed creative branch.

### 4. Asset Model and Persistence

Both automatic and manual modes produce:

```text
GridImageAsset
  source: generated | manual
  local_path
  sha256
  mime_type
  width
  height
  byte_size
  prompt
  provider
  model
  generated_at
  comfyui_filename
  upload_status
```

Run state stores the asset metadata, while image bytes live in the run artifact
directory. The run writes:

- `09_four_grid_prompt.json`
- `10_four_grid_image.<ext>`
- `11_comfyui_upload.json`

The numeric ordering follows the existing eight artifacts, including
`06_model_execution.json`, `07_comfyui_preview.json`, and `08_timeline.json`,
and keeps generated media adjacent to its upload receipt.

### 5. Validation

Before upload, validate:

- the file exists and can be decoded;
- MIME type and extension agree;
- width and height are positive;
- dimensions satisfy a configurable minimum;
- aspect ratio is close to square, as expected for a 2x2 grid;
- byte size is within configured limits;
- the four quadrants contain non-empty pixel variation;
- automatic output is saved inside the run artifact directory;
- a manual path is read-only and copied into the artifact directory.

The validator performs structural checks only. Semantic character-consistency
grading is explicitly outside this implementation scope and would require a
separately approved vision-audit stage.

### 6. ComfyUI Upload

Upload validated images through ComfyUI `/upload/image` using multipart form
data. Use a deterministic destination name based on:

```text
run_id + first 12 characters of sha256 + extension
```

The upload response must be normalized into the filename understood by a
ComfyUI `LoadImage` node. Repeated execution first reuses a persisted successful
upload receipt. If the previous upload result is uncertain, query or retry with
the same deterministic name instead of generating a new asset.

### 7. Workflow Detection and Injection

Extend `LTXInjectionPoints` with:

```text
grid_image_node_id
grid_image_input = image
grid_columns
grid_rows
```

Detection rules:

1. Find `TD_LTXVAddGuideFromGrid`.
2. Trace its `grid_image` input upstream.
3. Require exactly one reachable `LoadImage` node.
4. Read `columns` and `rows` from the guide node.
5. Reject ambiguous or missing image paths instead of selecting the first
   `LoadImage` node globally.

For the supplied workflow this must resolve node `196` and grid `2x2`.

Patching then performs four declared replacements only:

- node `196`: uploaded ComfyUI filename
- node `202`: LTX payload JSON
- node `37`: seed
- node `79`: output filename prefix

No other workflow input may be changed.

### 8. Preview and Preflight APIs

Extend existing endpoints instead of adding a parallel API family.

`POST /api/comfyui/analyze-workflow`

- reports the detected grid guide and load-image node;
- reports whether a grid asset is required;
- reports columns, rows, and adapter capabilities;
- fails on ambiguous image topology.

`POST /api/comfyui/preview`

- accepts an optional manual image path;
- compiles the four-grid prompt;
- validates a manual asset when provided;
- returns all four target replacements;
- returns the exact image filename when a manual or acquired asset is
  available, and an explicit `pending_generation` value for automatic mode
  before image bytes exist;
- does not generate, upload, or enqueue by default.

`GET /api/runs/{run_id}`

- returns grid asset metadata, generation attempts, upload state, and the final
  four workflow replacements.

No raw API key or image bytes are returned.

## Execution and Recovery Semantics

The stage is checkpointed into separate operations:

```text
prompt_compiled
image_acquired
image_validated
image_uploaded
workflow_patched
```

Recovery resumes from the last completed checkpoint:

- generation timeout, connection error, rate limit, or provider 5xx:
  retryable;
- local file missing, invalid image, invalid dimensions, or ambiguous workflow:
  non-retryable until configuration is corrected;
- upload timeout before acknowledgement: uncertain external state; reuse the
  deterministic name and reconcile before another upload;
- ComfyUI rejection: external, non-retryable by default;
- workflow patch failure: contract/external, non-retryable;
- manual override never falls back silently to auto generation.

An acquired image is never regenerated merely because upload or ComfyUI
submission failed.

## Batch Behavior

Each run owns one four-grid asset and one LTX submission. Batch concurrency
continues to use the persistent scheduler. Image generation and ComfyUI
submission use independent concurrency limits so that:

- image API quotas are respected;
- ComfyUI GPU jobs are not flooded;
- generated assets can queue safely while the GPU is occupied.

Initial defaults are:

- image generation concurrency: `2`;
- ComfyUI submission concurrency: `1`.

Both remain configurable and use separate scheduler boundaries.

## Security and Portability

- API keys come from environment variables and are excluded from run JSON.
- Manual paths are validated and copied; the source file is never modified.
- Artifact filenames are generated by the agent and cannot contain path
  traversal.
- Uploaded ComfyUI filenames are sanitized.
- The workflow file is treated as data and never executes local scripts.
- Provider and ComfyUI endpoints remain configurable for local deployment.

## Testing Strategy

### Unit tests

- balanced selection and chronological 2x2 prompt ordering;
- prompt character limit;
- manual path precedence;
- PNG/JPEG/WebP validation;
- invalid, empty, non-square, and undersized image rejection;
- deterministic asset hashes and ComfyUI filenames;
- graph tracing from node `221` to node `196`;
- ambiguity and missing-node rejection;
- patching changes only nodes `196`, `202`, `37`, and `79`.

### Integration tests

- fake image provider -> saved artifact -> fake ComfyUI upload -> patched prompt;
- manual image -> copied artifact -> upload -> patched prompt;
- generation retry does not duplicate completed assets;
- upload uncertainty reuses the same deterministic filename;
- failed ComfyUI submission reuses the existing generated image;
- run restart resumes from each checkpoint.

### Real-workflow regression test

Use a sanitized fixture derived from the supplied workflow structure. The test
must prove:

- 60 LiteGraph nodes are accepted;
- injection points resolve to `196`, `202`, `37`, and `79`;
- grid shape resolves to `2x2`;
- LiteGraph conversion produces the required API nodes and links;
- a preview includes exactly four replacements;
- the original workflow object remains unchanged.

The user's downloaded workflow remains an external development fixture and is
not copied into the distributable package unless licensing permits it.

## Acceptance Criteria

The feature is complete when:

1. Automatic and manual modes converge on one validated asset pipeline.
2. The supplied workflow is analyzed without a handwritten placeholder map.
3. The four-grid image is uploaded and injected into node `196`.
4. JSON, seed, and filename injection continue to target `202`, `37`, and `79`.
5. Preview exposes the exact four target nodes before side effects; its image
   value is exact for manual/acquired assets and explicitly pending for
   automatic mode before generation.
6. Restart and retry do not regenerate or re-upload completed assets
   unnecessarily.
7. Failed validation or ambiguous topology prevents ComfyUI enqueue.
8. All unit, integration, real-workflow regression, and full project tests pass.

## Out of Scope

- Desktop UI for selecting or cropping the image;
- automatic semantic vision grading of character consistency;
- automatic repair of arbitrary third-party ComfyUI workflows;
- generating ComfyUI node graphs from scratch;
- changing the approved writing and prompt-audit stage order.
