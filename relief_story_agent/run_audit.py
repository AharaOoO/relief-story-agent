from __future__ import annotations

from typing import Any

from .models import RunEvent, RunState
from .pipeline import CANONICAL_STAGE_ORDER


STAGE_EVENT_TYPES = {
    "stage_started",
    "stage_completed",
    "execution_policy_blocked",
    "run_failed",
    "retry_queued",
    "comfyui_outputs_refreshed",
    "comfyui_cancellation_requested",
}


def audit_run_state(run: RunState) -> dict[str, Any]:
    checks = [
        _check_event_sequence(run.events),
        _check_known_stage_names(run.events),
        _check_stage_order(run.events),
        _check_failure_record(run),
    ]
    summary = {
        "passed": sum(1 for check in checks if check["status"] == "pass"),
        "warnings": sum(1 for check in checks if check["status"] == "warn"),
        "failed": sum(1 for check in checks if check["status"] == "fail"),
    }
    return {
        "run_id": run.run_id,
        "status": run.status,
        "current_stage": run.current_stage,
        "valid": summary["failed"] == 0,
        "summary": summary,
        "checks": checks,
        "stage_path": _stage_path(run.events),
        "suggested_actions": _suggest_actions(run, summary),
        "retry_from_stage": (
            run.last_failure.stage
            if run.last_failure and run.last_failure.retryable
            else ""
        ),
    }


def _check_event_sequence(events: list[RunEvent]) -> dict[str, Any]:
    expected = list(range(1, len(events) + 1))
    actual = [event.sequence for event in events]
    if actual != expected:
        return _check(
            "event_sequence",
            "fail",
            "Run event sequence numbers are not contiguous.",
            {"expected": expected, "actual": actual},
        )
    return _check(
        "event_sequence",
        "pass",
        "Run event sequence numbers are contiguous.",
        {"count": len(events)},
    )


def _check_known_stage_names(events: list[RunEvent]) -> dict[str, Any]:
    unknown = sorted(
        {
            event.stage
            for event in events
            if event.stage
            and event.event_type in STAGE_EVENT_TYPES
            and event.stage not in CANONICAL_STAGE_ORDER
        }
    )
    if unknown:
        return _check(
            "known_stage_names",
            "fail",
            "Run event stream references unknown stage name(s).",
            {"unknown_stages": unknown, "valid_stage_ids": list(CANONICAL_STAGE_ORDER)},
        )
    return _check(
        "known_stage_names",
        "pass",
        "Run event stream only references known stage names.",
        {"valid_stage_ids": list(CANONICAL_STAGE_ORDER)},
    )


def _check_stage_order(events: list[RunEvent]) -> dict[str, Any]:
    index_by_stage = {stage: index for index, stage in enumerate(CANONICAL_STAGE_ORDER)}
    last_index: int | None = None
    last_stage = ""
    started: dict[str, int] = {}
    completed: dict[str, int] = {}
    regressions: list[dict[str, Any]] = []
    missing_starts: list[dict[str, Any]] = []

    for event in events:
        if event.event_type == "retry_queued":
            last_index = None
            last_stage = ""
            started = {}
            completed = {}
            continue
        if event.stage not in index_by_stage:
            continue
        if event.event_type == "stage_started":
            current_index = index_by_stage[event.stage]
            if last_index is not None and current_index < last_index:
                regressions.append(
                    {
                        "sequence": event.sequence,
                        "stage": event.stage,
                        "previous_stage": last_stage,
                    }
                )
            last_index = current_index
            last_stage = event.stage
            started[event.stage] = started.get(event.stage, 0) + 1
        elif event.event_type == "stage_completed":
            completed[event.stage] = completed.get(event.stage, 0) + 1
            if completed[event.stage] > started.get(event.stage, 0):
                missing_starts.append(
                    {
                        "sequence": event.sequence,
                        "stage": event.stage,
                    }
                )

    if regressions or missing_starts:
        return _check(
            "stage_order",
            "fail",
            "Run stage lifecycle is inconsistent with the fixed pipeline order.",
            {"regressions": regressions, "completed_without_start": missing_starts},
        )
    return _check(
        "stage_order",
        "pass",
        "Run stage lifecycle follows the fixed pipeline order.",
        {},
    )


def _check_failure_record(run: RunState) -> dict[str, Any]:
    if run.status != "failed":
        return _check(
            "failure_record",
            "pass",
            "Run is not failed; no failure record is required.",
            {"status": run.status},
        )
    if not run.last_failure:
        return _check(
            "failure_record",
            "fail",
            "Failed run is missing last_failure.",
            {"status": run.status, "failed_stage": run.failed_stage},
        )
    if not run.failure_records:
        return _check(
            "failure_record",
            "warn",
            "Failed run has last_failure but no failure_records history.",
            {"last_failure": run.last_failure.model_dump()},
        )
    return _check(
        "failure_record",
        "pass",
        "Failed run has structured failure details.",
        {"last_failure": run.last_failure.model_dump()},
    )


def _stage_path(events: list[RunEvent]) -> list[str]:
    completed = [
        event.stage
        for event in events
        if event.event_type == "stage_completed"
        and event.stage in CANONICAL_STAGE_ORDER
    ]
    if completed:
        return completed
    return [
        event.stage
        for event in events
        if event.event_type == "stage_started"
        and event.stage in CANONICAL_STAGE_ORDER
    ]


def _suggest_actions(run: RunState, summary: dict[str, int]) -> list[str]:
    if summary["failed"]:
        return ["inspect_run_events"]
    if run.last_failure and run.last_failure.retryable:
        return ["retry_from_stage"]
    return []


def _check(
    check_id: str,
    status: str,
    message: str,
    details: dict[str, Any],
) -> dict[str, Any]:
    return {
        "id": check_id,
        "status": status,
        "message": message,
        "details": details,
    }
