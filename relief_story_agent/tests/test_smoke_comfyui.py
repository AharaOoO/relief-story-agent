from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import httpx
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw

from relief_story_agent.api import create_app
from relief_story_agent.orchestrator import InMemoryRunStore, StoryRunOrchestrator
from relief_story_agent.providers import FakeModelProvider
from relief_story_agent.smoke_comfyui import ComfyUISmokeRequest, run_comfyui_smoke
from relief_story_agent.tests.fixtures.ltx23_workflow_factory import (
    build_sanitized_ltx23_workflow,
)


def _write_workflow(path: Path) -> Path:
    path.write_text(
        json.dumps(build_sanitized_ltx23_workflow(), ensure_ascii=False),
        encoding="utf-8",
    )
    return path


def _write_grid(path: Path) -> Path:
    image = Image.new("RGB", (1024, 1024), "white")
    draw = ImageDraw.Draw(image)
    colors = ["red", "green", "blue", "yellow"]
    boxes = [
        (0, 0, 512, 512),
        (512, 0, 1024, 512),
        (0, 512, 512, 1024),
        (512, 512, 1024, 1024),
    ]
    for color, box in zip(colors, boxes):
        image.paste(color, box)
        draw.line(
            (box[0] + 32, box[1] + 32, box[2] - 32, box[3] - 32),
            fill="black",
            width=10,
        )
    image.save(path)
    return path


def _final_storyboard() -> list[dict]:
    return [
        {
            "shot_id": 1,
            "time_range": "0-15s",
            "description": "quiet convenience store",
            "image_prompt": "soft convenience store keyframe",
            "negative_prompt": "shouting, horror, text, watermark",
            "comfyui_inputs": {"seed": 1234},
        }
    ]


def test_smoke_dry_run_writes_preflight_and_patched_workflow_without_upload(tmp_path):
    request = ComfyUISmokeRequest(
        workflow_path=str(_write_workflow(tmp_path / "workflow.json")),
        comfyui_base_url="http://127.0.0.1:8188",
        final_storyboard=_final_storyboard(),
        manual_grid_image_path=str(_write_grid(tmp_path / "grid.png")),
        output_root=str(tmp_path / "out"),
        dry_run=True,
    )

    result = run_comfyui_smoke(request)

    assert result.status == "passed"
    assert result.ready is True
    assert result.prompt_id == ""
    assert result.upload_result == {}
    assert result.artifact_dir
    artifact_dir = Path(result.artifact_dir)
    assert (artifact_dir / "smoke_request.json").exists()
    assert (artifact_dir / "smoke_preflight.json").exists()
    assert (artifact_dir / "smoke_grid_image.png").exists()
    assert (artifact_dir / "smoke_workflow_patched.json").exists()
    assert (artifact_dir / "smoke_result.json").exists()
    assert (artifact_dir / "smoke_logs.jsonl").exists()
    assert not (artifact_dir / "smoke_upload.json").exists()
    assert any(
        check.id == "ltx_injection_points" and check.status == "pass"
        for check in result.preflight
    )
    assert result.patched_replacements["grid_image"]["node"] == "196"


def test_smoke_fails_before_network_when_final_prompts_missing(tmp_path):
    request = ComfyUISmokeRequest(
        workflow_path=str(_write_workflow(tmp_path / "workflow.json")),
        comfyui_base_url="http://127.0.0.1:8188",
        manual_grid_image_path=str(_write_grid(tmp_path / "grid.png")),
        output_root=str(tmp_path / "out"),
        dry_run=True,
    )

    result = run_comfyui_smoke(request)

    assert result.status == "failed"
    assert result.ready is False
    assert result.failure_code == "final_prompts_missing"
    assert Path(result.artifact_dir, "smoke_result.json").exists()


def test_smoke_fails_before_patch_when_grid_image_missing(tmp_path):
    request = ComfyUISmokeRequest(
        workflow_path=str(_write_workflow(tmp_path / "workflow.json")),
        comfyui_base_url="http://127.0.0.1:8188",
        final_storyboard=_final_storyboard(),
        output_root=str(tmp_path / "out"),
        dry_run=True,
    )

    result = run_comfyui_smoke(request)

    assert result.status == "failed"
    assert result.failure_code == "grid_image_missing"
    assert not Path(result.artifact_dir, "smoke_workflow_patched.json").exists()


def test_smoke_reports_missing_workflow_without_patch_exception(tmp_path):
    request = ComfyUISmokeRequest(
        workflow_path=str(tmp_path / "missing_workflow.json"),
        comfyui_base_url="http://127.0.0.1:8188",
        final_storyboard=_final_storyboard(),
        manual_grid_image_path=str(_write_grid(tmp_path / "grid.png")),
        output_root=str(tmp_path / "out"),
        dry_run=True,
    )

    result = run_comfyui_smoke(request)

    assert result.status == "failed"
    assert result.failure_code == "workflow_file_readable"
    assert not Path(result.artifact_dir, "smoke_workflow_patched.json").exists()


def test_smoke_real_run_uploads_grid_and_enqueues_prompt(tmp_path):
    requests: list[tuple[str, str]] = []
    uploaded_name = ""
    prompted_payload: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal uploaded_name, prompted_payload
        requests.append((request.method, request.url.path))
        if request.url.path == "/upload/image":
            body = request.read()
            assert b"smoke_real" in body
            uploaded_name = "smoke_uploaded_grid.png"
            return httpx.Response(
                200,
                json={"name": uploaded_name, "subfolder": "", "type": "input"},
            )
        if request.url.path == "/prompt":
            prompted_payload = json.loads(request.content.decode("utf-8"))
            return httpx.Response(200, json={"prompt_id": prompted_payload["prompt_id"]})
        return httpx.Response(404)

    request = ComfyUISmokeRequest(
        workflow_path=str(_write_workflow(tmp_path / "workflow.json")),
        comfyui_base_url="http://comfy.test",
        final_storyboard=_final_storyboard(),
        manual_grid_image_path=str(_write_grid(tmp_path / "grid.png")),
        output_root=str(tmp_path / "out"),
        run_id="smoke_real",
        dry_run=False,
    )

    result = run_comfyui_smoke(
        request,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    assert result.status == "passed"
    assert result.prompt_id == prompted_payload["prompt_id"]
    assert result.upload_result["filename"] == uploaded_name
    assert ("POST", "/upload/image") in requests
    assert ("POST", "/prompt") in requests
    assert prompted_payload["prompt"]["196"]["inputs"]["image"] == uploaded_name
    assert Path(result.artifact_dir, "smoke_upload.json").exists()


def test_smoke_real_run_reports_upload_failure(tmp_path):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/upload/image":
            return httpx.Response(500, text="upload failed")
        return httpx.Response(404)

    result = run_comfyui_smoke(
        ComfyUISmokeRequest(
            workflow_path=str(_write_workflow(tmp_path / "workflow.json")),
            comfyui_base_url="http://comfy.test",
            final_storyboard=_final_storyboard(),
            manual_grid_image_path=str(_write_grid(tmp_path / "grid.png")),
            output_root=str(tmp_path / "out"),
        ),
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    assert result.status == "failed"
    assert result.failure_code == "comfyui_upload_failed"


def test_smoke_real_run_reports_prompt_failure(tmp_path):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/upload/image":
            return httpx.Response(200, json={"name": "grid.png"})
        if request.url.path == "/prompt":
            return httpx.Response(500, text="prompt failed")
        return httpx.Response(404)

    result = run_comfyui_smoke(
        ComfyUISmokeRequest(
            workflow_path=str(_write_workflow(tmp_path / "workflow.json")),
            comfyui_base_url="http://comfy.test",
            final_storyboard=_final_storyboard(),
            manual_grid_image_path=str(_write_grid(tmp_path / "grid.png")),
            output_root=str(tmp_path / "out"),
        ),
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    assert result.status == "failed"
    assert result.failure_code == "comfyui_prompt_failed"
    assert Path(result.artifact_dir, "smoke_upload.json").exists()


def test_api_smoke_comfyui_dry_run_returns_result(tmp_path):
    app = create_app(
        StoryRunOrchestrator(
            provider=FakeModelProvider.minimal_success(),
            store=InMemoryRunStore(),
        )
    )
    client = TestClient(app)

    response = client.post(
        "/api/smoke/comfyui",
        json={
            "workflow_path": str(_write_workflow(tmp_path / "workflow.json")),
            "comfyui_base_url": "http://127.0.0.1:8188",
            "final_storyboard": _final_storyboard(),
            "manual_grid_image_path": str(_write_grid(tmp_path / "grid.png")),
            "output_root": str(tmp_path / "out"),
            "dry_run": True,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "passed"
    assert body["ready"] is True
    assert body["prompt_id"] == ""


def test_smoke_cli_dry_run_exits_zero_and_writes_result(tmp_path):
    request_path = tmp_path / "smoke_request.json"
    request_path.write_text(
        json.dumps(
            {
                "workflow_path": str(_write_workflow(tmp_path / "workflow.json")),
                "comfyui_base_url": "http://127.0.0.1:8188",
                "final_storyboard": _final_storyboard(),
                "manual_grid_image_path": str(_write_grid(tmp_path / "grid.png")),
                "output_root": str(tmp_path / "out"),
                "dry_run": True,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "relief_story_agent.smoke_comfyui",
            "--request",
            str(request_path),
        ],
        cwd=str(Path(__file__).resolve().parents[2]),
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert completed.returncode == 0
    assert "status=passed" in completed.stdout
    assert "artifact_dir=" in completed.stdout
