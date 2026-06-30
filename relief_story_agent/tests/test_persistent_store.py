from __future__ import annotations

import threading
import time
from pathlib import Path

from fastapi.testclient import TestClient

from relief_story_agent import storage
from relief_story_agent.models import BatchRunRequest, RunRequest, RunState
from relief_story_agent.orchestrator import StoryRunOrchestrator
from relief_story_agent.providers import FakeModelProvider
from relief_story_agent.server import build_app
from relief_story_agent.storage import JsonFileRunStore


def test_server_health_reports_resource_limits(tmp_path):
    app = build_app(
        state_dir=str(tmp_path / "state"),
        provider=FakeModelProvider.minimal_success(),
        image_generation_concurrency=2,
        comfyui_submission_concurrency=1,
    )

    with TestClient(app) as client:
        body = client.get("/api/health").json()

    assert body["resources"] == {
        "image_generation_concurrency": 2,
        "comfyui_submission_concurrency": 1,
    }


def test_json_file_store_persists_runs_and_batches_across_instances(tmp_path):
    state_dir = tmp_path / "state"
    store = JsonFileRunStore(state_dir)
    orchestrator = StoryRunOrchestrator(provider=FakeModelProvider.minimal_success(), store=store)

    batch = orchestrator.create_batch(
        BatchRunRequest(
            items=[
                RunRequest(idea="便利店夜晚", approval_mode="auto"),
                RunRequest(idea="压力小怪物", approval_mode="manual"),
            ]
        )
    )

    reloaded = JsonFileRunStore(state_dir)
    saved_batch = reloaded.get_batch(batch.batch_id)
    saved_auto_run = reloaded.get(saved_batch.items[0].run_id)
    saved_manual_run = reloaded.get(saved_batch.items[1].run_id)

    assert saved_batch.batch_id == batch.batch_id
    assert saved_batch.summary["completed"] == 1
    assert saved_batch.summary["awaiting_approval"] == 1
    assert saved_auto_run.request.idea == "便利店夜晚"
    assert saved_auto_run.status == "completed"
    assert len(saved_auto_run.model_attempts) == 5
    assert saved_auto_run.model_usage_summary.total_requests == 5
    assert saved_manual_run.request.idea == "压力小怪物"
    assert saved_manual_run.status == "awaiting_approval"


def test_json_file_store_uses_unique_atomic_temp_files_across_instances(
    tmp_path,
    monkeypatch,
):
    state_dir = tmp_path / "state"
    first = JsonFileRunStore(state_dir)
    second = JsonFileRunStore(state_dir)
    initial = RunState(run_id="run_shared", request=RunRequest(idea="shared"))
    first.save(initial)

    real_replace = storage.os.replace
    errors: list[Exception] = []
    source_paths: list[str] = []

    def recording_replace(source, destination):
        source_paths.append(str(source))
        real_replace(source, destination)

    monkeypatch.setattr(storage.os, "replace", recording_replace)

    def save(store, stage):
        try:
            store.save(initial.model_copy(update={"current_stage": stage}))
        except Exception as exc:
            errors.append(exc)

    threads = [
        threading.Thread(target=save, args=(first, "chief_screenwriter")),
        threading.Thread(target=save, args=(second, "deepseek_polish")),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=3)

    assert errors == []
    assert len(set(source_paths)) == 2
    assert JsonFileRunStore(state_dir).get("run_shared").current_stage in {
        "chief_screenwriter",
        "deepseek_polish",
    }


def test_json_file_store_retries_transient_replace_permission_error(
    tmp_path,
    monkeypatch,
):
    store = JsonFileRunStore(tmp_path / "state")
    run = RunState(run_id="run_replace_retry", request=RunRequest(idea="retry replace"))
    real_replace = storage.os.replace
    attempts = 0

    def flaky_replace(source, destination):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise PermissionError(13, "temporarily locked")
        real_replace(source, destination)

    monkeypatch.setattr(storage.os, "replace", flaky_replace)

    store.save(run)

    assert attempts == 2
    assert store.get(run.run_id).request.idea == "retry replace"


def test_json_file_store_retries_transient_read_permission_error(
    tmp_path,
    monkeypatch,
):
    store = JsonFileRunStore(tmp_path / "state")
    run = RunState(run_id="run_read_retry", request=RunRequest(idea="retry read"))
    store.save(run)
    real_read_text = Path.read_text
    attempts = 0

    def flaky_read_text(path, *args, **kwargs):
        nonlocal attempts
        if path.name == "run_read_retry.json" and attempts == 0:
            attempts += 1
            raise PermissionError(13, "temporarily locked")
        return real_read_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", flaky_read_text)

    assert store.get(run.run_id).request.idea == "retry read"
    assert attempts == 1


def test_batch_idempotency_key_survives_store_restart(tmp_path):
    state_dir = tmp_path / "state"
    provider = FakeModelProvider.minimal_success()
    first_orchestrator = StoryRunOrchestrator(
        provider=provider,
        store=JsonFileRunStore(state_dir),
    )
    request = BatchRunRequest(
        idempotency_key="restart-safe",
        items=[RunRequest(idea="restart safe", approval_mode="auto")],
    )

    first = first_orchestrator.create_batch(request)
    calls_after_first = list(provider.calls)
    restarted = StoryRunOrchestrator(
        provider=provider,
        store=JsonFileRunStore(state_dir),
    )
    second = restarted.create_batch(request)

    assert second.batch_id == first.batch_id
    assert second.items[0].run_id == first.items[0].run_id
    assert provider.calls == calls_after_first


def test_run_idempotency_key_survives_store_restart(tmp_path):
    state_dir = tmp_path / "state"
    provider = FakeModelProvider.minimal_success()
    first_orchestrator = StoryRunOrchestrator(
        provider=provider,
        store=JsonFileRunStore(state_dir),
    )
    request = RunRequest(
        idempotency_key="run-restart-safe",
        idea="restart safe single",
        approval_mode="auto",
    )

    first = first_orchestrator.create_run(request)
    calls_after_first = list(provider.calls)
    restarted = StoryRunOrchestrator(
        provider=provider,
        store=JsonFileRunStore(state_dir),
    )
    second = restarted.create_run(request)

    assert second.run_id == first.run_id
    assert second.status == "completed"
    assert provider.calls == calls_after_first


def test_server_build_app_uses_persistent_state_dir(tmp_path):
    state_dir = tmp_path / "server_state"
    app = build_app(state_dir=str(state_dir), provider=FakeModelProvider.minimal_success())
    with TestClient(app) as client:
        response = client.post(
            "/api/runs",
            json={"idea": "持久化便利店", "approval_mode": "auto"},
        )

        assert response.status_code == 202
        run_id = response.json()["run_id"]
        reloaded = JsonFileRunStore(state_dir)
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            if reloaded.get(run_id).status == "completed":
                break
            time.sleep(0.01)
        saved = reloaded.get(run_id)
        assert saved.request.idea == "持久化便利店"
        assert saved.status == "completed"


def test_server_build_app_health_exposes_background_scheduler(tmp_path):
    state_dir = tmp_path / "server_state"
    app = build_app(state_dir=str(state_dir), provider=FakeModelProvider.minimal_success())

    with TestClient(app) as client:
        response = client.get("/api/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["scheduler"]["enabled"] is True
    assert body["scheduler"]["status"]["started"] is True
    assert body["state"]["persistent"] is True


def test_server_build_app_exposes_configurable_recovery_poll_interval(tmp_path):
    state_dir = tmp_path / "server_state"
    app = build_app(
        state_dir=str(state_dir),
        provider=FakeModelProvider.minimal_success(),
        recovery_poll_seconds=1.25,
    )

    with TestClient(app) as client:
        response = client.get("/api/health")

    assert response.status_code == 200
    body = response.json()
    assert body["scheduler"]["status"]["recovery_poll_seconds"] == 1.25
