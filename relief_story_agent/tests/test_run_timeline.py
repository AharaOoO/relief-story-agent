from __future__ import annotations

import json
import subprocess
import sys

from fastapi.testclient import TestClient

from relief_story_agent.api import create_app
from relief_story_agent.models import ComfyUIOutput, ComfyUIRunConfig, RunRequest, RunState
from relief_story_agent.orchestrator import InMemoryRunStore, StoryRunOrchestrator
from relief_story_agent.providers import FakeModelProvider
from relief_story_agent.run_timeline import build_run_timeline


def test_build_run_timeline_summarizes_stage_progress_and_outputs(tmp_path):
    video_path = tmp_path / "out.mp4"
    video_path.write_bytes(b"video")
    run = RunState(
        run_id="run_timeline",
        request=RunRequest(
            idea="timeline demo",
            output_root=str(tmp_path),
            comfyui=ComfyUIRunConfig(enabled=True, endpoint="http://comfy.local"),
        ),
        status="running",
        current_stage="comfyui",
        last_completed_stage="artifacts",
        artifact_dir=str(tmp_path / "run_timeline"),
        comfyui_prompt_ids=["prompt_1"],
        comfyui_outputs=[
            ComfyUIOutput(
                prompt_id="prompt_1",
                filename="out.mp4",
                media_type="video",
                local_path=str(video_path),
            )
        ],
    )
    for stage in (
        "chief_screenwriter",
        "deepseek_polish",
        "quality_gate",
        "gpt_prompt_writer",
        "gpt_prompt_audit",
        "final_prompts",
        "artifacts",
    ):
        run.add_event("stage_started", stage=stage)
        run.add_event("stage_completed", stage=stage)
    run.add_event("stage_started", stage="comfyui")

    timeline = build_run_timeline(run)
    stages = {stage["stage_id"]: stage for stage in timeline["stages"]}

    assert timeline["run_id"] == "run_timeline"
    assert timeline["progress"]["completed_count"] == 7
    assert timeline["progress"]["active_stage"] == "comfyui"
    assert timeline["progress"]["percent"] == 88
    assert stages["comfyui"]["status"] == "running"
    assert stages["artifacts"]["status"] == "completed"
    assert timeline["outputs"]["video_count"] == 1
    assert timeline["outputs"]["primary_video_path"] == str(video_path)
    assert timeline["links"]["artifacts"] == "/api/runs/run_timeline/artifacts"
    assert timeline["suggested_actions"] == []


def test_api_run_timeline_returns_persisted_run_timeline(tmp_path):
    store = InMemoryRunStore()
    run = RunState(
        run_id="run_api_timeline",
        request=RunRequest(idea="api timeline", output_root=str(tmp_path)),
        status="completed",
        current_stage="completed",
    )
    run.add_event("stage_started", stage="chief_screenwriter")
    run.add_event("stage_completed", stage="chief_screenwriter")
    store.save(run)
    client = TestClient(
        create_app(
            StoryRunOrchestrator(
                provider=FakeModelProvider.minimal_success(),
                store=store,
            )
        )
    )

    response = client.get(f"/api/runs/{run.run_id}/timeline")

    assert response.status_code == 200
    body = response.json()
    assert body["run_id"] == run.run_id
    assert body["progress"]["completed_count"] == 1
    assert body["links"]["events"] == f"/api/runs/{run.run_id}/events"


def test_cli_run_timeline_fetches_run_timeline():
    from relief_story_agent.tests.test_cli import _CliApiServer

    server = _CliApiServer({"run_id": "run_cli", "progress": {"percent": 50}})

    with server:
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "relief_story_agent.cli",
                "run-timeline",
                "--server",
                server.url,
                "--run-id",
                "run_cli",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )

    assert completed.returncode == 0
    assert json.loads(completed.stdout)["progress"]["percent"] == 50
    recorded = server.requests[0]
    assert recorded["method"] == "GET"
    assert recorded["path"] == "/api/runs/run_cli/timeline"
