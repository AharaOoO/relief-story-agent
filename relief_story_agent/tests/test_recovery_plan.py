from fastapi.testclient import TestClient

from relief_story_agent.api import create_app
from relief_story_agent.models import (
    BatchRunItem,
    BatchRunState,
    ComfyUIOutput,
    FailureRecord,
    RunRequest,
    RunState,
)
from relief_story_agent.orchestrator import InMemoryRunStore, StoryRunOrchestrator
from relief_story_agent.providers import FakeModelProvider


def test_batch_recovery_plan_classifies_publish_retry_manual_and_wait_items(tmp_path):
    store = InMemoryRunStore()
    runs = [
        RunState(
            run_id="run_publish",
            request=RunRequest(idea="publish", output_root=str(tmp_path)),
            status="completed",
            current_stage="completed",
            comfyui_outputs=[
                ComfyUIOutput(
                    prompt_id="prompt_publish",
                    filename="publish.mp4",
                    media_type="video",
                    local_path=str(tmp_path / "publish.mp4"),
                )
            ],
        ),
        RunState(
            run_id="run_retry",
            request=RunRequest(idea="retry", output_root=str(tmp_path)),
            status="failed",
            current_stage="failed",
            failed_stage="deepseek_polish",
            error="temporary model timeout",
        ),
        RunState(
            run_id="run_template",
            request=RunRequest(idea="template", output_root=str(tmp_path)),
            status="failed",
            current_stage="failed",
            failed_stage="gpt_prompt_writer",
            error="Template missing required placeholder(s): script_json",
        ),
        RunState(
            run_id="run_mapping",
            request=RunRequest(idea="mapping", output_root=str(tmp_path)),
            status="failed",
            current_stage="failed",
            failed_stage="comfyui",
            error="placeholder_map 'positive' source was not found in shot",
        ),
        RunState(
            run_id="run_running",
            request=RunRequest(idea="running", output_root=str(tmp_path)),
            status="running",
            current_stage="gpt_prompt_audit",
        ),
    ]
    for run in runs:
        store.save(run)
    batch = BatchRunState(
        batch_id="batch_recovery",
        status="partial_failed",
        summary={"total": 5, "completed": 1, "failed": 3, "running": 1},
        items=[
            BatchRunItem(index=index, run_id=run.run_id, idea=run.request.idea, status=run.status, current_stage=run.current_stage)
            for index, run in enumerate(runs)
        ],
    )
    store.save_batch(batch)
    app = create_app(
        StoryRunOrchestrator(
            provider=FakeModelProvider.minimal_success(),
            store=store,
        )
    )
    client = TestClient(app)

    response = client.get("/api/batches/batch_recovery/recovery-plan")

    assert response.status_code == 200
    body = response.json()
    assert body["batch_id"] == "batch_recovery"
    assert body["summary"]["total_items"] == 5
    assert body["summary"]["publish_ready_count"] == 1
    assert body["summary"]["auto_retryable_count"] == 1
    assert body["summary"]["manual_review_count"] == 2
    assert body["summary"]["wait_count"] == 1
    assert body["summary"]["by_action"]["publish"] == 1
    assert body["summary"]["by_action"]["retry_from_stage"] == 1
    assert body["summary"]["by_action"]["fix_template"] == 1
    assert body["summary"]["by_action"]["check_comfyui_mapping"] == 1
    assert body["summary"]["by_action"]["wait"] == 1

    plans = {item["run_id"]: item for item in body["items"]}
    assert plans["run_publish"]["automation_level"] == "publish"
    assert plans["run_publish"]["primary_video_path"].endswith("publish.mp4")
    assert plans["run_retry"]["automation_level"] == "auto"
    assert plans["run_retry"]["safe_to_auto_execute"] is True
    assert plans["run_retry"]["retry_from_stage"] == "deepseek_polish"
    assert plans["run_retry"]["endpoint"] == "/api/runs/run_retry/retry"
    assert plans["run_retry"]["request_payload"] == {"from_stage": "deepseek_polish"}
    assert plans["run_template"]["automation_level"] == "manual"
    assert plans["run_template"]["safe_to_auto_execute"] is False
    assert plans["run_template"]["blocking_reason"] == "Prompt template must be fixed before retry."
    assert plans["run_mapping"]["blocking_reason"] == "ComfyUI workflow or placeholder mapping must be inspected before retry."
    assert plans["run_running"]["automation_level"] == "wait"


def test_recovery_plan_exposes_structured_failure_and_holds_unknown(tmp_path):
    run = RunState(
        run_id="run_recovery_unknown",
        request=RunRequest(idea="unknown", output_root=str(tmp_path)),
        status="failed",
        current_stage="failed",
        failed_stage="deepseek_polish",
        last_failure=FailureRecord(
            stage="deepseek_polish",
            category="unknown",
            code="unknown_error",
            retryable=False,
            message="surprising failure",
        ),
    )
    batch = BatchRunState(
        batch_id="batch_recovery_unknown",
        items=[
            BatchRunItem(
                index=0,
                run_id=run.run_id,
                idea="unknown",
                status="failed",
                current_stage="failed",
            )
        ],
    )
    store = InMemoryRunStore()
    store.save(run)
    store.save_batch(batch)
    app = create_app(
        StoryRunOrchestrator(
            provider=FakeModelProvider.minimal_success(),
            store=store,
        )
    )
    client = TestClient(app)

    response = client.get("/api/batches/batch_recovery_unknown/recovery-plan")

    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["safe_to_auto_execute"] is False
    assert item["action_code"] == "manual_review"
    assert item["last_failure"]["category"] == "unknown"


def test_batch_recovery_execute_runs_safe_retries_and_skips_manual_items(tmp_path):
    store = InMemoryRunStore()
    provider = FakeModelProvider.minimal_success()
    retryable = RunState(
        run_id="run_retry_exec",
        request=RunRequest(idea="retry exec", output_root=str(tmp_path)),
        status="failed",
        current_stage="failed",
        failed_stage="deepseek_polish",
        error="temporary model timeout",
        selected_core=provider.responses["chief_screenwriter"]["core_candidates"][0],
        script=provider.responses["chief_screenwriter"]["draft_script"],
    )
    manual = RunState(
        run_id="run_template_exec",
        request=RunRequest(idea="template exec", output_root=str(tmp_path)),
        status="failed",
        current_stage="failed",
        failed_stage="gpt_prompt_writer",
        error="Template missing required placeholder(s): script_json",
    )
    store.save(retryable)
    store.save(manual)
    batch = BatchRunState(
        batch_id="batch_recovery_exec",
        status="failed",
        summary={"total": 2, "failed": 2},
        items=[
            BatchRunItem(index=0, run_id=retryable.run_id, idea=retryable.request.idea, status=retryable.status, current_stage=retryable.current_stage),
            BatchRunItem(index=1, run_id=manual.run_id, idea=manual.request.idea, status=manual.status, current_stage=manual.current_stage),
        ],
    )
    store.save_batch(batch)
    app = create_app(StoryRunOrchestrator(provider=provider, store=store))
    client = TestClient(app)

    response = client.post("/api/batches/batch_recovery_exec/recover")

    assert response.status_code == 200
    body = response.json()
    assert body["batch_id"] == "batch_recovery_exec"
    assert body["dry_run"] is False
    assert body["summary"]["executed_count"] == 1
    assert body["summary"]["skipped_count"] == 1
    executed = {item["run_id"]: item for item in body["executed"]}
    skipped = {item["run_id"]: item for item in body["skipped"]}
    assert executed["run_retry_exec"]["action_code"] == "retry_from_stage"
    assert executed["run_retry_exec"]["status_after"] == "completed"
    assert skipped["run_template_exec"]["action_code"] == "fix_template"
    assert skipped["run_template_exec"]["reason"] == "not safe to auto execute"
    assert store.get("run_retry_exec").status == "completed"
    assert store.get("run_template_exec").status == "failed"
    assert body["after_plan"]["summary"]["by_action"]["inspect_outputs"] == 1


def test_batch_recovery_execute_dry_run_does_not_change_state(tmp_path):
    store = InMemoryRunStore()
    retryable = RunState(
        run_id="run_retry_dry",
        request=RunRequest(idea="retry dry", output_root=str(tmp_path)),
        status="failed",
        current_stage="failed",
        failed_stage="deepseek_polish",
        error="temporary model timeout",
    )
    store.save(retryable)
    batch = BatchRunState(
        batch_id="batch_recovery_dry",
        status="failed",
        summary={"total": 1, "failed": 1},
        items=[
            BatchRunItem(index=0, run_id=retryable.run_id, idea=retryable.request.idea, status=retryable.status, current_stage=retryable.current_stage),
        ],
    )
    store.save_batch(batch)
    app = create_app(
        StoryRunOrchestrator(
            provider=FakeModelProvider.minimal_success(),
            store=store,
        )
    )
    client = TestClient(app)

    response = client.post(
        "/api/batches/batch_recovery_dry/recover",
        json={"dry_run": True},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["dry_run"] is True
    assert body["summary"]["would_execute_count"] == 1
    assert body["summary"]["executed_count"] == 0
    assert body["would_execute"][0]["run_id"] == "run_retry_dry"
    assert store.get("run_retry_dry").status == "failed"


def test_batch_recovery_plan_infers_retry_stage_from_timeline_when_failed_stage_is_missing(tmp_path):
    store = InMemoryRunStore()
    interrupted = RunState(
        run_id="run_timeline_retry",
        request=RunRequest(idea="timeline retry", output_root=str(tmp_path)),
        status="failed",
        current_stage="failed",
        error="temporary model timeout",
    )
    interrupted.add_event("stage_started", stage="chief_screenwriter")
    interrupted.add_event("stage_completed", stage="chief_screenwriter")
    interrupted.add_event("stage_started", stage="deepseek_polish")
    store.save(interrupted)
    batch = BatchRunState(
        batch_id="batch_timeline_recovery",
        status="failed",
        summary={"total": 1, "failed": 1},
        items=[
            BatchRunItem(
                index=0,
                run_id=interrupted.run_id,
                idea=interrupted.request.idea,
                status=interrupted.status,
                current_stage=interrupted.current_stage,
            )
        ],
    )
    store.save_batch(batch)
    app = create_app(
        StoryRunOrchestrator(
            provider=FakeModelProvider.minimal_success(),
            store=store,
        )
    )
    client = TestClient(app)

    response = client.get("/api/batches/batch_timeline_recovery/recovery-plan")

    body = response.json()
    item = body["items"][0]
    assert response.status_code == 200
    assert item["action_code"] == "retry_from_stage"
    assert item["safe_to_auto_execute"] is True
    assert item["retry_from_stage"] == "deepseek_polish"
    assert item["request_payload"] == {"from_stage": "deepseek_polish"}
    assert item["timeline_diagnostics"]["inferred_retry_from_stage"] == "deepseek_polish"
    assert item["timeline_diagnostics"]["open_stages"] == ["deepseek_polish"]
