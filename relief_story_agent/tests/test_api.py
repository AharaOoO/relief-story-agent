import json

from fastapi.testclient import TestClient

from relief_story_agent.api import create_app
from relief_story_agent.acceptance import write_acceptance_report
from relief_story_agent.orchestrator import InMemoryRunStore, StoryRunOrchestrator
from relief_story_agent.providers import FakeModelProvider
from relief_story_agent.models import ComfyUIRunConfig, RunRequest
from relief_story_agent.segment_render import build_segment_render_plan


def _segment_api_client(tmp_path):
    workflow = tmp_path / "workflow.json"
    workflow.write_text("{}", encoding="utf-8")
    store = InMemoryRunStore()
    orchestrator = StoryRunOrchestrator(
        provider=FakeModelProvider.minimal_success(),
        store=store,
    )
    run = orchestrator.prepare_run(
        RunRequest(
            idea="segment api",
            output_root=str(tmp_path / "runs"),
            comfyui=ComfyUIRunConfig(
                enabled=True,
                workflow_api_path=str(workflow),
            ),
        )
    )
    storyboard = [
        {"shot_id": 1, "time_range": "0-10s", "image_prompt": "one"},
        {"shot_id": 2, "time_range": "10-20s", "image_prompt": "two"},
    ]
    run.final_storyboard = storyboard
    run.segment_renders = build_segment_render_plan(
        storyboard,
        target_duration_seconds=0,
    )
    run.segment_renders[0].status = "completed"
    run.segment_renders[1].status = "failed"
    run.segment_renders[1].error = "image failed"
    run.status = "failed"
    run.failed_stage = "four_grid_asset"
    store.save(run)
    return TestClient(create_app(orchestrator)), store, run


def test_segment_render_plan_and_detail_endpoints(tmp_path):
    client, _, run = _segment_api_client(tmp_path)

    plan = client.get(f"/api/runs/{run.run_id}/render-plan")
    detail = client.get(
        f"/api/runs/{run.run_id}/segments/{run.segment_renders[1].segment_id}"
    )
    missing = client.get(f"/api/runs/{run.run_id}/segments/not-found")

    assert plan.status_code == 200
    assert len(plan.json()["segments"]) == 2
    assert plan.json()["planned_duration_seconds"] == 20
    assert detail.status_code == 200
    assert detail.json()["segment_id"] == run.segment_renders[1].segment_id
    assert missing.status_code == 404
    assert "api_key" not in json.dumps(plan.json()).casefold()


def test_segment_image_retry_is_scoped_and_completed_segment_requires_force(tmp_path):
    client, store, run = _segment_api_client(tmp_path)
    completed_id = run.segment_renders[0].segment_id
    failed_id = run.segment_renders[1].segment_id

    blocked = client.post(
        f"/api/runs/{run.run_id}/segments/{completed_id}/retry-image",
        json={},
    )
    retried = client.post(
        f"/api/runs/{run.run_id}/segments/{failed_id}/retry-image",
        json={"runninghub_site": "cn", "aspect_ratio": "9:16", "resolution": "2k"},
    )

    assert blocked.status_code == 409
    assert retried.status_code == 200
    saved = store.get(run.run_id)
    assert saved.segment_renders[0].status == "completed"
    assert saved.segment_renders[1].status == "planned"
    assert saved.status == "queued"
    assert saved.resume_stage == "four_grid_asset"


def test_api_creates_and_fetches_async_style_run():
    provider = FakeModelProvider.minimal_success()
    store = InMemoryRunStore()
    app = create_app(StoryRunOrchestrator(provider=provider, store=store))
    client = TestClient(app)

    response = client.post(
        "/api/runs",
        json={
            "idea": "便利店多放一双筷子",
            "audience_pressure": "下班后疲惫的人",
            "preferred_style": "现实",
            "duration_seconds": 90,
            "approval_mode": "auto",
        },
    )

    assert response.status_code == 200
    run_id = response.json()["run_id"]
    detail = client.get(f"/api/runs/{run_id}")

    assert detail.status_code == 200
    body = detail.json()
    assert body["run_id"] == run_id
    assert body["status"] == "completed"
    assert body["current_stage"] == "completed"
    assert body["script"]["title"]


def test_api_run_idempotency_key_returns_existing_run():
    provider = FakeModelProvider.minimal_success()
    store = InMemoryRunStore()
    app = create_app(StoryRunOrchestrator(provider=provider, store=store))
    client = TestClient(app)
    payload = {
        "idempotency_key": "run-same-click",
        "idea": "same run",
        "approval_mode": "auto",
    }

    first = client.post("/api/runs", json=payload)
    calls_after_first = list(provider.calls)
    second = client.post("/api/runs", json=payload)

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["run_id"] == first.json()["run_id"]
    assert provider.calls == calls_after_first


def test_api_run_idempotency_conflict_returns_409():
    provider = FakeModelProvider.minimal_success()
    store = InMemoryRunStore()
    app = create_app(StoryRunOrchestrator(provider=provider, store=store))
    client = TestClient(app)

    first = client.post(
        "/api/runs",
        json={
            "idempotency_key": "run-conflict",
            "idea": "first",
            "approval_mode": "auto",
        },
    )
    second = client.post(
        "/api/runs",
        json={
            "idempotency_key": "run-conflict",
            "idea": "changed",
            "approval_mode": "auto",
        },
    )

    assert first.status_code == 200
    assert second.status_code == 409
    assert "different request payload" in second.json()["detail"]


def test_api_lists_runs_with_status_filter_and_limit():
    provider = FakeModelProvider.minimal_success()
    store = InMemoryRunStore()
    app = create_app(StoryRunOrchestrator(provider=provider, store=store))
    client = TestClient(app)

    first = client.post(
        "/api/runs",
        json={"idea": "first completed", "approval_mode": "auto"},
    ).json()
    second = client.post(
        "/api/runs",
        json={"idea": "second completed", "approval_mode": "auto"},
    ).json()
    client.post(
        "/api/runs",
        json={"idea": "manual waiting", "approval_mode": "manual"},
    )

    response = client.get("/api/runs", params={"status": "completed", "limit": 1})

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    assert body["limit"] == 1
    assert len(body["items"]) == 1
    assert body["items"][0]["run_id"] == second["run_id"]
    assert body["items"][0]["idea"] == "second completed"
    assert body["items"][0]["title"]
    assert body["items"][0]["status"] == "completed"


def test_api_cancel_marks_queued_or_running_run_cancelled():
    provider = FakeModelProvider.minimal_success()
    store = InMemoryRunStore()
    orchestrator = StoryRunOrchestrator(provider=provider, store=store)
    app = create_app(orchestrator)
    client = TestClient(app)

    response = client.post(
        "/api/runs",
        json={
            "idea": "雨停之前",
            "audience_pressure": "通勤焦虑",
            "approval_mode": "manual",
        },
    )
    run_id = response.json()["run_id"]

    cancel = client.post(f"/api/runs/{run_id}/cancel")

    assert cancel.status_code == 200
    assert cancel.json()["status"] == "cancelled"


def test_api_health_reports_model_and_scheduler_status():
    provider = FakeModelProvider.minimal_success()
    store = InMemoryRunStore()
    app = create_app(StoryRunOrchestrator(provider=provider, store=store))
    client = TestClient(app)

    response = client.get("/api/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["scheduler"]["enabled"] is False
    assert body["model_config"]["missing_environment_variables"] == []


def test_api_local_acceptance_status_reads_report(tmp_path):
    report_path = write_acceptance_report(
        tmp_path,
        {
            "mode": "local_e2e",
            "status": "completed",
            "checks": [
                {"id": "full_tests", "status": "pass", "evidence": "353 passed"},
                {"id": "export", "status": "manual_pending"},
            ],
        },
    )
    app = create_app(
        StoryRunOrchestrator(
            provider=FakeModelProvider.minimal_success(),
            store=InMemoryRunStore(),
        )
    )
    client = TestClient(app)

    response = client.get(
        "/api/local/acceptance-status",
        params={"report_path": report_path},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["exists"] is True
    assert body["ready_for_release"] is False
    blocking_ids = [check["id"] for check in body["blocking_checks"]]
    assert blocking_ids[0] == "full_tests"
    assert "export" in blocking_ids
    assert body["blocking_checks"][0]["details"]["full_tests_evidence"]["error"] == "missing_pytest_stdout"
    assert "run_full_tests" in body["suggested_actions"]
    assert "export_and_validate_batch" in body["suggested_actions"]
