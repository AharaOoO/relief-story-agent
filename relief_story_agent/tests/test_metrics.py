from fastapi.testclient import TestClient

from relief_story_agent.api import create_app
from relief_story_agent.models import (
    BatchRunItem,
    BatchRunState,
    ComfyUIOutput,
    ModelUsageSummary,
    RunEvent,
    RunRequest,
    RunState,
)
from relief_story_agent.orchestrator import InMemoryRunStore, StoryRunOrchestrator
from relief_story_agent.providers import FakeModelProvider


def test_metrics_api_summarizes_runs_batches_usage_and_publish_ready():
    store = InMemoryRunStore()
    completed = RunState(
        run_id="run_completed",
        request=RunRequest(idea="done"),
        status="completed",
        current_stage="completed",
        created_at="2026-06-24T00:00:00+00:00",
        finished_at="2026-06-24T00:02:00+00:00",
        model_usage_summary=ModelUsageSummary(
            total_requests=4,
            total_attempts=5,
            retry_count=1,
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
            estimated_cost_usd=0.0123,
        ),
        comfyui_outputs=[
            ComfyUIOutput(
                prompt_id="prompt_1",
                filename="done.mp4",
                media_type="video",
                local_path="D:/out/done.mp4",
            )
        ],
    )
    failed = RunState(
        run_id="run_failed",
        request=RunRequest(idea="failed"),
        status="failed",
        current_stage="failed",
        failed_stage="gpt_prompt_audit",
        created_at="2026-06-24T00:00:00+00:00",
        finished_at="2026-06-24T00:01:00+00:00",
        model_usage_summary=ModelUsageSummary(total_tokens=30, estimated_cost_usd=0.004),
    )
    cancelled = RunState(
        run_id="run_cancelled",
        request=RunRequest(idea="cancelled"),
        status="cancelled",
        current_stage="cancelled",
    )
    for run in (completed, failed, cancelled):
        store.save(run)
    store.save_batch(
        BatchRunState(
            batch_id="batch_one",
            status="partial_failed",
            summary={"total": 2, "completed": 1, "failed": 1},
            items=[
                BatchRunItem(
                    index=0,
                    run_id=completed.run_id,
                    idea="done",
                    status="completed",
                    current_stage="completed",
                ),
                BatchRunItem(
                    index=1,
                    run_id=failed.run_id,
                    idea="failed",
                    status="failed",
                    current_stage="failed",
                ),
            ],
        )
    )
    client = TestClient(
        create_app(
            StoryRunOrchestrator(
                provider=FakeModelProvider.minimal_success(),
                store=store,
            )
        )
    )

    response = client.get("/api/metrics")

    assert response.status_code == 200
    body = response.json()
    assert body["runs"]["total"] == 3
    assert body["runs"]["by_status"]["completed"] == 1
    assert body["runs"]["by_status"]["failed"] == 1
    assert body["runs"]["by_failed_stage"]["gpt_prompt_audit"] == 1
    assert body["runs"]["completed_success_rate"] == 1 / 3
    assert body["runs"]["average_duration_seconds"] == 90
    assert body["usage"]["total_tokens"] == 180
    assert body["usage"]["estimated_cost_usd"] == 0.0163
    assert body["usage"]["retry_count"] == 1
    assert body["batches"]["total"] == 1
    assert body["batches"]["by_status"]["partial_failed"] == 1
    assert body["publish"]["ready_run_count"] == 1


def test_metrics_api_handles_empty_state():
    client = TestClient(
        create_app(
            StoryRunOrchestrator(
                provider=FakeModelProvider.minimal_success(),
                store=InMemoryRunStore(),
            )
        )
    )

    response = client.get("/api/metrics")

    assert response.status_code == 200
    body = response.json()
    assert body["runs"]["total"] == 0
    assert body["runs"]["completed_success_rate"] == 0
    assert body["runs"]["average_duration_seconds"] == 0
    assert body["usage"]["total_tokens"] == 0
    assert body["publish"]["ready_run_count"] == 0


def test_batch_health_report_summarizes_stage_bottlenecks_and_recovery_actions():
    store = InMemoryRunStore()
    completed = RunState(
        run_id="run_health_done",
        request=RunRequest(idea="done"),
        status="completed",
        current_stage="completed",
        finished_at="2026-06-24T00:02:00+00:00",
        comfyui_outputs=[
            ComfyUIOutput(
                prompt_id="prompt_done",
                filename="done.mp4",
                media_type="video",
                local_path="D:/out/done.mp4",
            )
        ],
        events=[
            RunEvent(
                sequence=1,
                run_id="run_health_done",
                event_type="stage_started",
                stage="chief_screenwriter",
                timestamp="2026-06-24T00:00:00+00:00",
            ),
            RunEvent(
                sequence=2,
                run_id="run_health_done",
                event_type="stage_completed",
                stage="chief_screenwriter",
                timestamp="2026-06-24T00:00:10+00:00",
            ),
            RunEvent(
                sequence=3,
                run_id="run_health_done",
                event_type="stage_started",
                stage="deepseek_polish",
                timestamp="2026-06-24T00:00:10+00:00",
            ),
            RunEvent(
                sequence=4,
                run_id="run_health_done",
                event_type="stage_completed",
                stage="deepseek_polish",
                timestamp="2026-06-24T00:00:50+00:00",
            ),
        ],
    )
    failed = RunState(
        run_id="run_health_failed",
        request=RunRequest(idea="failed"),
        status="failed",
        current_stage="failed",
        failed_stage="gpt_prompt_audit",
        error="axis issue",
        events=[
            RunEvent(
                sequence=1,
                run_id="run_health_failed",
                event_type="stage_started",
                stage="gpt_prompt_audit",
                timestamp="2026-06-24T00:01:00+00:00",
            )
        ],
    )
    for run in (completed, failed):
        store.save(run)
    batch = BatchRunState(
        batch_id="batch_health",
        status="partial_failed",
        summary={"total": 2, "completed": 1, "failed": 1},
        items=[
            BatchRunItem(index=0, run_id=completed.run_id, idea="done", status="completed", current_stage="completed"),
            BatchRunItem(index=1, run_id=failed.run_id, idea="failed", status="failed", current_stage="failed"),
        ],
    )
    store.save_batch(batch)
    client = TestClient(
        create_app(
            StoryRunOrchestrator(
                provider=FakeModelProvider.minimal_success(),
                store=store,
            )
        )
    )

    response = client.get("/api/batches/batch_health/health")

    assert response.status_code == 200
    body = response.json()
    assert body["batch_id"] == "batch_health"
    assert body["summary"]["total_items"] == 2
    assert body["summary"]["completed_count"] == 1
    assert body["summary"]["failed_count"] == 1
    assert body["summary"]["success_rate"] == 0.5
    assert body["summary"]["publish_ready_count"] == 1
    assert body["bottlenecks"]["failed_stage_counts"] == {"gpt_prompt_audit": 1}
    assert body["bottlenecks"]["recovery_action_counts"]["manual_review_prompt_audit"] == 1
    assert body["stage_performance"]["deepseek_polish"]["average_duration_seconds"] == 40
    assert body["stage_performance"]["gpt_prompt_audit"]["open_count"] == 1
    assert body["open_stage_runs"][0]["run_id"] == "run_health_failed"
    assert body["recommendations"][0]["code"] == "review_prompt_audit"
