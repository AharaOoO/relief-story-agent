from __future__ import annotations

import httpx
import json
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import RLock
from typing import Any

from .artifacts import write_artifact_manifest, write_run_artifacts, write_run_timeline_artifact
from .comfyui import (
    ComfyUIOutputTimeout,
    ComfyUIWaitCancelled,
    analyze_workflow_config,
    cancel_prompt_jobs,
    collect_prompt_outputs,
    detect_workflow_format,
    download_prompt_outputs,
    load_workflow,
    preview_storyboard_submission,
    submit_storyboard,
    upload_grid_image,
    wait_for_prompt_outputs,
)
from .content import (
    build_chief_screenwriter_prompt,
    build_deepseek_polish_prompt,
)
from .execution_policy import ExecutionPolicyExceeded, enforce_execution_policy
from .failure_policy import classify_failure
from .grid_image import (
    GridImageProvider,
    acquire_generated_grid_image,
    acquire_manual_grid_image,
    compile_four_grid_prompt,
    deterministic_comfyui_filename,
)
from .image_providers import OpenAICompatibleGridImageProvider
from .ltx_workflow import find_ltx_injection_points
from .model_config import ModelConfigRegistry
from .model_runtime import ModelCallExecutor
from .models import (
    BatchRetryRequest,
    BatchRunItem,
    BatchRunRequest,
    BatchRunState,
    GridImageAsset,
    GridImageAttempt,
    GridImageConfig,
    RunRequest,
    RunRetryRequest,
    RunState,
    ModelAttempt,
    ModelUsageSummary,
)
from .output_contracts import require_bool, require_list, require_mapping, require_shot_contract
from .pipeline import BASE_RUNTIME_STAGE_ORDER, retry_tail_for_stage, stage_ids_for_run
from .prompt_templates import (
    build_prompt_audit_prompt,
    build_prompt_reviser_prompt,
    build_prompt_writer_prompt,
)
from .providers import ModelProvider
from .quality import QualityGate
from .resource_limits import ExecutionResourceLimits


IMAGE_PROMPT_MAX_CHARS = 220
CHECKPOINT_COMPLETE = "__checkpoint_complete__"
PIPELINE_STAGES = list(BASE_RUNTIME_STAGE_ORDER)


class InMemoryRunStore:
    def __init__(self):
        self._runs: dict[str, RunState] = {}
        self._batches: dict[str, BatchRunState] = {}
        self._lock = RLock()

    def save(self, state: RunState) -> None:
        with self._lock:
            current = self._runs.get(state.run_id)
            if current and current.cancel_requested and state.status == "running":
                state.cancel_requested = True
            self._runs[state.run_id] = state.model_copy(deep=True)

    def get(self, run_id: str) -> RunState:
        with self._lock:
            if run_id not in self._runs:
                raise KeyError(run_id)
            return self._runs[run_id].model_copy(deep=True)

    def list_runs(self) -> list[RunState]:
        with self._lock:
            return [state.model_copy(deep=True) for state in self._runs.values()]

    def try_claim(self, run_id: str, owner: str, lease_seconds: float) -> RunState | None:
        with self._lock:
            if run_id not in self._runs:
                return None
            run = self._runs[run_id].model_copy(deep=True)
            if run.status == "queued":
                pass
            elif run.status == "running" and self._lease_expired(run.lease_expires_at):
                pass
            else:
                return None
            now = datetime.now(timezone.utc)
            run.status = "running"
            run.execution_attempt += 1
            run.lease_owner = owner
            run.lease_seconds = lease_seconds
            run.lease_expires_at = (
                now + timedelta(seconds=lease_seconds)
            ).isoformat()
            if not run.started_at:
                run.started_at = now.isoformat()
            self._runs[run_id] = run.model_copy(deep=True)
            return run

    def save_batch(self, state: BatchRunState) -> None:
        with self._lock:
            self._batches[state.batch_id] = state.model_copy(deep=True)

    def get_batch(self, batch_id: str) -> BatchRunState:
        with self._lock:
            if batch_id not in self._batches:
                raise KeyError(batch_id)
            return self._batches[batch_id].model_copy(deep=True)

    def list_batches(self) -> list[BatchRunState]:
        with self._lock:
            return [state.model_copy(deep=True) for state in self._batches.values()]

    @staticmethod
    def _lease_expired(value: str) -> bool:
        if not value:
            return True
        try:
            expires_at = datetime.fromisoformat(value)
        except ValueError:
            return True
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        return expires_at <= datetime.now(timezone.utc)


class RunCancellationRequested(RuntimeError):
    pass


class StoryRunOrchestrator:
    def __init__(
        self,
        *,
        provider: ModelProvider,
        store: InMemoryRunStore | None = None,
        quality_gate: QualityGate | None = None,
        model_executor: ModelCallExecutor | None = None,
        model_registry: ModelConfigRegistry | None = None,
        grid_image_provider: GridImageProvider | None = None,
        resource_limits: ExecutionResourceLimits | None = None,
        profile_store: Any = None,
    ):
        self.provider = provider
        self.store = store or InMemoryRunStore()
        self.quality_gate = quality_gate or QualityGate()
        self.model_executor = model_executor or ModelCallExecutor(provider)
        self.model_registry = model_registry or ModelConfigRegistry()
        self.grid_image_provider = grid_image_provider or OpenAICompatibleGridImageProvider()
        self.resource_limits = resource_limits or ExecutionResourceLimits()
        
        if profile_store is None:
            from .prompt_profiles import PromptProfileStore
            from pathlib import Path
            self.profile_store = PromptProfileStore(Path.home() / ".relief_story" / "profiles")
        else:
            self.profile_store = profile_store

    def create_run(self, request: RunRequest) -> RunState:
        existing = self._find_idempotent_run(request)
        if existing:
            return existing
        run = self.prepare_run(request)
        return self._start_prepared_run(run)

    def _start_prepared_run(self, run: RunState) -> RunState:
        if run.request.approval_mode == "manual":
            try:
                self._run_chief_screenwriter(run)
                run.status = "awaiting_approval"
                run.current_stage = "core_selection"
                run.add_log("core_selection", "Run created and waiting for core approval.")
            except Exception as exc:
                run.status = "failed"
                run.current_stage = "failed"
                run.error = str(exc)
                run.add_log("failed", str(exc), level="error")
            self.store.save(run)
            return run
        self._execute(run)
        return run

    def prepare_run(
        self,
        request: RunRequest,
        *,
        parent_batch_id: str = "",
    ) -> RunState:
        if not parent_batch_id:
            existing = self._find_idempotent_run(request)
            if existing:
                return existing
        profile_id = "system-default"
        if request.prompt_profile:
            profile_id = request.prompt_profile.profile_id
        try:
            profile = self.profile_store.get(profile_id)
            profile_version = profile.version
            profile_hash = profile.content_hash
            prompt_snapshot = profile.stages.model_dump()
            if request.prompt_profile and request.prompt_profile.stage_overrides:
                prompt_snapshot.update(request.prompt_profile.stage_overrides)
        except Exception as exc:
            raise ValueError(f"Failed to load prompt profile {profile_id!r}: {exc}") from exc

        now = datetime.now(timezone.utc).isoformat()
        run = RunState(
            run_id="run_" + uuid.uuid4().hex[:12],
            request=request,
            idempotency_key=request.idempotency_key,
            request_fingerprint=self._run_request_fingerprint(request),
            prompt_profile_id=profile_id,
            prompt_profile_version=profile_version,
            prompt_profile_hash=profile_hash,
            prompt_snapshot=prompt_snapshot,
            status="queued",
            current_stage="queued",
            parent_batch_id=parent_batch_id,
            queue_priority=request.queue_priority,
            queued_at=now,
        )
        run.add_log("queued", "Run queued for background execution.")
        run.add_event("run_queued", message="Run queued for background execution.")
        self.store.save(run)
        return run

    def _find_idempotent_run(self, request: RunRequest) -> RunState | None:
        if not request.idempotency_key:
            return None
        fingerprint = self._run_request_fingerprint(request)
        for run in self.store.list_runs():
            if run.idempotency_key != request.idempotency_key:
                continue
            if run.request_fingerprint and run.request_fingerprint != fingerprint:
                raise ValueError(
                    f"Run idempotency_key {request.idempotency_key!r} already exists "
                    "with a different request payload"
                )
            return run
        return None

    @staticmethod
    def _run_request_fingerprint(request: RunRequest) -> str:
        payload = request.model_dump(exclude={"idempotency_key"})
        return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

    def prepare_batch(self, request: BatchRunRequest) -> BatchRunState:
        existing = self._find_idempotent_batch(request)
        if existing:
            return existing
        batch = BatchRunState(
            batch_id="batch_" + uuid.uuid4().hex[:12],
            idempotency_key=request.idempotency_key,
            request_fingerprint=self._batch_request_fingerprint(request),
            failure_policy=request.failure_policy,
            status="queued",
        )
        self.store.save_batch(batch)
        for index, item_request in enumerate(request.resolved_items()):
            run = self.prepare_run(item_request, parent_batch_id=batch.batch_id)
            batch.items.append(
                BatchRunItem(
                    index=index,
                    run_id=run.run_id,
                    idea=item_request.idea,
                    status=run.status,
                    current_stage=run.current_stage,
                    queue_priority=run.queue_priority,
                )
            )
        batch.summary = self._summarize_batch(batch.items)
        batch.status = self._derive_batch_status(batch.summary)
        batch.updated_at = datetime.now(timezone.utc).isoformat()
        self.store.save_batch(batch)
        return batch

    def create_batch(self, request: BatchRunRequest) -> BatchRunState:
        existing = self._find_idempotent_batch(request)
        if existing:
            return existing
        batch = BatchRunState(
            batch_id="batch_" + uuid.uuid4().hex[:12],
            idempotency_key=request.idempotency_key,
            request_fingerprint=self._batch_request_fingerprint(request),
            failure_policy=request.failure_policy,
            status="running",
        )
        self.store.save_batch(batch)
        for index, item_request in enumerate(request.resolved_items()):
            run = self.prepare_run(item_request, parent_batch_id=batch.batch_id)
            run = self._start_prepared_run(run)
            batch.items.append(
                BatchRunItem(
                    index=index,
                    run_id=run.run_id,
                    idea=item_request.idea,
                    status=run.status,
                    current_stage=run.current_stage,
                    queue_priority=run.queue_priority,
                    error=run.error,
                )
            )
            batch.summary = self._summarize_batch(batch.items)
            batch.status = self._derive_batch_status(batch.summary)
            batch.updated_at = datetime.now(timezone.utc).isoformat()
            self.store.save_batch(batch)
        batch.status = self._derive_batch_status(batch.summary)
        batch.updated_at = datetime.now(timezone.utc).isoformat()
        self.store.save_batch(batch)
        return batch

    def _find_idempotent_batch(self, request: BatchRunRequest) -> BatchRunState | None:
        if not request.idempotency_key:
            return None
        fingerprint = self._batch_request_fingerprint(request)
        for batch in self.store.list_batches():
            if batch.idempotency_key != request.idempotency_key:
                continue
            if batch.request_fingerprint and batch.request_fingerprint != fingerprint:
                raise ValueError(
                    f"Batch idempotency_key {request.idempotency_key!r} already exists "
                    "with a different request payload"
                )
            return self.refresh_batch(batch.batch_id)
        return None

    @staticmethod
    def _batch_request_fingerprint(request: BatchRunRequest) -> str:
        payload = {
            "defaults": request.defaults.model_dump(),
            "failure_policy": request.failure_policy.model_dump(),
            "items": [item.model_dump() for item in request.resolved_items()],
        }
        return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

    def approve(self, run_id: str, approval_type: str = "continue", payload: dict[str, Any] | None = None) -> RunState:
        run = self.store.get(run_id)
        if run.status == "cancelled":
            return run
        if payload and "selected_core_index" in payload and run.core_candidates:
            run.selected_core = run.core_candidates[int(payload["selected_core_index"])]
        run.add_log("approval", f"Approved: {approval_type}")
        self._execute(run, resume=True)
        return run

    def retry(self, run_id: str, request: RunRetryRequest | None = None) -> RunState:
        run = self.store.get(run_id)
        retry_request = request or RunRetryRequest()
        start_stage = retry_request.from_stage or run.failed_stage or "chief_screenwriter"
        run.retry_count += 1
        run.add_log("retry", f"Retrying from stage: {start_stage}")
        self._execute(run, start_stage=start_stage)
        return run

    def retry_batch(self, batch_id: str, request: BatchRetryRequest | None = None) -> BatchRunState:
        batch = self.store.get_batch(batch_id)
        retry_request = request or BatchRetryRequest()
        for item in batch.items:
            if item.status != "failed":
                continue
            run = self.retry(
                item.run_id,
                RunRetryRequest(from_stage=retry_request.from_stage),
            )
            item.status = run.status
            item.current_stage = run.current_stage
            item.error = run.error
        batch.summary = self._summarize_batch(batch.items)
        batch.status = self._derive_batch_status(batch.summary)
        batch.updated_at = datetime.now(timezone.utc).isoformat()
        self.store.save_batch(batch)
        return batch

    def cancel_batch(self, batch_id: str) -> BatchRunState:
        batch = self.store.get_batch(batch_id)
        for item in batch.items:
            run = self.store.get(item.run_id)
            if run.status in {"completed", "failed", "cancelled"}:
                continue
            self.request_cancel(item.run_id)
        return self.refresh_batch(batch_id)

    def pause_batch(self, batch_id: str) -> BatchRunState:
        batch = self.store.get_batch(batch_id)
        batch.paused = True
        self.store.save_batch(batch)
        for item in batch.items:
            self.pause_run_if_queued(item.run_id)
        return self.refresh_batch(batch_id)

    def resume_batch(self, batch_id: str) -> BatchRunState:
        batch = self.store.get_batch(batch_id)
        batch.paused = False
        self.store.save_batch(batch)
        for item in batch.items:
            self.resume_run_if_paused(item.run_id)
        return self.refresh_batch(batch_id)

    def pause_run_if_queued(self, run_id: str) -> RunState:
        run = self.store.get(run_id)
        if run.status != "queued":
            return run
        run.status = "paused"
        run.current_stage = "paused"
        self._clear_lease(run)
        run.add_log("pause", "Run paused by batch control.")
        run.add_event("run_paused", message="Run paused by batch control.")
        self.store.save(run)
        return run

    def resume_run_if_paused(self, run_id: str) -> RunState:
        run = self.store.get(run_id)
        if run.status != "paused":
            return run
        run.status = "queued"
        run.current_stage = "queued"
        run.cancel_requested = False
        run.error = ""
        run.queued_at = datetime.now(timezone.utc).isoformat()
        self._clear_lease(run)
        run.add_log("resume", "Run resumed by batch control.")
        run.add_event("run_resumed", message="Run resumed by batch control.")
        self.store.save(run)
        return run

    def cancel(self, run_id: str) -> RunState:
        run = self.store.get(run_id)
        run.status = "cancelled"
        run.current_stage = "cancelled"
        run.add_log("cancel", "Run cancelled by API caller.")
        self.store.save(run)
        return run

    def execute_scheduled(self, run_id: str) -> RunState:
        run = self.store.get(run_id)
        if run.cancel_requested:
            return self._finish_cancelled(run)
        if (
            run.request.approval_mode == "manual"
            and not run.core_candidates
            and not run.resume_stage
        ):
            try:
                self._check_cancelled(run)
                self._renew_lease(run)
                self._run_chief_screenwriter(run)
                run.last_completed_stage = "chief_screenwriter"
                run.status = "awaiting_approval"
                run.current_stage = "core_selection"
                run.add_log("core_selection", "Waiting for core approval.")
                self._clear_lease(run)
                self.store.save(run)
            except RunCancellationRequested:
                self._finish_cancelled(run)
            except Exception as exc:
                self._finish_failed(run, exc)
            return run

        start_stage = run.resume_stage or self._recovery_start_stage(run)
        run.resume_stage = ""
        if start_stage == CHECKPOINT_COMPLETE:
            self._finish_completed(run)
            return run
        self._execute(run, start_stage=start_stage)
        return run

    def queue_approval(
        self,
        run_id: str,
        payload: dict[str, Any] | None = None,
    ) -> RunState:
        run = self.store.get(run_id)
        if payload and "selected_core_index" in payload and run.core_candidates:
            run.selected_core = run.core_candidates[int(payload["selected_core_index"])]
        run.status = "queued"
        run.current_stage = "queued"
        run.resume_stage = "deepseek_polish"
        run.cancel_requested = False
        run.error = ""
        self._clear_lease(run)
        run.add_log("approval", "Approval accepted and continuation queued.")
        run.add_event("approval_queued", message="Approval accepted and continuation queued.")
        self.store.save(run)
        return run

    def queue_retry(
        self,
        run_id: str,
        request: RunRetryRequest | None = None,
    ) -> RunState:
        run = self.store.get(run_id)
        retry_request = request or RunRetryRequest()
        run.resume_stage = retry_request.from_stage or run.failed_stage or "chief_screenwriter"
        run.retry_count += 1
        run.status = "queued"
        run.current_stage = "queued"
        run.cancel_requested = False
        run.error = ""
        self._clear_lease(run)
        run.add_log("retry", f"Retry queued from stage: {run.resume_stage}")
        run.add_event("retry_queued", stage=run.resume_stage, message=f"Retry queued from stage: {run.resume_stage}")
        self.store.save(run)
        return run

    def request_cancel(self, run_id: str) -> RunState:
        run = self.store.get(run_id)
        run.cancel_requested = True
        if run.status in {"queued", "awaiting_approval", "failed"}:
            return self._finish_cancelled(run)
        run.add_log("cancel", "Cancellation requested; waiting for stage boundary.")
        run.add_event("cancel_requested", message="Cancellation requested; waiting for stage boundary.")
        self.store.save(run)
        return run

    def refresh_batch(self, batch_id: str) -> BatchRunState:
        batch, _ = self.snapshot_batch(batch_id)
        return batch

    def snapshot_batch(
        self,
        batch_id: str,
        *,
        tolerate_missing_runs: bool = False,
    ) -> tuple[BatchRunState, list[RunState]]:
        batch = self.store.get_batch(batch_id)
        runs: list[RunState] = []
        for item in batch.items:
            try:
                run = self.store.get(item.run_id)
            except KeyError:
                if not tolerate_missing_runs:
                    raise
                item.error = item.error or "run not found"
                continue
            runs.append(run)
            item.status = run.status
            item.current_stage = run.current_stage
            item.queue_priority = run.queue_priority
            item.error = run.error
        batch.summary = self._summarize_batch(batch.items)
        batch.status = self._derive_batch_status(batch.summary)
        batch.updated_at = datetime.now(timezone.utc).isoformat()
        self.store.save_batch(batch)
        return batch, runs

    def refresh_comfyui_outputs(self, run_id: str) -> RunState:
        run = self.store.get(run_id)
        if not run.request.comfyui:
            raise ValueError("ComfyUI is not configured for this run.")
        if not run.comfyui_prompt_ids:
            run.add_log("comfyui_outputs", "No ComfyUI prompt ids to refresh.", level="warn")
            run.comfyui_outputs = []
        else:
            run.comfyui_outputs = collect_prompt_outputs(
                run.request.comfyui,
                run.comfyui_prompt_ids,
            )
            if run.comfyui_outputs:
                artifact_dir = write_artifact_manifest(run)
                run.comfyui_outputs = download_prompt_outputs(
                    run.comfyui_outputs,
                    artifact_dir,
                )
            run.add_log(
                "comfyui_outputs",
                f"Recovered {len(run.comfyui_outputs)} ComfyUI output file(s).",
            )
        run.add_event(
            "comfyui_outputs_refreshed",
            stage="comfyui",
            data={"count": len(run.comfyui_outputs)},
        )
        if run.artifact_dir or run.request.output_root:
            write_artifact_manifest(run)
        self.store.save(run)
        return run

    def _execute(self, run: RunState, resume: bool = False, start_stage: str | None = None) -> None:
        try:
            run.status = "running"
            run.error = ""
            run.failed_stage = ""
            for stage in self._stage_sequence(run, resume=resume, start_stage=start_stage):
                self._check_cancelled(run)
                self._renew_lease(run)
                self._check_execution_policy(run, stage)
                run.add_event("stage_started", stage=stage)
                self.store.save(run)
                self._run_stage(run, stage)
                run.last_completed_stage = stage
                run.add_event("stage_completed", stage=stage)
                self.store.save(run)
            self._check_cancelled(run)
            self._finish_completed(run)
        except RunCancellationRequested:
            self._finish_cancelled(run)
        except Exception as exc:
            self._finish_failed(run, exc)
        finally:
            self.store.save(run)

    def _check_cancelled(self, run: RunState) -> None:
        persisted = self.store.get(run.run_id)
        if persisted.cancel_requested:
            run.cancel_requested = True
            raise RunCancellationRequested("run cancellation requested")

    def _check_execution_policy(self, run: RunState, stage: str) -> None:
        try:
            enforce_execution_policy(run, stage)
        except ExecutionPolicyExceeded as exc:
            run.current_stage = stage
            run.add_event(
                "execution_policy_blocked",
                stage=stage,
                message=str(exc),
                data=exc.details,
            )
            self.store.save(run)
            raise

    def _renew_lease(self, run: RunState) -> None:
        if not run.lease_owner:
            return
        run.lease_expires_at = (
            datetime.now(timezone.utc) + timedelta(seconds=run.lease_seconds)
        ).isoformat()
        self.store.save(run)

    def _finish_cancelled(self, run: RunState) -> RunState:
        run.status = "cancelled"
        run.current_stage = "cancelled"
        run.finished_at = datetime.now(timezone.utc).isoformat()
        self._clear_lease(run)
        run.add_log("cancelled", "Run cancelled at a safe stage boundary.")
        run.add_event("run_cancelled", message="Run cancelled at a safe stage boundary.")
        self._refresh_terminal_artifacts(run)
        self.store.save(run)
        return run

    def _finish_completed(self, run: RunState) -> RunState:
        run.status = "completed"
        run.current_stage = "completed"
        run.finished_at = datetime.now(timezone.utc).isoformat()
        self._clear_lease(run)
        run.add_log("completed", "Run completed.")
        run.add_event("run_completed", message="Run completed.")
        self._refresh_terminal_artifacts(run)
        self.store.save(run)
        return run

    def _finish_failed(self, run: RunState, exc: Exception) -> RunState:
        if run.current_stage != "failed":
            run.failed_stage = run.current_stage
        failure = classify_failure(run.failed_stage or run.current_stage, exc)
        run.last_failure = failure
        run.failure_records.append(failure)
        run.status = "failed"
        run.current_stage = "failed"
        run.error = str(exc)
        run.finished_at = datetime.now(timezone.utc).isoformat()
        self._clear_lease(run)
        run.add_log("failed", str(exc), level="error")
        run.add_event("run_failed", stage=run.failed_stage, message=str(exc))
        self._refresh_terminal_artifacts(run)
        self.store.save(run)
        return run

    def _refresh_terminal_artifacts(self, run: RunState) -> None:
        if not run.artifact_dir and not run.request.output_root:
            return
        write_run_timeline_artifact(run)
        write_artifact_manifest(run)

    @staticmethod
    def _clear_lease(run: RunState) -> None:
        run.lease_owner = ""
        run.lease_expires_at = ""

    def _recovery_start_stage(self, run: RunState) -> str | None:
        stages = self._stage_sequence(run)
        if run.last_completed_stage and run.last_completed_stage in stages:
            checkpoint_index = stages.index(run.last_completed_stage)
            if run.current_stage == run.last_completed_stage:
                next_index = checkpoint_index + 1
                return (
                    stages[next_index]
                    if next_index < len(stages)
                    else CHECKPOINT_COMPLETE
                )
        if run.current_stage not in {"queued", "running", "failed"}:
            if run.current_stage:
                return run.current_stage
        if run.last_completed_stage:
            if run.last_completed_stage in stages:
                index = stages.index(run.last_completed_stage) + 1
                return stages[index] if index < len(stages) else CHECKPOINT_COMPLETE
        return None

    def _stage_sequence(self, run: RunState, *, resume: bool = False, start_stage: str | None = None) -> list[str]:
        requires_grid = self._requires_grid_asset(run)
        writes_artifacts = bool(run.request.output_root or requires_grid)
        comfyui_enabled = bool(run.request.comfyui and run.request.comfyui.enabled)
        stages = stage_ids_for_run(
            requires_grid_asset=requires_grid,
            writes_artifacts=writes_artifacts,
            comfyui_enabled=comfyui_enabled,
        )
        if start_stage:
            return retry_tail_for_stage(
                start_stage,
                requires_grid_asset=requires_grid,
                writes_artifacts=writes_artifacts,
                comfyui_enabled=comfyui_enabled,
            )
        if resume and run.core_candidates:
            return stages[1:]
        return stages

    def _requires_grid_asset(self, run: RunState) -> bool:
        config = run.request.comfyui
        if not config or not config.enabled or not config.workflow_api_path:
            return False
        workflow = load_workflow(config.workflow_api_path)
        if detect_workflow_format(workflow) != "litegraph":
            return False
        return find_ltx_injection_points(workflow).grid_image_node_id is not None

    def _run_stage(self, run: RunState, stage: str) -> None:
        stage_handlers = {
            "chief_screenwriter": self._run_chief_screenwriter,
            "deepseek_polish": self._run_deepseek_polish,
            "quality_gate": self._run_quality_gate,
            "gpt_prompt_writer": self._run_prompt_writer,
            "gpt_prompt_audit": self._run_prompt_audit,
            "gpt_prompt_reviser": self._run_prompt_reviser,
            "final_prompts": self._run_final_prompts,
            "four_grid_asset": self._run_four_grid_asset,
            "artifacts": self._write_artifacts,
            "comfyui": self._run_comfyui,
        }
        stage_handlers[stage](run)

    @staticmethod
    def _summarize_batch(items: list[BatchRunItem]) -> dict[str, int]:
        summary = {
            "total": len(items),
            "paused": 0,
            "completed": 0,
            "failed": 0,
            "cancelled": 0,
            "awaiting_approval": 0,
            "running": 0,
        }
        for item in items:
            if item.status in summary:
                summary[item.status] += 1
            elif item.status in {"queued"}:
                summary["running"] += 1
        return summary

    @staticmethod
    def _derive_batch_status(summary: dict[str, int]) -> str:
        total = summary.get("total", 0)
        if total == 0:
            return "queued"
        if summary.get("running", 0):
            return "running"
        if summary.get("paused", 0):
            return "paused"
        if summary.get("failed", 0) and summary.get("failed", 0) == total:
            return "failed"
        if summary.get("cancelled", 0) and summary.get("cancelled", 0) == total:
            return "cancelled"
        if summary.get("failed", 0) or summary.get("cancelled", 0):
            return "partial_failed"
        if summary.get("awaiting_approval", 0):
            return "awaiting_approval"
        if summary.get("completed", 0) == total:
            return "completed"
        return "running"

    def _run_chief_screenwriter(self, run: RunState) -> None:
        run.current_stage = "chief_screenwriter"
        run.add_log("chief_screenwriter", "Generating core candidates and draft script.")
        idea_text = run.request.input_spec.content if run.request.input_spec.content else run.request.idea
        prompt = build_chief_screenwriter_prompt(
            idea=idea_text,
            audience_pressure=run.request.creation_spec.audience,
            preferred_style=run.request.creation_spec.style_preset_id,
            preferred_series=run.request.creation_spec.series_name,
            duration_seconds=run.request.creation_spec.duration_seconds,
            template=run.prompt_snapshot.get("chief_screenwriter"),
        )
        payload = self._generate_model_json(
            run,
            stage="chief_screenwriter",
            prompt=prompt,
        )
        run.core_candidates = list(require_list(payload, "chief_screenwriter", "core_candidates"))
        selected_index = int(payload.get("selected_core_index") or 0)
        if run.core_candidates:
            run.selected_core = run.core_candidates[selected_index]
        run.script = dict(require_mapping(payload, "chief_screenwriter", "draft_script"))

    def _run_deepseek_polish(self, run: RunState) -> None:
        run.current_stage = "deepseek_polish"
        run.add_log("deepseek_polish", "Polishing script without increasing stimulation.")
        prompt = build_deepseek_polish_prompt(
            {
                "selected_core": run.selected_core,
                "draft_script": run.script,
            },
            template=run.prompt_snapshot.get("deepseek_polish"),
        )
        payload = self._generate_model_json(
            run,
            stage="deepseek_polish",
            prompt=prompt,
        )
        polished = dict(require_mapping(payload, "deepseek_polish", "polished_script"))
        if run.script.get("core_sentence") and polished.get("core_sentence") != run.script.get("core_sentence"):
            raise ValueError("deepseek_polish changed the core_sentence")
        run.script = polished

    def _run_quality_gate(self, run: RunState) -> None:
        run.current_stage = "quality_gate"
        run.add_log("quality_gate", "Checking polished script quality gates.")
        gate = self.quality_gate.check_script_object(run.script)
        if not gate.passed:
            raise ValueError(f"deepseek_polish quality gate failed: {gate.issues}")

    def _run_prompt_writer(self, run: RunState) -> None:
        run.current_stage = "gpt_prompt_writer"
        run.add_log("gpt_prompt_writer", "Generating concise storyboard prompts.")
        prompt = build_prompt_writer_prompt(
            request=run.request,
            script=run.script,
            workflow_context=self._build_workflow_context(run.request),
            template=run.prompt_snapshot.get("gpt_prompt_writer"),
        )
        payload = self._generate_model_json(
            run,
            stage="gpt_prompt_writer",
            prompt=prompt,
        )
        shots = self._normalize_shots(
            list(require_list(payload, "gpt_prompt_writer", "shots")),
            stage="gpt_prompt_writer",
        )
        run.storyboard = shots
        run.final_storyboard = []

    def _run_prompt_audit(self, run: RunState) -> None:
        run.current_stage = "gpt_prompt_audit"
        run.add_log("gpt_prompt_audit", "Checking prompt spatial, axis, motion, and story logic.")
        prompt = build_prompt_audit_prompt(
            request=run.request,
            script=run.script,
            storyboard=run.storyboard,
            workflow_context=self._build_workflow_context(run.request),
            template=run.prompt_snapshot.get("gpt_prompt_audit"),
        )
        audit = self._generate_model_json(
            run,
            stage="gpt_prompt_audit",
            prompt=prompt,
        )
        run.prompt_audit = dict(audit)
        if require_bool(audit, "gpt_prompt_audit", "passed"):
            run.final_storyboard = list(run.storyboard)
            return
        self._run_prompt_reviser(run)

    def _run_prompt_reviser(self, run: RunState) -> None:
        run.current_stage = "gpt_prompt_reviser"
        run.add_log("gpt_prompt_reviser", "Revising prompt issues once from audit instructions.")
        prompt = build_prompt_reviser_prompt(
            request=run.request,
            script=run.script,
            storyboard=run.storyboard,
            audit=run.prompt_audit,
            workflow_context=self._build_workflow_context(run.request),
            template=run.prompt_snapshot.get("gpt_prompt_reviser"),
        )
        payload = self._generate_model_json(
            run,
            stage="gpt_prompt_reviser",
            prompt=prompt,
        )
        run.final_storyboard = self._normalize_shots(
            list(require_list(payload, "gpt_prompt_reviser", "shots")),
            stage="gpt_prompt_reviser",
        )
        run.prompt_revision_count = 1

    def _run_final_prompts(self, run: RunState) -> None:
        run.current_stage = "final_prompts"
        if not run.final_storyboard:
            raise ValueError("final_prompts requires a finalized storyboard")
        run.add_log("final_prompts", "Final prompts are ready for grid image and video generation.")

    def _acquire_generated_grid_asset(
        self,
        run: RunState,
        *,
        artifact_dir: Path,
        image_config: GridImageConfig,
    ) -> GridImageAsset:
        for attempt_number in range(1, image_config.max_attempts + 1):
            attempt = GridImageAttempt(attempt_number=attempt_number)
            run.grid_image_attempts.append(attempt)
            self.store.save(run)
            try:
                with self.resource_limits.image_generation():
                    asset = acquire_generated_grid_image(
                        self.grid_image_provider,
                        artifact_dir=artifact_dir,
                        prompt=run.grid_image_prompt,
                        config=image_config,
                    )
            except Exception as exc:
                attempt.status = "failed"
                attempt.error_type = type(exc).__name__
                attempt.error_message = str(exc)
                attempt.finished_at = datetime.now(timezone.utc).isoformat()
                self.store.save(run)
                failure = classify_failure("four_grid_asset", exc)
                if not failure.retryable or attempt_number == image_config.max_attempts:
                    raise
                time.sleep(min(2 ** (attempt_number - 1), 8))
                continue
            attempt.status = "succeeded"
            attempt.finished_at = datetime.now(timezone.utc).isoformat()
            self.store.save(run)
            return asset
        raise RuntimeError("grid image generation exhausted without a result")

    def _run_four_grid_asset(self, run: RunState) -> None:
        run.current_stage = "four_grid_asset"
        config = run.request.comfyui
        if not config:
            raise ValueError("ComfyUI config is required for four_grid_asset")
        image_config = config.grid_image
        storyboard = run.final_storyboard or run.storyboard
        artifact_dir = Path(run.request.output_root or "runs") / run.run_id
        artifact_dir.mkdir(parents=True, exist_ok=True)
        run.artifact_dir = str(artifact_dir)

        if not run.grid_image_prompt:
            run.grid_image_prompt = compile_four_grid_prompt(
                storyboard,
                max_chars=image_config.prompt_max_chars,
            )
            run.grid_image_checkpoint = "prompt_compiled"
            self.store.save(run)

        if run.grid_image_asset is None:
            if image_config.effective_mode() == "manual_override":
                run.grid_image_asset = acquire_manual_grid_image(
                    image_config.manual_image_path or "",
                    artifact_dir=artifact_dir,
                    prompt=run.grid_image_prompt,
                    config=image_config,
                )
            else:
                run.grid_image_asset = self._acquire_generated_grid_asset(
                    run,
                    artifact_dir=artifact_dir,
                    image_config=image_config,
                )
            run.grid_image_checkpoint = "image_acquired"
            self.store.save(run)

        run.grid_image_checkpoint = "image_validated"
        asset = run.grid_image_asset
        if asset.upload_status != "accepted":
            destination = deterministic_comfyui_filename(
                run.run_id,
                asset.sha256,
                asset.mime_type,
            )
            try:
                asset.comfyui_filename = upload_grid_image(
                    config.endpoint,
                    asset.local_path,
                    destination_name=destination,
                )
                asset.upload_status = "accepted"
                asset.upload_error = ""
            except httpx.TransportError as exc:
                asset.comfyui_filename = destination
                asset.upload_status = "unknown"
                asset.upload_error = str(exc)
                self.store.save(run)
                raise
            run.grid_image_checkpoint = "image_uploaded"
            self.store.save(run)

        preview = preview_storyboard_submission(
            config,
            storyboard,
            run.run_id,
            duration_seconds=run.request.duration_seconds,
            grid_image_asset=asset,
        )
        run.grid_image_replacements = preview["items"][0]["replacements"]
        run.grid_image_checkpoint = "workflow_patched"
        self.store.save(run)

    def _run_comfyui(self, run: RunState) -> None:
        run.current_stage = "comfyui"
        run.add_log("comfyui", "Submitting storyboard shots to ComfyUI.")
        assert run.request.comfyui is not None

        def persist_submissions(submissions):
            run.comfyui_submissions = submissions
            run.comfyui_prompt_ids = [
                item.prompt_id for item in submissions if item.status == "accepted"
            ]
            self.store.save(run)

        with self.resource_limits.comfyui_submission():
            run.comfyui_submissions = submit_storyboard(
                run.request.comfyui,
                run.final_storyboard or run.storyboard,
                run.run_id,
                duration_seconds=run.request.duration_seconds,
                existing_submissions=run.comfyui_submissions,
                on_update=persist_submissions,
                grid_image_asset=run.grid_image_asset,
            )
        persist_submissions(run.comfyui_submissions)
        if run.request.comfyui.wait_for_completion and run.comfyui_prompt_ids:
            run.add_log("comfyui", "Waiting for ComfyUI outputs.")
            try:
                run.comfyui_outputs = wait_for_prompt_outputs(
                    run.request.comfyui,
                    run.comfyui_prompt_ids,
                    should_cancel=lambda: self.store.get(run.run_id).cancel_requested,
                )
            except ComfyUIWaitCancelled as exc:
                run.cancel_requested = True
                run.comfyui_cancellations = cancel_prompt_jobs(
                    run.request.comfyui,
                    run.comfyui_prompt_ids,
                )
                run.add_log(
                    "comfyui",
                    "Cancellation observed while waiting; requested precise remote job cancellation.",
                )
                run.add_event(
                    "comfyui_cancellation_requested",
                    stage="comfyui",
                    data={
                        "results": [
                            item.model_dump() for item in run.comfyui_cancellations
                        ]
                    },
                )
                if run.artifact_dir or run.request.output_root:
                    write_artifact_manifest(run)
                self.store.save(run)
                raise RunCancellationRequested(
                    "run cancellation requested while waiting for ComfyUI"
                ) from exc
            except ComfyUIOutputTimeout as exc:
                run.comfyui_diagnostics = exc.diagnostics
                run.add_log("comfyui", str(exc), level="warn")
                if run.artifact_dir or run.request.output_root:
                    write_artifact_manifest(run)
                self.store.save(run)
                raise
            run.comfyui_diagnostics = {}
            if run.request.comfyui.download_outputs:
                artifact_dir = write_artifact_manifest(run)
                run.comfyui_outputs = download_prompt_outputs(
                    run.comfyui_outputs,
                    artifact_dir,
                )
            run.add_event(
                "comfyui_outputs_refreshed",
                stage="comfyui",
                data={"count": len(run.comfyui_outputs)},
            )
            if run.artifact_dir or run.request.output_root:
                write_artifact_manifest(run)
            self.store.save(run)

    def _write_artifacts(self, run: RunState) -> None:
        run.current_stage = "artifacts"
        artifact_dir = write_run_artifacts(run)
        run.add_log("artifacts", f"Wrote run artifacts to {artifact_dir}.")

    def _generate_model_json(
        self,
        run: RunState,
        *,
        stage: str,
        prompt: str,
    ) -> dict[str, Any]:
        result = self.model_executor.execute(
            stage=stage,
            prompt=prompt,
            config=self.model_registry.resolve(
                stage,
                inline=run.request.model_configs.get(stage),
                profile_override=run.request.model_profiles.get(stage),
            ),
            record_attempt=lambda attempt: self._record_model_attempt(run, attempt),
        )
        return result.payload

    def _record_model_attempt(self, run: RunState, attempt: ModelAttempt) -> None:
        persisted = self.store.get(run.run_id)
        if persisted.cancel_requested:
            run.cancel_requested = True
        for index, current in enumerate(run.model_attempts):
            if current.attempt_id == attempt.attempt_id:
                run.model_attempts[index] = attempt
                break
        else:
            run.model_attempts.append(attempt)
        terminal = [item for item in run.model_attempts if item.status != "running"]
        run.model_usage_summary = ModelUsageSummary(
            total_requests=sum(item.status == "succeeded" for item in terminal),
            total_attempts=len(terminal),
            retry_count=sum(item.status == "retryable_failed" for item in terminal),
            prompt_tokens=sum(item.prompt_tokens for item in terminal),
            completion_tokens=sum(item.completion_tokens for item in terminal),
            total_tokens=sum(item.total_tokens for item in terminal),
            estimated_cost_usd=sum(item.estimated_cost_usd for item in terminal),
        )
        self.store.save(run)

    def _normalize_shots(self, shots: list[Any], *, stage: str) -> list[dict[str, Any]]:
        if not 1 <= len(shots) <= 8:
            raise ValueError(f"{stage} must return between 1 and 8 shots")
        normalized: list[dict[str, Any]] = []
        for shot in require_shot_contract(shots, stage):
            current = dict(shot)
            image_prompt = str(current.get("image_prompt") or "")
            if len(image_prompt) > IMAGE_PROMPT_MAX_CHARS:
                current["image_prompt"] = image_prompt[:IMAGE_PROMPT_MAX_CHARS].rstrip()
                comfyui_inputs = dict(current.get("comfyui_inputs") or {})
                if "positive" in comfyui_inputs:
                    comfyui_inputs["positive"] = str(comfyui_inputs["positive"])[:IMAGE_PROMPT_MAX_CHARS].rstrip()
                current["comfyui_inputs"] = comfyui_inputs
            normalized.append(current)
        return normalized

    @staticmethod
    def _build_workflow_context(request: RunRequest) -> str:
        if not request.comfyui or not request.comfyui.workflow_api_path:
            return "No ComfyUI workflow configured."
        try:
            analysis = analyze_workflow_config(request.comfyui)
            parts = [
                f"workflow_format={analysis.get('workflow_format', '')}",
                f"adapter_mode={analysis.get('adapter_mode', '')}",
                f"node_count={analysis.get('node_count', 0)}",
                f"api_node_count={analysis.get('api_node_count', 0)}",
                f"placeholder_map_required={str(bool(analysis.get('placeholder_map_required'))).lower()}",
            ]
            points = analysis.get("ltx_injection_points") or {}
            if points:
                parts.extend(
                    [
                        f"ltx_json_node={points.get('json_node_id')}",
                        f"seed_node={points.get('seed_node_id')}",
                        f"filename_prefix_node={points.get('filename_prefix_node_id')}",
                    ]
                )
            placeholder_keys = analysis.get("placeholder_map_keys") or []
            if placeholder_keys:
                parts.append(f"placeholder_map_keys={','.join(placeholder_keys)}")
            warnings = analysis.get("warnings") or []
            if warnings:
                parts.append(f"warnings={' | '.join(str(item) for item in warnings)}")
            return "ComfyUI workflow analysis: " + "; ".join(parts) + "."
        except Exception as exc:
            return f"ComfyUI workflow context unavailable: {exc}"
