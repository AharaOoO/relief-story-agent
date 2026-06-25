from __future__ import annotations

from collections import Counter
from datetime import datetime
from typing import Any

from .models import BatchRunState, RunState
from .recovery import build_batch_recovery_plan


def build_system_metrics(
    runs: list[RunState],
    batches: list[BatchRunState],
) -> dict[str, Any]:
    status_counts = Counter(run.status for run in runs)
    failed_stage_counts = Counter(
        run.failed_stage or "unknown"
        for run in runs
        if run.status == "failed"
    )
    batch_status_counts = Counter(batch.status for batch in batches)
    durations = [_duration_seconds(run) for run in runs]
    durations = [value for value in durations if value is not None]
    total_runs = len(runs)
    completed_runs = status_counts.get("completed", 0)
    return {
        "runs": {
            "total": total_runs,
            "by_status": dict(sorted(status_counts.items())),
            "by_failed_stage": dict(sorted(failed_stage_counts.items())),
            "completed_success_rate": (
                completed_runs / total_runs if total_runs else 0
            ),
            "average_duration_seconds": (
                sum(durations) / len(durations) if durations else 0
            ),
        },
        "batches": {
            "total": len(batches),
            "by_status": dict(sorted(batch_status_counts.items())),
        },
        "usage": _usage_summary(runs),
        "publish": {
            "ready_run_count": sum(1 for run in runs if _publish_ready(run)),
            "video_output_count": sum(
                1
                for run in runs
                for output in run.comfyui_outputs
                if output.media_type == "video"
            ),
        },
    }


def build_batch_health_report(
    batch: BatchRunState,
    runs: list[RunState],
) -> dict[str, Any]:
    runs_by_id = {run.run_id: run for run in runs}
    ordered_runs = [runs_by_id[item.run_id] for item in batch.items if item.run_id in runs_by_id]
    status_counts = Counter(run.status for run in ordered_runs)
    failed_stage_counts = Counter(
        run.failed_stage or "unknown"
        for run in ordered_runs
        if run.status == "failed"
    )
    current_stage_counts = Counter(run.current_stage or "unknown" for run in ordered_runs)
    recovery_plan = build_batch_recovery_plan(batch, ordered_runs)
    recovery_action_counts = Counter(
        str(item.get("action_code") or "unknown")
        for item in recovery_plan.get("items", [])
    )
    stage_stats = _stage_performance(ordered_runs)
    open_stage_runs = _open_stage_runs(ordered_runs)

    total = len(batch.items)
    completed = status_counts.get("completed", 0)
    failed = status_counts.get("failed", 0)
    return {
        "batch_id": batch.batch_id,
        "status": batch.status,
        "summary": {
            "total_items": total,
            "known_run_count": len(ordered_runs),
            "completed_count": completed,
            "failed_count": failed,
            "running_count": status_counts.get("running", 0),
            "cancelled_count": status_counts.get("cancelled", 0),
            "success_rate": completed / total if total else 0,
            "publish_ready_count": sum(1 for run in ordered_runs if _publish_ready(run)),
            "auto_recovery_count": recovery_plan.get("summary", {}).get("auto_executable_count", 0),
            "manual_review_count": recovery_plan.get("summary", {}).get("manual_review_count", 0),
        },
        "bottlenecks": {
            "failed_stage_counts": dict(sorted(failed_stage_counts.items())),
            "current_stage_counts": dict(sorted(current_stage_counts.items())),
            "recovery_action_counts": dict(sorted(recovery_action_counts.items())),
            "top_failed_stage": _top_counter_key(failed_stage_counts),
            "top_recovery_action": _top_counter_key(recovery_action_counts),
        },
        "stage_performance": stage_stats,
        "open_stage_runs": open_stage_runs,
        "slowest_runs": _slowest_runs(ordered_runs),
        "recommendations": _health_recommendations(
            failed_stage_counts=failed_stage_counts,
            recovery_action_counts=recovery_action_counts,
            open_stage_runs=open_stage_runs,
        ),
    }


def _usage_summary(runs: list[RunState]) -> dict[str, Any]:
    return {
        "total_requests": sum(run.model_usage_summary.total_requests for run in runs),
        "total_attempts": sum(run.model_usage_summary.total_attempts for run in runs),
        "retry_count": sum(run.model_usage_summary.retry_count for run in runs),
        "prompt_tokens": sum(run.model_usage_summary.prompt_tokens for run in runs),
        "completion_tokens": sum(run.model_usage_summary.completion_tokens for run in runs),
        "total_tokens": sum(run.model_usage_summary.total_tokens for run in runs),
        "estimated_cost_usd": round(
            sum(run.model_usage_summary.estimated_cost_usd for run in runs),
            6,
        ),
    }


def _publish_ready(run: RunState) -> bool:
    return run.status == "completed" and any(
        output.media_type == "video" and (output.local_path or output.url)
        for output in run.comfyui_outputs
    )


def _duration_seconds(run: RunState) -> float | None:
    if not run.created_at or not run.finished_at:
        return None
    try:
        started = datetime.fromisoformat(run.created_at)
        finished = datetime.fromisoformat(run.finished_at)
    except ValueError:
        return None
    return max((finished - started).total_seconds(), 0)


def _stage_performance(runs: list[RunState]) -> dict[str, dict[str, Any]]:
    durations: dict[str, list[float]] = {}
    open_counts: Counter[str] = Counter()
    completed_counts: Counter[str] = Counter()
    for run in runs:
        open_starts: dict[str, datetime] = {}
        for event in run.events:
            if not event.stage:
                continue
            event_time = _parse_iso_datetime(event.timestamp)
            if event_time is None:
                continue
            if event.event_type == "stage_started":
                open_starts[event.stage] = event_time
            elif event.event_type == "stage_completed":
                start = open_starts.pop(event.stage, None)
                if start is not None:
                    durations.setdefault(event.stage, []).append(
                        max((event_time - start).total_seconds(), 0)
                    )
                completed_counts[event.stage] += 1
        for stage in open_starts:
            open_counts[stage] += 1

    stages = sorted(set(durations) | set(open_counts) | set(completed_counts))
    return {
        stage: {
            "completed_count": completed_counts.get(stage, 0),
            "open_count": open_counts.get(stage, 0),
            "average_duration_seconds": (
                round(sum(durations.get(stage, [])) / len(durations[stage]), 3)
                if durations.get(stage)
                else 0
            ),
            "max_duration_seconds": (
                round(max(durations.get(stage, [])), 3)
                if durations.get(stage)
                else 0
            ),
        }
        for stage in stages
    }


def _open_stage_runs(runs: list[RunState]) -> list[dict[str, Any]]:
    items = []
    for run in runs:
        open_stages = _open_stages_for_run(run)
        for stage in open_stages:
            items.append(
                {
                    "run_id": run.run_id,
                    "idea": run.request.idea,
                    "status": run.status,
                    "stage": stage,
                    "failed_stage": run.failed_stage,
                }
            )
    return items


def _open_stages_for_run(run: RunState) -> list[str]:
    open_stages: list[str] = []
    for event in run.events:
        if not event.stage:
            continue
        if event.event_type == "stage_started":
            if event.stage not in open_stages:
                open_stages.append(event.stage)
        elif event.event_type == "stage_completed":
            open_stages = [stage for stage in open_stages if stage != event.stage]
    return open_stages


def _slowest_runs(runs: list[RunState], *, limit: int = 5) -> list[dict[str, Any]]:
    candidates = []
    for run in runs:
        duration = _duration_seconds(run)
        if duration is None:
            continue
        candidates.append(
            {
                "run_id": run.run_id,
                "idea": run.request.idea,
                "status": run.status,
                "duration_seconds": round(duration, 3),
            }
        )
    return sorted(candidates, key=lambda item: item["duration_seconds"], reverse=True)[:limit]


def _health_recommendations(
    *,
    failed_stage_counts: Counter[str],
    recovery_action_counts: Counter[str],
    open_stage_runs: list[dict[str, Any]],
) -> list[dict[str, str]]:
    recommendations: list[dict[str, str]] = []
    if failed_stage_counts.get("gpt_prompt_audit", 0) or recovery_action_counts.get("manual_review_prompt_audit", 0):
        recommendations.append(
            {
                "code": "review_prompt_audit",
                "message": "Prompt audit failures are present; inspect spatial, axis, motion, and shot-meaning template rules.",
            }
        )
    if recovery_action_counts.get("check_comfyui_mapping", 0):
        recommendations.append(
            {
                "code": "check_comfyui_mapping",
                "message": "ComfyUI mapping failures are present; validate workflow injection points and placeholder sources.",
            }
        )
    if recovery_action_counts.get("fix_template", 0):
        recommendations.append(
            {
                "code": "fix_templates",
                "message": "Template validation failures are present; update writer or audit markdown templates before retry.",
            }
        )
    if open_stage_runs:
        recommendations.append(
            {
                "code": "inspect_open_stages",
                "message": "Some runs have stage_started events without matching stage_completed events; recovery should use timeline diagnostics.",
            }
        )
    if not recommendations:
        recommendations.append(
            {
                "code": "continue_batch",
                "message": "No dominant bottleneck detected from current run history.",
            }
        )
    return recommendations


def _top_counter_key(counter: Counter[str]) -> str:
    return counter.most_common(1)[0][0] if counter else ""


def _parse_iso_datetime(value: str) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None
