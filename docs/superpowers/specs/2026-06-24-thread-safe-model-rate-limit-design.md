# Thread-Safe Model Rate Limit Design

## Goal

Ensure that background workers sharing one `ModelCallExecutor` cannot start requests for the same OpenAI-compatible endpoint and model faster than the configured `requests_per_minute`, while allowing unrelated model endpoints to progress independently.

## Current Problem

`PersistentRunScheduler` can run multiple worker threads against the same orchestrator and model executor. The executor currently stores the latest request time in a shared dictionary without synchronization. Two workers can read the same previous timestamp, sleep concurrently, and then start requests at the same logical time, exceeding the configured rate.

## Chosen Approach

Use one lock per `base_url + model` rate-limit key:

- A small registry lock creates and retrieves per-key locks safely.
- A worker holds only its model key lock while calculating and waiting for its next request slot.
- The request timestamp is updated before the provider call starts.
- Retries pass through the same limiter because every attempt already invokes `_apply_rate_limit`.
- Requests with `requests_per_minute == 0` remain unlimited.

This keeps the existing fixed-interval behavior and configuration schema. It does not add burst semantics, distributed coordination, or a second queue.

## Concurrency Guarantees

- Two workers targeting the same endpoint and model cannot wait for the same slot concurrently.
- Workers targeting different endpoint/model keys do not block one another.
- All scheduler workers in one server process share the executor's rate-limit state.
- Multiple independent server processes are outside this local limiter's scope.

## Testing

Add deterministic thread tests using a blocking fake clock:

1. Prime a model key, then start two workers while the first is waiting. The maximum number of concurrent sleepers for that key must be one.
2. Prime two different model keys, then start one worker for each key. Both must be able to wait concurrently.
3. Retain the existing sequential spacing, retry, `Retry-After`, and usage tests.

## Documentation

Clarify in the README that local RPM spacing is thread-safe across scheduler workers but process-local. A future multi-process deployment will require a shared limiter such as Redis or provider-side quota coordination.
