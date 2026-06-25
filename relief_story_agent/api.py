from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Response

from .artifacts import (
    export_batch_artifact_package,
    read_batch_artifact_index,
    read_run_artifact_index,
    validate_batch_export_package,
    validate_batch_export_zip,
)
from .config_validation import (
    diagnose_batch_configuration,
    diagnose_run_configuration,
    validate_batch_configuration,
    validate_run_configuration,
)
from .comfyui import analyze_workflow_config, connect_comfyui, preview_storyboard_submission
from .metrics import build_batch_health_report, build_system_metrics
from .models import (
    BatchExportRequest,
    BatchExportValidationRequest,
    BatchExportZipValidationRequest,
    BatchRecoveryExecuteRequest,
    BatchRetryRequest,
    BatchRunRequest,
    BatchRunState,
    ComfyUIConnectionRequest,
    ComfyUIPreviewRequest,
    ComfyUIWorkflowAnalysisRequest,
    RunRequest,
    RunRetryRequest,
    RunState,
)
from .orchestrator import StoryRunOrchestrator
from .pipeline import build_pipeline_schema
from .planning import build_batch_plan
from .recovery import build_batch_recovery_plan
from .run_audit import audit_run_state
from .scheduler import PersistentRunScheduler
from .smoke_comfyui import ComfyUISmokeRequest, run_comfyui_smoke


def create_app(
    orchestrator: StoryRunOrchestrator,
    scheduler: PersistentRunScheduler | None = None,
) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if scheduler:
            scheduler.start()
        yield
        if scheduler:
            scheduler.shutdown()

    app = FastAPI(title="Relief Story Agent API", lifespan=lifespan)

    @app.get("/api/health")
    def get_health():
        return {
            "status": "ok",
            "scheduler": {
                "enabled": scheduler is not None,
                "status": scheduler.status() if scheduler else None,
            },
            "state": {
                "persistent": orchestrator.store.__class__.__name__ == "JsonFileRunStore",
                "store": orchestrator.store.__class__.__name__,
            },
            "resources": orchestrator.resource_limits.status(),
            "model_config": orchestrator.model_registry.status(),
        }

    @app.get("/api/metrics")
    def get_metrics():
        batches = orchestrator.store.list_batches()
        if scheduler:
            batches = [orchestrator.refresh_batch(batch.batch_id) for batch in batches]
        return build_system_metrics(orchestrator.store.list_runs(), batches)

    @app.get("/api/config/models")
    def get_model_config_status():
        return orchestrator.model_registry.status()

    @app.get("/api/pipeline/schema")
    def get_pipeline_schema():
        return build_pipeline_schema()

    @app.post("/api/config/validate")
    def validate_config(request: RunRequest, check_comfyui_connection: bool = False):
        return validate_run_configuration(
            request,
            orchestrator.model_registry,
            check_comfyui_connection=check_comfyui_connection,
        )

    @app.post("/api/config/diagnose")
    def diagnose_config(request: RunRequest, check_comfyui_connection: bool = False):
        return diagnose_run_configuration(
            request,
            orchestrator.model_registry,
            check_comfyui_connection=check_comfyui_connection,
        )

    @app.post("/api/config/validate-batch")
    def validate_batch_config(request: BatchRunRequest, check_comfyui_connection: bool = False):
        return validate_batch_configuration(
            request,
            orchestrator.model_registry,
            check_comfyui_connection=check_comfyui_connection,
        )

    @app.post("/api/config/diagnose-batch")
    def diagnose_batch_config(request: BatchRunRequest, check_comfyui_connection: bool = False):
        return diagnose_batch_configuration(
            request,
            orchestrator.model_registry,
            check_comfyui_connection=check_comfyui_connection,
        )

    @app.post("/api/runs")
    def create_run(
        request: RunRequest,
        response: Response,
        preflight: bool = False,
        check_comfyui_connection: bool = False,
    ):
        try:
            if preflight:
                _raise_if_preflight_failed(
                    validate_run_configuration(
                        request,
                        orchestrator.model_registry,
                        check_comfyui_connection=check_comfyui_connection,
                    )
                )
            run = scheduler.create_run(request) if scheduler else orchestrator.create_run(request)
            if scheduler:
                response.status_code = 202
            return run.model_dump()
        except ValueError as exc:
            if "idempotency_key" in str(exc):
                raise HTTPException(status_code=409, detail=str(exc)) from exc
            raise

    @app.get("/api/runs")
    def list_runs(
        status: str | None = None,
        parent_batch_id: str | None = None,
        limit: int = 50,
    ):
        runs = orchestrator.store.list_runs()
        if status:
            runs = [run for run in runs if run.status == status]
        if parent_batch_id:
            runs = [run for run in runs if run.parent_batch_id == parent_batch_id]
        runs = sorted(runs, key=lambda run: run.created_at, reverse=True)
        normalized_limit = _normalize_limit(limit)
        return {
            "total": len(runs),
            "limit": normalized_limit,
            "items": [_run_summary(run) for run in runs[:normalized_limit]],
        }

    @app.post("/api/batches")
    def create_batch(
        request: BatchRunRequest,
        response: Response,
        preflight: bool = False,
        check_comfyui_connection: bool = False,
    ):
        try:
            if preflight:
                _raise_if_preflight_failed(
                    validate_batch_configuration(
                        request,
                        orchestrator.model_registry,
                        check_comfyui_connection=check_comfyui_connection,
                    )
                )
            batch = scheduler.create_batch(request) if scheduler else orchestrator.create_batch(request)
            if scheduler:
                response.status_code = 202
            return batch.model_dump()
        except ValueError as exc:
            if "idempotency_key" in str(exc):
                raise HTTPException(status_code=409, detail=str(exc)) from exc
            raise

    @app.post("/api/batches/plan")
    def plan_batch(request: BatchRunRequest, check_comfyui_connection: bool = False):
        return build_batch_plan(
            request,
            orchestrator.model_registry,
            check_comfyui_connection=check_comfyui_connection,
        )

    @app.post("/api/comfyui/preview")
    def preview_comfyui_submission(request: ComfyUIPreviewRequest):
        try:
            return preview_storyboard_submission(
                request.comfyui,
                request.storyboard,
                request.run_id,
                duration_seconds=request.duration_seconds,
                include_workflow=request.include_workflow,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/comfyui/analyze-workflow")
    def analyze_comfyui_workflow(request: ComfyUIWorkflowAnalysisRequest):
        try:
            return analyze_workflow_config(request.comfyui)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/comfyui/connect")
    def connect_comfyui_endpoint(request: ComfyUIConnectionRequest):
        return connect_comfyui(request)

    @app.post("/api/smoke/comfyui")
    def smoke_comfyui(request: ComfyUISmokeRequest):
        result = run_comfyui_smoke(
            request,
            resource_limits=orchestrator.resource_limits,
        )
        return result.model_dump()

    @app.get("/api/batches")
    def list_batches(status: str | None = None, limit: int = 50):
        batches = orchestrator.store.list_batches()
        if status:
            batches = [batch for batch in batches if batch.status == status]
        if scheduler:
            batches = [orchestrator.refresh_batch(batch.batch_id) for batch in batches]
        batches = sorted(batches, key=lambda batch: batch.created_at, reverse=True)
        normalized_limit = _normalize_limit(limit)
        return {
            "total": len(batches),
            "limit": normalized_limit,
            "items": [_batch_summary(batch) for batch in batches[:normalized_limit]],
        }

    @app.get("/api/batches/{batch_id}")
    def get_batch(batch_id: str):
        try:
            batch = (
                orchestrator.refresh_batch(batch_id)
                if scheduler
                else orchestrator.store.get_batch(batch_id)
            )
            return batch.model_dump()
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="batch not found") from exc

    @app.get("/api/batches/{batch_id}/artifacts")
    def get_batch_artifacts(batch_id: str):
        try:
            batch = orchestrator.refresh_batch(batch_id)
            runs = [orchestrator.store.get(item.run_id) for item in batch.items]
            return read_batch_artifact_index(batch, runs)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="batch not found") from exc

    @app.get("/api/batches/{batch_id}/recovery-plan")
    def get_batch_recovery_plan(batch_id: str):
        try:
            batch = orchestrator.refresh_batch(batch_id)
            runs = [orchestrator.store.get(item.run_id) for item in batch.items]
            return build_batch_recovery_plan(batch, runs)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="batch not found") from exc

    @app.get("/api/batches/{batch_id}/health")
    def get_batch_health_report(batch_id: str):
        try:
            batch = orchestrator.refresh_batch(batch_id)
            runs = [orchestrator.store.get(item.run_id) for item in batch.items]
            return build_batch_health_report(batch, runs)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="batch not found") from exc

    @app.post("/api/batches/{batch_id}/recover")
    def execute_batch_recovery(
        batch_id: str,
        payload: BatchRecoveryExecuteRequest | None = None,
    ):
        try:
            request = payload or BatchRecoveryExecuteRequest()
            batch = orchestrator.refresh_batch(batch_id)
            runs = [orchestrator.store.get(item.run_id) for item in batch.items]
            before_plan = build_batch_recovery_plan(batch, runs)
            result = _execute_recovery_plan(
                before_plan,
                request,
                retry_run=lambda item: (
                    scheduler.retry(
                        item["run_id"],
                        RunRetryRequest(from_stage=item.get("retry_from_stage") or None),
                    )
                    if scheduler
                    else orchestrator.retry(
                        item["run_id"],
                        RunRetryRequest(from_stage=item.get("retry_from_stage") or None),
                    )
                ),
                refresh_outputs=lambda item: orchestrator.refresh_comfyui_outputs(item["run_id"]),
            )
            refreshed = orchestrator.refresh_batch(batch_id)
            refreshed_runs = [orchestrator.store.get(item.run_id) for item in refreshed.items]
            result["after_plan"] = build_batch_recovery_plan(refreshed, refreshed_runs)
            return result
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="batch not found") from exc

    @app.post("/api/batches/{batch_id}/export")
    def export_batch_artifacts(
        batch_id: str,
        payload: BatchExportRequest | None = None,
    ):
        try:
            request = payload or BatchExportRequest()
            batch = orchestrator.refresh_batch(batch_id)
            runs = [orchestrator.store.get(item.run_id) for item in batch.items]
            return export_batch_artifact_package(
                batch,
                runs,
                export_root=request.export_root,
                include_zip=request.include_zip,
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="batch not found") from exc

    @app.post("/api/batches/{batch_id}/export/validate")
    def validate_batch_export(
        batch_id: str,
        payload: BatchExportValidationRequest,
    ):
        try:
            orchestrator.store.get_batch(batch_id)
            return validate_batch_export_package(
                payload.export_dir,
                save_report=payload.save_report,
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="batch not found") from exc

    @app.post("/api/batches/{batch_id}/export/validate-zip")
    def validate_batch_export_zip_route(
        batch_id: str,
        payload: BatchExportZipValidationRequest,
    ):
        try:
            orchestrator.store.get_batch(batch_id)
            return validate_batch_export_zip(
                payload.zip_path,
                expected_sha256=payload.expected_sha256,
                expected_size_bytes=payload.expected_size_bytes,
                save_report=payload.save_report,
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="batch not found") from exc

    @app.post("/api/batches/{batch_id}/retry")
    def retry_batch(batch_id: str, payload: BatchRetryRequest | None = None):
        try:
            batch = (
                scheduler.retry_batch(batch_id, payload)
                if scheduler
                else orchestrator.retry_batch(batch_id, payload)
            )
            return batch.model_dump()
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="batch not found") from exc

    @app.post("/api/batches/{batch_id}/cancel")
    def cancel_batch(batch_id: str):
        try:
            batch = scheduler.cancel_batch(batch_id) if scheduler else orchestrator.cancel_batch(batch_id)
            return batch.model_dump()
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="batch not found") from exc

    @app.post("/api/batches/{batch_id}/pause")
    def pause_batch(batch_id: str):
        try:
            batch = scheduler.pause_batch(batch_id) if scheduler else orchestrator.pause_batch(batch_id)
            return batch.model_dump()
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="batch not found") from exc

    @app.post("/api/batches/{batch_id}/resume")
    def resume_batch(batch_id: str):
        try:
            batch = scheduler.resume_batch(batch_id) if scheduler else orchestrator.resume_batch(batch_id)
            return batch.model_dump()
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="batch not found") from exc

    @app.get("/api/runs/{run_id}")
    def get_run(run_id: str):
        try:
            return orchestrator.store.get(run_id).model_dump()
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="run not found") from exc

    @app.get("/api/runs/{run_id}/events")
    def get_run_events(run_id: str, after: int = 0):
        try:
            run = orchestrator.store.get(run_id)
            events = [event for event in run.events if event.sequence > after]
            return {
                "run_id": run_id,
                "after": after,
                "events": [event.model_dump() for event in events],
            }
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="run not found") from exc

    @app.get("/api/runs/{run_id}/audit")
    def get_run_audit(run_id: str):
        try:
            return audit_run_state(orchestrator.store.get(run_id))
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="run not found") from exc

    @app.get("/api/runs/{run_id}/artifacts")
    def get_run_artifacts(run_id: str):
        try:
            return read_run_artifact_index(orchestrator.store.get(run_id))
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="run not found") from exc

    @app.post("/api/runs/{run_id}/refresh-comfyui")
    def refresh_comfyui_outputs(run_id: str):
        try:
            run = orchestrator.refresh_comfyui_outputs(run_id)
            return read_run_artifact_index(run)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="run not found") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/runs/{run_id}/approve")
    def approve_run(run_id: str, payload: dict | None = None):
        try:
            run = (
                scheduler.approve(run_id, payload or {})
                if scheduler
                else orchestrator.approve(run_id, payload=payload or {})
            )
            return run.model_dump()
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="run not found") from exc

    @app.post("/api/runs/{run_id}/retry")
    def retry_run(run_id: str, payload: RunRetryRequest | None = None):
        try:
            run = (
                scheduler.retry(run_id, payload)
                if scheduler
                else orchestrator.retry(run_id, payload)
            )
            return run.model_dump()
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="run not found") from exc

    @app.post("/api/runs/{run_id}/cancel")
    def cancel_run(run_id: str):
        try:
            run = scheduler.cancel(run_id) if scheduler else orchestrator.cancel(run_id)
            return run.model_dump()
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="run not found") from exc

    if scheduler:
        @app.get("/api/scheduler")
        def get_scheduler_status():
            return scheduler.status()

    return app


def _normalize_limit(limit: int) -> int:
    if limit < 1:
        return 1
    return min(limit, 200)


def _raise_if_preflight_failed(validation: dict) -> None:
    if validation.get("passed") is True:
        return
    raise HTTPException(
        status_code=400,
        detail={
            "message": "preflight validation failed",
            "validation": validation,
        },
    )


def _execute_recovery_plan(
    plan: dict,
    request: BatchRecoveryExecuteRequest,
    *,
    retry_run,
    refresh_outputs,
) -> dict:
    requested_actions = set(request.action_codes or [])
    executed = []
    skipped = []
    failed = []
    would_execute = []
    for item in plan.get("items", []):
        action_code = str(item.get("action_code") or "")
        base = {
            "run_id": item.get("run_id", ""),
            "action_code": action_code,
            "retry_from_stage": item.get("retry_from_stage", ""),
            "endpoint": item.get("endpoint", ""),
            "request_payload": item.get("request_payload", {}),
        }
        if requested_actions and action_code not in requested_actions:
            skipped.append({**base, "reason": "action not requested"})
            continue
        if not item.get("safe_to_auto_execute"):
            skipped.append({**base, "reason": "not safe to auto execute"})
            continue
        if request.dry_run:
            would_execute.append(base)
            continue
        try:
            if action_code == "retry_from_stage":
                run = retry_run(item)
            elif action_code == "refresh_comfyui_outputs":
                run = refresh_outputs(item)
            else:
                skipped.append({**base, "reason": "unsupported auto action"})
                continue
            executed.append(
                {
                    **base,
                    "status_after": run.status,
                    "current_stage_after": run.current_stage,
                    "error_after": run.error,
                }
            )
        except Exception as exc:
            failed.append({**base, "error": str(exc)})
    return {
        "batch_id": plan.get("batch_id", ""),
        "dry_run": request.dry_run,
        "summary": {
            "total_items": len(plan.get("items", [])),
            "would_execute_count": len(would_execute),
            "executed_count": len(executed),
            "skipped_count": len(skipped),
            "failed_count": len(failed),
        },
        "would_execute": would_execute,
        "executed": executed,
        "skipped": skipped,
        "failed": failed,
        "before_plan": plan,
    }


def _run_summary(run: RunState) -> dict:
    return {
        "run_id": run.run_id,
        "status": run.status,
        "current_stage": run.current_stage,
        "idea": run.request.idea,
        "title": str(run.script.get("title") or ""),
        "parent_batch_id": run.parent_batch_id,
        "idempotency_key": run.idempotency_key,
        "queue_priority": run.queue_priority,
        "created_at": run.created_at,
        "updated_at": run.updated_at,
        "finished_at": run.finished_at,
        "error": run.error,
    }


def _batch_summary(batch: BatchRunState) -> dict:
    return {
        "batch_id": batch.batch_id,
        "status": batch.status,
        "paused": batch.paused,
        "failure_policy": batch.failure_policy.model_dump(),
        "summary": dict(batch.summary),
        "item_count": len(batch.items),
        "items": [
            {
                "index": item.index,
                "run_id": item.run_id,
                "idea": item.idea,
                "status": item.status,
                "current_stage": item.current_stage,
                "queue_priority": item.queue_priority,
                "error": item.error,
            }
            for item in batch.items
        ],
        "idempotency_key": batch.idempotency_key,
        "created_at": batch.created_at,
        "updated_at": batch.updated_at,
    }
