from __future__ import annotations

from collections import Counter
from typing import Any

from .artifacts import read_batch_artifact_index
from .models import BatchRunItem, BatchRunState, RunState
from .run_timeline import build_run_timeline


def build_batch_timeline(
    batch: BatchRunState,
    runs: list[RunState],
) -> dict[str, Any]:
    runs_by_id = {run.run_id: run for run in runs}
    artifact_index = read_batch_artifact_index(batch, runs)
    artifacts_by_run_id = {
        str(item.get("run_id") or ""): item
        for item in artifact_index.get("items", [])
    }
    items = [
        _timeline_item(batch_item, runs_by_id.get(batch_item.run_id), artifacts_by_run_id)
        for batch_item in batch.items
    ]
    return {
        "batch_id": batch.batch_id,
        "status": batch.status,
        "paused": batch.paused,
        "summary": dict(batch.summary),
        "progress": _progress_summary(batch, items),
        "items": items,
        "audit_summary": artifact_index.get("audit_summary", {}),
        "links": {
            "detail": f"/api/batches/{batch.batch_id}",
            "artifacts": f"/api/batches/{batch.batch_id}/artifacts",
            "health": f"/api/batches/{batch.batch_id}/health",
            "recovery_plan": f"/api/batches/{batch.batch_id}/recovery-plan",
            "recover": f"/api/batches/{batch.batch_id}/recover",
            "export": f"/api/batches/{batch.batch_id}/export",
        },
        "timestamps": {
            "created_at": batch.created_at,
            "updated_at": batch.updated_at,
        },
    }


def _timeline_item(
    batch_item: BatchRunItem,
    run: RunState | None,
    artifacts_by_run_id: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    artifact = artifacts_by_run_id.get(batch_item.run_id, {})
    if run is None:
        return _missing_run_item(batch_item, artifact)
    run_timeline = build_run_timeline(run)
    progress = run_timeline["progress"]
    outputs = run_timeline["outputs"]
    return {
        "index": batch_item.index,
        "run_id": run.run_id,
        "idea": batch_item.idea,
        "status": run.status,
        "current_stage": run.current_stage,
        "active_stage": progress.get("active_stage", ""),
        "stage_percent": progress.get("percent", 0),
        "stage_count": progress.get("stage_count", 0),
        "completed_stage_count": progress.get("completed_count", 0),
        "failed_stage": run.failed_stage,
        "last_completed_stage": run.last_completed_stage,
        "publish_ready": bool(artifact.get("publish_ready")),
        "primary_video_path": str(artifact.get("primary_video_path") or outputs.get("primary_video_path") or ""),
        "output_count": outputs.get("output_count", 0),
        "video_count": outputs.get("video_count", 0),
        "retryable": bool(artifact.get("retryable")),
        "retry_from_stage": str(artifact.get("retry_from_stage") or ""),
        "recommended_action": artifact.get("recommended_action") or {},
        "suggested_actions": run_timeline.get("suggested_actions", []),
        "links": run_timeline.get("links", {}),
        "error": run.error or batch_item.error,
    }


def _missing_run_item(
    batch_item: BatchRunItem,
    artifact: dict[str, Any],
) -> dict[str, Any]:
    recommended_action = artifact.get("recommended_action") or {}
    return {
        "index": batch_item.index,
        "run_id": batch_item.run_id,
        "idea": batch_item.idea,
        "status": batch_item.status,
        "current_stage": batch_item.current_stage,
        "active_stage": batch_item.current_stage,
        "stage_percent": 0,
        "stage_count": 0,
        "completed_stage_count": 0,
        "failed_stage": artifact.get("failed_stage", ""),
        "last_completed_stage": "",
        "publish_ready": False,
        "primary_video_path": "",
        "output_count": 0,
        "video_count": 0,
        "retryable": False,
        "retry_from_stage": "",
        "recommended_action": recommended_action,
        "suggested_actions": [recommended_action.get("code", "inspect_missing_run")],
        "links": {
            "detail": f"/api/runs/{batch_item.run_id}",
            "artifacts": f"/api/runs/{batch_item.run_id}/artifacts",
        },
        "error": batch_item.error or artifact.get("error", "run not found"),
    }


def _progress_summary(
    batch: BatchRunState,
    items: list[dict[str, Any]],
) -> dict[str, int]:
    status_counts = Counter(str(item.get("status") or "") for item in items)
    item_count = len(batch.items)
    completed_count = status_counts.get("completed", 0)
    return {
        "item_count": item_count,
        "known_run_count": sum(1 for item in items if item.get("stage_count", 0) > 0),
        "completed_count": completed_count,
        "failed_count": status_counts.get("failed", 0),
        "running_count": status_counts.get("running", 0),
        "publish_ready_count": sum(1 for item in items if item.get("publish_ready")),
        "retryable_count": sum(1 for item in items if item.get("retryable")),
        "percent": round((completed_count / item_count) * 100) if item_count else 0,
    }
