# Relief Story Agent Current Status

Last updated: 2026-06-27

This file is the short, GitHub-visible status page for reviewers. It exists to
avoid judging the project from an old README, a single UI idea, or an early
prototype snapshot.

## Current Summary

Relief Story Agent is no longer just a loose story agent prototype. The current
branch contains an API-first backend with pipeline orchestration, ComfyUI/LTX
workflow adaptation, batch scheduling, recovery/export/acceptance evidence, and
a starter RunningHub cloud-generation mode.

It is not yet a fully release-ready creator product because the final real
acceptance evidence is still missing: real model probes, one completed local
video, a real 3-5 item batch, restart recovery drill, export validation, and
final `ready_for_release=true`.

Latest verified test baseline:

```text
python -m pytest relief_story_agent/tests -q
446 passed
```

Latest readiness baseline:

```text
ready_for_configuration=true
ready_for_real_runs=false
ready_for_release=false
```

The remaining real-run blockers are model API key environment variables and
missing final acceptance evidence, not missing backend architecture.

## What Exists Today

### Workflow Layer

Implemented:

- fixed pipeline schema: `chief_screenwriter -> deepseek_polish -> quality_gate -> gpt_prompt_writer -> gpt_prompt_audit -> gpt_prompt_reviser -> final_prompts -> four_grid_asset -> artifacts -> comfyui`
- orchestrator state machine
- persistent run/batch state
- local acceptance evidence gates
- `local-readiness` aggregate status for launchers and future UI

Important nuance:

- This is an internal Python/FastAPI workflow layer, not a Temporal/Prefect style
  external durable workflow engine.

### ComfyUI Adapter Layer

Implemented:

- ComfyUI endpoint normalization and `/queue` checks
- workflow discovery
- workflow analysis
- LiteGraph and ComfyUI API JSON support
- LTX 2.3 node-field injection and workflow patching
- seed and filename-prefix injection
- four-grid image upload and reuse
- `/object_info` runtime node validation
- `/prompt` submission
- `/history` output inspection and optional download
- smoke dry-run and real `/prompt` acceptance evidence

Core files:

- `relief_story_agent/comfyui.py`
- `relief_story_agent/ltx_workflow.py`
- `relief_story_agent/comfyui_outputs.py`
- `relief_story_agent/smoke_comfyui.py`

### Batch System

Implemented:

- batch plan
- batch create
- persistent batch state
- scheduler queue
- worker concurrency limits
- pause/resume/cancel/retry
- batch timeline
- batch health
- batch artifact index
- export and validation

Still missing:

- final real 3-5 item batch evidence on the user's actual model/API/GPU setup.

### Production Stability Systems

Implemented:

- idempotency keys for run and batch requests
- persistent state backend
- scheduler leases and recovery
- failure categorization
- retry and resume from selected stages
- ComfyUI duplicate-submission avoidance
- execution policy budgets
- model retry/backoff/rate-limit tracking
- seed injection/tracking for ComfyUI workflows
- artifact manifests
- acceptance evidence revalidation
- structured CLI/API error responses instead of tracebacks

Still missing or not yet production-grade:

- complete prompt/result cache layer
- distributed multi-machine workers
- long-running production observability dashboard
- cloud/local output unification for imported RunningHub videos
- real load/soak test evidence

### RunningHub Cloud Generation Mode 2

Starter implemented:

- advanced workflow API payload contract: `workflowId + nodeInfoList`
- `RUNNINGHUB_API_KEY` env-based secret handling
- dry-run payload redaction
- submit/status/outputs helpers
- CLI commands:
  - `runninghub-check`
  - `runninghub-submit`
  - `runninghub-status`
  - `runninghub-outputs`
- API endpoints:
  - `POST /api/runninghub/check`
  - `POST /api/runninghub/submit`
  - `POST /api/runninghub/status`
  - `POST /api/runninghub/outputs`

Still missing:

- real RunningHub API key
- real uploaded/copied `workflowId`
- node mapping for the user's cloud workflow
- real cloud task acceptance evidence

Design and plan:

- `docs/superpowers/specs/2026-06-27-runninghub-cloud-generation-design.md`
- `docs/superpowers/plans/2026-06-27-runninghub-cloud-generation.md`

### UI Status

Not production-grade yet.

The backend is intentionally API-first. The future UI should be a creator
operations tool, not a simple story-agent chat screen. It should expose:

- generation mode selector: Local ComfyUI / RunningHub Cloud
- local readiness and model-key checks
- workflow selection and validation
- batch queue and progress timeline
- failure recovery actions
- artifact/output review
- export validation

## What Must Not Be Claimed Yet

Do not claim the project is release-ready until all of these are true:

- `model-check --real-run` passes for configured text and image providers.
- one real local run completes with a validated local video file.
- a real 3-5 item batch is executed and recorded.
- restart recovery is demonstrated with before/after recovery-plan evidence.
- export, zip, checksum, and validation reports pass.
- `acceptance-status` returns `ready_for_release=true`.
- `local-readiness` returns `ready_for_release=true`.

## Review Shortcut

If someone says the project has no workflow layer, no ComfyUI adapter, no batch
system, or no stability layer, they are likely reviewing an old branch or only
looking at an early UI concept.

The more accurate current critique is:

```text
The backend architecture is substantially built, but final real-world evidence
and production-grade UI are still pending.
```
