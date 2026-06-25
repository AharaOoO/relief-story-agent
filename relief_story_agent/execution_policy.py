from __future__ import annotations

from .models import RunEvent, RunState


class ExecutionPolicyExceeded(RuntimeError):
    def __init__(self, *, stage: str, code: str, message: str, details: dict):
        super().__init__(message)
        self.stage = stage
        self.code = code
        self.details = details


def enforce_execution_policy(run: RunState, stage: str) -> None:
    policy = run.request.execution_policy
    total_started = _stage_started_count(run.events)
    if (
        policy.max_total_stage_executions
        and total_started >= policy.max_total_stage_executions
    ):
        raise ExecutionPolicyExceeded(
            stage=stage,
            code="execution_policy_exhausted",
            message=(
                "Execution policy exhausted before starting "
                f"{stage}: total stage execution limit "
                f"{policy.max_total_stage_executions} reached."
            ),
            details={
                "limit_type": "max_total_stage_executions",
                "limit": policy.max_total_stage_executions,
                "total_stage_execution_count": total_started,
                "next_stage": stage,
            },
        )

    stage_limit = policy.max_stage_executions.get(stage, 0)
    stage_started = _stage_started_count(run.events, stage=stage)
    if stage_limit and stage_started >= stage_limit:
        raise ExecutionPolicyExceeded(
            stage=stage,
            code="execution_policy_exhausted",
            message=(
                "Execution policy exhausted before starting "
                f"{stage}: stage execution limit {stage_limit} reached."
            ),
            details={
                "limit_type": "max_stage_executions",
                "limit": stage_limit,
                "stage_execution_count": stage_started,
                "next_stage": stage,
            },
        )


def _stage_started_count(events: list[RunEvent], *, stage: str = "") -> int:
    return sum(
        1
        for event in events
        if event.event_type == "stage_started" and (not stage or event.stage == stage)
    )
