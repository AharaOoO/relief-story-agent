from __future__ import annotations

from typing import Any

from .artifacts import read_batch_artifact_index
from .models import BatchRunState, RunState


AUTO_ACTIONS = {"retry_from_stage", "refresh_comfyui_outputs"}
PUBLISH_ACTIONS = {"publish"}
WAIT_ACTIONS = {"wait"}


def build_batch_recovery_plan(
    batch: BatchRunState,
    runs: list[RunState],
) -> dict[str, Any]:
    artifact_index = read_batch_artifact_index(batch, runs)
    items = [_build_recovery_item(item) for item in artifact_index["items"]]
    return {
        "batch_id": batch.batch_id,
        "status": artifact_index["status"],
        "summary": _summarize_recovery_items(items),
        "items": items,
        "audit_summary": artifact_index.get("audit_summary", {}),
    }


def _build_recovery_item(item: dict[str, Any]) -> dict[str, Any]:
    action = item.get("recommended_action") or {}
    action_code = str(action.get("code") or "manual_review")
    retry_from_stage = str(action.get("retry_from_stage") or item.get("retry_from_stage") or "")
    automation_level = _automation_level(action_code)
    safe_to_auto_execute = action_code in AUTO_ACTIONS
    endpoint = str(action.get("endpoint") or "")
    request_payload: dict[str, Any] = {}
    if action_code == "retry_from_stage" and retry_from_stage:
        request_payload = {"from_stage": retry_from_stage}

    return {
        "index": item.get("index"),
        "run_id": item.get("run_id", ""),
        "idea": item.get("idea", ""),
        "status": item.get("status", ""),
        "current_stage": item.get("current_stage", ""),
        "failed_stage": item.get("failed_stage", ""),
        "error": item.get("error", ""),
        "action_code": action_code,
        "action_label": str(action.get("label") or ""),
        "automation_level": automation_level,
        "safe_to_auto_execute": safe_to_auto_execute,
        "retryable": bool(item.get("retryable")),
        "retry_from_stage": retry_from_stage,
        "endpoint": endpoint,
        "request_payload": request_payload,
        "blocking_reason": _blocking_reason(action_code),
        "primary_video_path": str(item.get("primary_video_path") or ""),
        "timeline_diagnostics": item.get("timeline_diagnostics") or {},
        "last_failure": item.get("last_failure") or {},
        "failure_records": item.get("failure_records") or [],
        "recommended_action": action,
    }


def _automation_level(action_code: str) -> str:
    if action_code in AUTO_ACTIONS:
        return "auto"
    if action_code in PUBLISH_ACTIONS:
        return "publish"
    if action_code in WAIT_ACTIONS:
        return "wait"
    return "manual"


def _blocking_reason(action_code: str) -> str:
    if action_code == "fix_template":
        return "Prompt template must be fixed before retry."
    if action_code == "check_comfyui_mapping":
        return "ComfyUI workflow or placeholder mapping must be inspected before retry."
    if action_code == "manual_review_prompt_audit":
        return "Prompt spatial, axis, motion, or story logic needs manual review before retry."
    if action_code == "manual_review_script_quality":
        return "Script quality gate needs manual review before retry."
    if action_code == "manual_review_cancelled":
        return "Cancelled run needs an operator decision before rerun."
    if action_code in {"manual_review", "inspect_missing_run", "inspect_outputs"}:
        return "Manual inspection is required before automatic execution."
    return ""


def _summarize_recovery_items(items: list[dict[str, Any]]) -> dict[str, Any]:
    by_action: dict[str, int] = {}
    by_automation_level: dict[str, int] = {}
    for item in items:
        action_code = str(item.get("action_code") or "")
        automation_level = str(item.get("automation_level") or "")
        if action_code:
            by_action[action_code] = by_action.get(action_code, 0) + 1
        if automation_level:
            by_automation_level[automation_level] = by_automation_level.get(automation_level, 0) + 1
    return {
        "total_items": len(items),
        "publish_ready_count": by_automation_level.get("publish", 0),
        "auto_retryable_count": sum(
            1 for item in items if item.get("safe_to_auto_execute") and item.get("action_code") == "retry_from_stage"
        ),
        "auto_executable_count": sum(1 for item in items if item.get("safe_to_auto_execute")),
        "manual_review_count": by_automation_level.get("manual", 0),
        "wait_count": by_automation_level.get("wait", 0),
        "by_action": by_action,
        "by_automation_level": by_automation_level,
    }
