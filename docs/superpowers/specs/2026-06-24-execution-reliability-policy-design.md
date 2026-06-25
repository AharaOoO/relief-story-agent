# Execution Reliability Policy Design

## Goal

Make batch automation safer by replacing text-based failure guessing with structured failure records and conservative recovery decisions. The pipeline order stays unchanged:

`chief_screenwriter -> deepseek_polish -> quality_gate -> gpt_prompt_writer -> gpt_prompt_audit -> optional gpt_prompt_reviser -> artifacts -> comfyui`

The default policy is conservative: unknown failures do not auto-retry. This protects local users from silent token and ComfyUI time waste.

## Current Problem

The current recovery layer mostly decides retryability from `failed_stage` and error text. Any failed run with a retry stage can be treated as retryable, even when the root cause is a missing template, invalid workflow mapping, model configuration error, quality gate failure, or model output contract violation.

That is risky for unattended local batch generation because a launcher can repeatedly spend model quota on failures that require operator action.

## Reference Practices

Durable workflow systems share the same broad ideas:

- Treat stages as restartable activities.
- Keep checkpoints after completed activities.
- Separate transient failures from permanent configuration or validation failures.
- Apply retries only to safe classes of errors.
- Preserve enough failure metadata for recovery UIs and operators.

This design keeps the service lightweight and local instead of adding Temporal or Prefect as a deployment dependency.

## Policy

### Failure Categories

The system records failures with one of these categories:

- `transient`: network disconnects, temporary provider errors, retryable transport failures.
- `throttled`: HTTP `429` and equivalent rate limit errors.
- `timeout`: model request timeout, ComfyUI output timeout, or other explicit timeout.
- `configuration`: missing model profile, missing API key environment variable, unreadable local files, invalid template path.
- `validation`: business rules such as script quality gate or prompt audit failure.
- `contract`: malformed model output, missing required stage fields, invalid shot contract.
- `external`: ComfyUI workflow or placeholder-map rejection that requires inspection.
- `cancelled`: user or batch cancellation.
- `unknown`: anything not classified. Under the default policy, this is not automatically retried.

### Retryability

Default automatic retry eligibility:

- Retryable: `transient`, `throttled`, `timeout`.
- Not retryable: `configuration`, `validation`, `contract`, `external`, `cancelled`, `unknown`.

Older runs without structured failure records keep the current fallback behavior, but new failures must prefer structured data.

## Data Model

Add a `FailureRecord` model with:

- `stage`
- `category`
- `code`
- `retryable`
- `source`
- `message`
- `exception_type`
- `http_status`
- `attempt_number`
- `details`
- `recorded_at`

Add to `RunState`:

- `failure_records: list[FailureRecord]`
- `last_failure: FailureRecord | None`

The public API already returns `RunState`, so these fields become visible in `GET /api/runs/{run_id}` automatically. Artifact manifests and recovery plans should include the same data for export and launcher use.

## Classifier

Create a small module, `failure_policy.py`, responsible for classification. It should not know the whole orchestrator. It accepts `stage` and an exception-like object, then returns a `FailureRecord`.

Classification priority:

1. Explicit cancellation exceptions become `cancelled`.
2. HTTP status codes classify as `throttled`, `transient`, `configuration`, or `unknown`.
3. Transport and timeout exception classes classify as `transient` or `timeout`.
4. Known business validation messages from quality gate, prompt audit, template loading, workflow mapping, and output contracts classify as non-retryable categories.
5. Everything else is `unknown` and non-retryable.

The text-message checks are a compatibility bridge for current generic `ValueError` usage. Future slices can replace more generic raises with typed domain exceptions.

## Recovery Behavior

`read_batch_artifact_index` and `build_batch_recovery_plan` should prefer `run.last_failure.retryable`.

When `last_failure` exists:

- Retryable failures recommend `retry_from_stage`.
- Configuration failures recommend `fix_template` or config inspection.
- External ComfyUI failures recommend workflow or placeholder-map inspection.
- Validation and contract failures recommend manual review.
- Unknown failures recommend manual review.

When `last_failure` is missing:

- Preserve the existing legacy inference from `failed_stage` and timeline diagnostics.

## Execution Budget Boundary

This phase defines the extension point but does not implement full budget enforcement.

The next reliability slice should add an `ExecutionPolicy` object for:

- total active execution budget per run;
- per-stage active budget;
- maximum automatic retries for unknown failures if the user later chooses a less conservative mode.

Budget enforcement should be cooperative. It can stop before starting a new stage or retry, but it should not forcibly kill a Python thread or corrupt a ComfyUI request.

## Testing Strategy

Unit tests should cover classifier behavior directly. Integration tests should verify:

- failed runs persist `last_failure`;
- recovery plans use structured retryability;
- unknown errors do not auto-retry under the default policy;
- old runs without failure records still get legacy recovery suggestions.

## Non-Goals

- Do not change pipeline stage order.
- Do not introduce Temporal, Prefect, Celery, or another runtime dependency.
- Do not implement full execution budget enforcement in this first slice.
- Do not remove existing recovery fallback for historical run files.
