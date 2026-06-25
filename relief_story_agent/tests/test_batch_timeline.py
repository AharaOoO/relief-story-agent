from __future__ import annotations

import json
import subprocess
import sys

from fastapi.testclient import TestClient

from relief_story_agent.api import create_app
from relief_story_agent.batch_timeline import build_batch_timeline
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


def test_build_batch_timeline_summarizes_item_progress_outputs_and_recovery(tmp_path):
    video_path = tmp_path / "publish.mp4"
    video_path.write_bytes(b"video")
    completed = RunState(
        run_id="run_batch_done",
        request=RunRequest(idea="done idea", output_root=str(tmp_path)),
        status="completed",
        current_stage="completed",
        comfyui_outputs=[
            ComfyUIOutput(
                prompt_id="prompt_done",
                filename="publish.mp4",
                media_type="video",
                local_path=str(video_path),
            )
        ],
    )
    completed.add_event("stage_started", stage="chief_screenwriter")
    completed.add_event("stage_completed", stage="chief_screenwriter")
    failed = RunState(
        run_id="run_batch_failed",
        request=RunRequest(idea="failed idea", output_root=str(tmp_path)),
        status="failed",
        current_stage="gpt_prompt_audit",
        failed_stage="gpt_prompt_audit",
        last_failure=FailureRecord(
            stage="gpt_prompt_audit",
            category="validation",
            code="audit_failed",
            retryable=True,
            message="prompt audit failed",
        ),
        error="prompt audit failed",
    )
    failed.add_event("stage_started", stage="chief_screenwriter")
    failed.add_event("stage_completed", stage="chief_screenwriter")
    failed.add_event("stage_started", stage="gpt_prompt_audit")
    failed.add_event("run_failed", stage="gpt_prompt_audit")
    batch = BatchRunState(
        batch_id="batch_timeline",
        status="partial_failed",
        paused=False,
        summary={"total": 2, "completed": 1, "failed": 1},
        items=[
            BatchRunItem(
                index=0,
                run_id=completed.run_id,
                idea="done idea",
                status="completed",
                current_stage="completed",
            ),
            BatchRunItem(
                index=1,
                run_id=failed.run_id,
                idea="failed idea",
                status="failed",
                current_stage="gpt_prompt_audit",
            ),
        ],
    )

    timeline = build_batch_timeline(batch, [completed, failed])

    assert timeline["batch_id"] == "batch_timeline"
    assert timeline["progress"] == {
        "item_count": 2,
        "known_run_count": 2,
        "completed_count": 1,
        "failed_count": 1,
        "running_count": 0,
        "publish_ready_count": 1,
        "retryable_count": 1,
        "percent": 50,
    }
    assert timeline["items"][0]["publish_ready"] is True
    assert timeline["items"][0]["primary_video_path"] == str(video_path)
    assert timeline["items"][1]["retryable"] is True
    assert timeline["items"][1]["retry_from_stage"] == "gpt_prompt_audit"
    assert timeline["items"][1]["active_stage"] == "gpt_prompt_audit"
    assert timeline["links"]["recovery_plan"] == "/api/batches/batch_timeline/recovery-plan"


def test_api_batch_timeline_returns_persisted_batch_timeline(tmp_path):
    store = InMemoryRunStore()
    run = RunState(
        run_id="run_api_batch_timeline",
        request=RunRequest(idea="api batch timeline", output_root=str(tmp_path)),
        status="completed",
        current_stage="completed",
    )
    run.add_event("stage_started", stage="chief_screenwriter")
    run.add_event("stage_completed", stage="chief_screenwriter")
    batch = BatchRunState(
        batch_id="batch_api_timeline",
        status="completed",
        summary={"total": 1, "completed": 1},
        items=[
            BatchRunItem(
                index=0,
                run_id=run.run_id,
                idea="api batch timeline",
                status="completed",
                current_stage="completed",
            )
        ],
    )
    store.save(run)
    store.save_batch(batch)
    client = TestClient(
        create_app(
            StoryRunOrchestrator(
                provider=FakeModelProvider.minimal_success(),
                store=store,
            )
        )
    )

    response = client.get("/api/batches/batch_api_timeline/timeline")

    assert response.status_code == 200
    body = response.json()
    assert body["batch_id"] == "batch_api_timeline"
    assert body["progress"]["completed_count"] == 1
    assert body["items"][0]["run_id"] == run.run_id
    assert body["items"][0]["stage_percent"] > 0


def test_api_batch_diagnostics_tolerate_missing_child_run_state():
    store = InMemoryRunStore()
    batch = BatchRunState(
        batch_id="batch_missing_child",
        status="running",
        summary={"total": 1, "running": 1},
        items=[
            BatchRunItem(
                index=0,
                run_id="run_missing_child",
                idea="missing child",
                status="running",
                current_stage="comfyui",
            )
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

    for path in (
        "/api/batches/batch_missing_child/timeline",
        "/api/batches/batch_missing_child/artifacts",
        "/api/batches/batch_missing_child/recovery-plan",
        "/api/batches/batch_missing_child/health",
    ):
        response = client.get(path)

        assert response.status_code == 200, path
        body = response.json()
        assert body["batch_id"] == "batch_missing_child"

    timeline = client.get("/api/batches/batch_missing_child/timeline").json()
    assert timeline["items"][0]["error"] == "run not found"
    assert timeline["items"][0]["recommended_action"]["code"] == "inspect_missing_run"

    recovery = client.get("/api/batches/batch_missing_child/recovery-plan").json()
    assert recovery["items"][0]["action_code"] == "inspect_missing_run"


def test_cli_batch_timeline_fetches_batch_timeline():
    from relief_story_agent.tests.test_cli import _CliApiServer

    server = _CliApiServer({"batch_id": "batch_cli", "progress": {"percent": 50}})

    with server:
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "relief_story_agent.cli",
                "batch-timeline",
                "--server",
                server.url,
                "--batch-id",
                "batch_cli",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )

    assert completed.returncode == 0
    assert json.loads(completed.stdout)["progress"]["percent"] == 50
    recorded = server.requests[0]
    assert recorded["method"] == "GET"
    assert recorded["path"] == "/api/batches/batch_cli/timeline"
