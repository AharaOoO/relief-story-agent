# ComfyUI Precise Cancellation Design

## Goal

Make cancellation of a run responsive while it is waiting for ComfyUI, and cancel only the ComfyUI jobs owned by that run when the local ComfyUI version supports safe job-level cancellation.

## User-Visible Semantics

When `POST /api/runs/{run_id}/cancel` is called:

1. The run records `cancel_requested` immediately.
2. A ComfyUI polling stage observes that request without waiting for the full output timeout.
3. The Agent attempts to cancel every accepted `prompt_id` owned by the run.
4. The run ends as `cancelled` even if ComfyUI is offline or too old to cancel a running job.
5. The prompt IDs and cancellation diagnostics remain available for later inspection or output refresh.

The Agent never calls the global ComfyUI `/interrupt` endpoint automatically.

## Compatibility Strategy

Cancellation uses two safe layers:

1. **Modern API:** call `POST /api/jobs/{prompt_id}/cancel`. Current ComfyUI classifies the job atomically: a running job is interrupted only if that exact ID is still running, and a pending job is removed.
2. **Legacy fallback:** if the modern endpoint returns `404` or `405`, call `POST /queue` with `{"delete": [prompt_id]}`. This can remove a queued job but does not globally interrupt a running job.

Authentication errors, transport errors, and server errors are recorded. They do not trigger the legacy fallback because those responses do not prove the endpoint is unsupported.

## Components

### Poll Cancellation Signal

`wait_for_prompt_outputs` gains an optional `should_cancel` callback. It checks the callback before each history request and during interruptible sleep slices. A dedicated `ComfyUIWaitCancelled` exception carries no business failure meaning; the orchestrator converts it into the existing `RunCancellationRequested` path.

The interruptible sleep slice is capped at one second. This keeps cancellation latency bounded even when the configured output poll interval is much longer.

### Precise Remote Cancellation

`cancel_prompt_jobs` accepts a configuration, prompt IDs, and an optional HTTP client. It returns one structured result per prompt:

- `prompt_id`
- `strategy`: `job_api`, `legacy_queue`, or `none`
- `cancelled`
- `remote_status`
- `error`
- `checked_at`

The result describes what the server acknowledged. A `200 {"cancelled": false}` response is a successful idempotent no-op, not an exception.

### Persisted Run State

`RunState.comfyui_cancellations` stores cancellation results. The artifact manifest and run artifact index include the same list.

The orchestrator attempts remote cancellation only after a cancellation signal is observed during ComfyUI waiting. Cancelling during an earlier model stage does not contact ComfyUI because no accepted prompt IDs exist yet.

## Failure Handling

- Modern API `2xx`: record the JSON `cancelled` value.
- Modern API `404` or `405`: try the legacy queue deletion API.
- Legacy API `2xx`: record `strategy=legacy_queue` and `remote_status=queued_delete_requested`.
- Network or other HTTP failure: record `strategy=none`, preserve the error, and continue local cancellation.
- No prompt IDs: finish local cancellation without a remote call.

## Tests

1. Polling raises the cancellation exception before another history request.
2. Long poll sleeps are split so cancellation is observed within one second.
3. Modern job cancellation uses only the exact prompt ID.
4. `404`/`405` falls back to legacy queue deletion.
5. `500` and transport failures do not call `/interrupt` or unsafe fallback routes.
6. A scheduled run waiting for ComfyUI reaches `cancelled`, persists remote cancellation results, and retains prompt IDs.
7. Artifacts expose the cancellation audit.

## Deployment Boundary

This feature improves one Agent process controlling one or more jobs on a ComfyUI instance. It does not make the JSON state store safe for multiple Agent server processes sharing one state directory.
