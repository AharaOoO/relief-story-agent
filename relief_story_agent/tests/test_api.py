from fastapi.testclient import TestClient

from relief_story_agent.api import create_app
from relief_story_agent.acceptance import write_acceptance_report
from relief_story_agent.orchestrator import InMemoryRunStore, StoryRunOrchestrator
from relief_story_agent.providers import FakeModelProvider


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
    assert body["blocking_checks"][0]["id"] == "export"
    assert "export_and_validate_batch" in body["suggested_actions"]
