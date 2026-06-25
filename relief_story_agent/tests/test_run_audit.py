from __future__ import annotations

from fastapi.testclient import TestClient

from relief_story_agent.api import create_app
from relief_story_agent.models import FailureRecord, RunRequest, RunState
from relief_story_agent.orchestrator import InMemoryRunStore, StoryRunOrchestrator
from relief_story_agent.providers import FakeModelProvider
from relief_story_agent.run_audit import audit_run_state


def _run_state(*, status: str = "running", current_stage: str = "gpt_prompt_writer") -> RunState:
    return RunState(
        run_id="run_audit_demo",
        request=RunRequest(idea="audit demo"),
        status=status,
        current_stage=current_stage,
    )


def test_run_audit_passes_ordered_stage_event_stream():
    run = _run_state(status="completed", current_stage="completed")
    for stage in (
        "chief_screenwriter",
        "deepseek_polish",
        "quality_gate",
        "gpt_prompt_writer",
        "gpt_prompt_audit",
        "final_prompts",
    ):
        run.add_event("stage_started", stage=stage)
        run.add_event("stage_completed", stage=stage)
    run.add_event("run_completed")

    report = audit_run_state(run)

    assert report["valid"] is True
    assert report["summary"] == {"passed": 4, "warnings": 0, "failed": 0}
    assert report["stage_path"] == [
        "chief_screenwriter",
        "deepseek_polish",
        "quality_gate",
        "gpt_prompt_writer",
        "gpt_prompt_audit",
        "final_prompts",
    ]


def test_run_audit_flags_stage_order_regression_and_unknown_stage():
    run = _run_state()
    run.add_event("stage_started", stage="deepseek_polish")
    run.add_event("stage_completed", stage="deepseek_polish")
    run.add_event("stage_started", stage="chief_screenwriter")
    run.add_event("stage_started", stage="not_a_stage")

    report = audit_run_state(run)
    checks = {check["id"]: check for check in report["checks"]}

    assert report["valid"] is False
    assert checks["stage_order"]["status"] == "fail"
    assert checks["stage_order"]["details"]["regressions"][0]["stage"] == "chief_screenwriter"
    assert checks["known_stage_names"]["status"] == "fail"
    assert checks["known_stage_names"]["details"]["unknown_stages"] == ["not_a_stage"]
    assert "inspect_run_events" in report["suggested_actions"]


def test_run_audit_flags_failed_run_without_failure_record():
    run = _run_state(status="failed", current_stage="failed")
    run.failed_stage = "gpt_prompt_writer"
    run.add_event("stage_started", stage="gpt_prompt_writer")
    run.add_event("run_failed", stage="gpt_prompt_writer", message="boom")

    report = audit_run_state(run)
    checks = {check["id"]: check for check in report["checks"]}

    assert report["valid"] is False
    assert checks["failure_record"]["status"] == "fail"
    assert checks["failure_record"]["details"]["status"] == "failed"


def test_run_audit_reports_retryable_failure_action():
    run = _run_state(status="failed", current_stage="failed")
    run.failed_stage = "deepseek_polish"
    run.last_failure = FailureRecord(
        stage="deepseek_polish",
        category="transient",
        code="temporary_model_error",
        retryable=True,
    )
    run.failure_records.append(run.last_failure)
    run.add_event("stage_started", stage="deepseek_polish")
    run.add_event("run_failed", stage="deepseek_polish")

    report = audit_run_state(run)

    assert report["suggested_actions"] == ["retry_from_stage"]
    assert report["retry_from_stage"] == "deepseek_polish"


def test_api_run_audit_returns_report_for_persisted_run():
    store = InMemoryRunStore()
    run = _run_state(status="completed", current_stage="completed")
    run.add_event("stage_started", stage="chief_screenwriter")
    run.add_event("stage_completed", stage="chief_screenwriter")
    run.add_event("run_completed")
    store.save(run)
    client = TestClient(
        create_app(
            StoryRunOrchestrator(
                provider=FakeModelProvider.minimal_success(),
                store=store,
            )
        )
    )

    response = client.get(f"/api/runs/{run.run_id}/audit")

    assert response.status_code == 200
    body = response.json()
    assert body["run_id"] == run.run_id
    assert body["valid"] is True
