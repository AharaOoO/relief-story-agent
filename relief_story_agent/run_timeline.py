from __future__ import annotations

from typing import Any

from .models import RunEvent, RunState
from .pipeline import get_stage_spec, stage_ids_for_run
from .run_audit import audit_run_state


TERMINAL_STATUSES = {"completed", "failed", "cancelled"}


def build_run_timeline(run: RunState) -> dict[str, Any]:
    stages = _stage_ids_for_timeline(run)
    stage_items = [_stage_item(run, stage_id, index, stages) for index, stage_id in enumerate(stages)]
    completed_count = sum(1 for item in stage_items if item["status"] == "completed")
    active_stage = _active_stage(stage_items)
    stage_count = len(stage_items)
    audit = audit_run_state(run)
    return {
        "run_id": run.run_id,
        "status": run.status,
        "current_stage": run.current_stage,
        "failed_stage": run.failed_stage,
        "last_completed_stage": run.last_completed_stage,
        "resume_stage": run.resume_stage,
        "is_terminal": run.status in TERMINAL_STATUSES,
        "progress": {
            "stage_count": stage_count,
            "completed_count": completed_count,
            "active_stage": active_stage,
            "percent": round((completed_count / stage_count) * 100) if stage_count else 0,
        },
        "stages": stage_items,
        "outputs": _outputs_summary(run),
        "audit": {
            "valid": audit["valid"],
            "summary": audit["summary"],
            "retry_from_stage": audit.get("retry_from_stage", ""),
        },
        "suggested_actions": _suggested_actions(run, audit),
        "links": {
            "detail": f"/api/runs/{run.run_id}",
            "events": f"/api/runs/{run.run_id}/events",
            "audit": f"/api/runs/{run.run_id}/audit",
            "artifacts": f"/api/runs/{run.run_id}/artifacts",
            "retry": f"/api/runs/{run.run_id}/retry",
            "refresh_comfyui": f"/api/runs/{run.run_id}/refresh-comfyui",
        },
        "timestamps": {
            "created_at": run.created_at,
            "queued_at": run.queued_at,
            "started_at": run.started_at,
            "updated_at": run.updated_at,
            "finished_at": run.finished_at,
        },
        "error": run.error,
    }


def _stage_ids_for_timeline(run: RunState) -> list[str]:
    requires_grid_asset = bool(run.grid_image_asset or run.grid_image_checkpoint)
    writes_artifacts = bool(run.request.output_root or run.artifact_dir or requires_grid_asset)
    comfyui_enabled = bool(run.request.comfyui and run.request.comfyui.enabled)
    stages = stage_ids_for_run(
        requires_grid_asset=requires_grid_asset,
        writes_artifacts=writes_artifacts,
        comfyui_enabled=comfyui_enabled,
    )
    observed_stages = [
        event.stage
        for event in run.events
        if event.stage and event.stage not in stages
    ]
    for stage_id in observed_stages:
        if stage_id == "gpt_prompt_reviser" and "final_prompts" in stages:
            stages.insert(stages.index("final_prompts"), stage_id)
        elif stage_id not in stages:
            stages.append(stage_id)
    return stages


def _stage_item(
    run: RunState,
    stage_id: str,
    index: int,
    stages: list[str],
) -> dict[str, Any]:
    spec = get_stage_spec(stage_id)
    started_event = _first_event(run.events, "stage_started", stage_id)
    completed_event = _last_event(run.events, "stage_completed", stage_id)
    failed_event = _last_event(run.events, "run_failed", stage_id)
    status = _stage_status(run, stage_id, started_event, completed_event, failed_event)
    return {
        "stage_id": stage_id,
        "index": index,
        "category": spec.category,
        "retryable": spec.retryable,
        "status": status,
        "started_at": started_event.timestamp if started_event else "",
        "completed_at": completed_event.timestamp if completed_event else "",
        "event_count": sum(1 for event in run.events if event.stage == stage_id),
        "previous_stage": stages[index - 1] if index else "",
        "next_stage": stages[index + 1] if index < len(stages) - 1 else "",
    }


def _stage_status(
    run: RunState,
    stage_id: str,
    started_event: RunEvent | None,
    completed_event: RunEvent | None,
    failed_event: RunEvent | None,
) -> str:
    if completed_event:
        return "completed"
    if failed_event or (run.status == "failed" and run.failed_stage == stage_id):
        return "failed"
    if run.status == "running" and run.current_stage == stage_id:
        return "running"
    if started_event and run.current_stage == stage_id and run.status not in TERMINAL_STATUSES:
        return "running"
    return "pending"


def _outputs_summary(run: RunState) -> dict[str, Any]:
    outputs = [output.model_dump() for output in run.comfyui_outputs]
    video_outputs = [output for output in outputs if output.get("media_type") == "video"]
    primary_video_path = ""
    for output in video_outputs:
        if output.get("local_path"):
            primary_video_path = str(output["local_path"])
            break
    return {
        "comfyui_prompt_ids": list(run.comfyui_prompt_ids),
        "output_count": len(outputs),
        "video_count": len(video_outputs),
        "primary_video_path": primary_video_path,
        "actual_outputs": outputs,
        "artifact_dir": run.artifact_dir,
    }


def _suggested_actions(run: RunState, audit: dict[str, Any]) -> list[str]:
    actions = list(audit.get("suggested_actions") or [])
    if run.status == "completed" and not _outputs_summary(run)["primary_video_path"]:
        actions.append("inspect_outputs")
    if run.comfyui_prompt_ids and not run.comfyui_outputs:
        actions.append("refresh_comfyui_outputs")
    return _dedupe(actions)


def _active_stage(stage_items: list[dict[str, Any]]) -> str:
    for item in stage_items:
        if item["status"] in {"running", "failed"}:
            return str(item["stage_id"])
    for item in stage_items:
        if item["status"] == "pending":
            return str(item["stage_id"])
    return ""


def _first_event(events: list[RunEvent], event_type: str, stage_id: str) -> RunEvent | None:
    for event in events:
        if event.event_type == event_type and event.stage == stage_id:
            return event
    return None


def _last_event(events: list[RunEvent], event_type: str, stage_id: str) -> RunEvent | None:
    for event in reversed(events):
        if event.event_type == event_type and event.stage == stage_id:
            return event
    return None


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result
