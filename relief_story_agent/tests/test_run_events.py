from __future__ import annotations

from fastapi.testclient import TestClient

from relief_story_agent.api import create_app
from relief_story_agent.models import RunRequest
from relief_story_agent.orchestrator import InMemoryRunStore, StoryRunOrchestrator
from relief_story_agent.providers import FakeModelProvider
from relief_story_agent.scheduler import PersistentRunScheduler
from relief_story_agent.storage import JsonFileRunStore


def test_run_events_record_stage_timeline_and_can_be_polled():
    store = InMemoryRunStore()
    orchestrator = StoryRunOrchestrator(provider=FakeModelProvider.minimal_success(), store=store)
    scheduler = PersistentRunScheduler(orchestrator, max_workers=1)
    app = create_app(orchestrator, scheduler=scheduler)

    with TestClient(app) as client:
        created = client.post("/api/runs", json={"idea": "事件流", "approval_mode": "auto"})
        run_id = created.json()["run_id"]
        assert scheduler.wait_for_idle(timeout=5)

        response = client.get(f"/api/runs/{run_id}/events")
        assert response.status_code == 200
        events = response.json()["events"]
        names = [event["event_type"] for event in events]

        assert names[:2] == ["run_queued", "run_claimed"]
        assert "stage_started" in names
        assert "stage_completed" in names
        assert names[-1] == "run_completed"
        assert [event["sequence"] for event in events] == list(range(1, len(events) + 1))
        assert response.json()["next_cursor"] == events[-1]["sequence"]
        assert response.json()["is_terminal"] is True

        after = events[-2]["sequence"]
        tail = client.get(f"/api/runs/{run_id}/events", params={"after": after}).json()
        assert [event["event_type"] for event in tail["events"]] == ["run_completed"]
        assert tail["next_cursor"] == events[-1]["sequence"]

        empty = client.get(
            f"/api/runs/{run_id}/events",
            params={"after": tail["next_cursor"]},
        ).json()
        assert empty["events"] == []
        assert empty["next_cursor"] == tail["next_cursor"]


def test_run_events_are_persisted_with_json_store(tmp_path):
    store = JsonFileRunStore(tmp_path / "state")
    orchestrator = StoryRunOrchestrator(provider=FakeModelProvider.minimal_success(), store=store)
    scheduler = PersistentRunScheduler(orchestrator, max_workers=1)

    run = scheduler.create_run(RunRequest(idea="持久事件", approval_mode="auto"))
    assert scheduler.wait_for_idle(timeout=5)
    scheduler.shutdown()

    reloaded = JsonFileRunStore(tmp_path / "state").get(run.run_id)
    assert [event.event_type for event in reloaded.events][-1] == "run_completed"
    assert all(event.run_id == run.run_id for event in reloaded.events)
