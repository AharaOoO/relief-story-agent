from __future__ import annotations

import io
import json

import httpx
from PIL import Image, ImageDraw

from relief_story_agent.grid_image import GeneratedImage
from relief_story_agent.models import ComfyUIRunConfig, GridImageAsset, RunRequest
from relief_story_agent.orchestrator import InMemoryRunStore, StoryRunOrchestrator
from relief_story_agent.providers import FakeModelProvider
from relief_story_agent.segment_render import build_segment_render_plan
from relief_story_agent.tests.fixtures.ltx23_workflow_factory import (
    build_sanitized_ltx23_workflow,
)


SIX_SHOTS = [
    {
        "shot_id": index,
        "time_range": time_range,
        "description": f"shot {index}",
        "image_prompt": f"image prompt {index}",
        "negative_prompt": "text, watermark",
        "comfyui_inputs": {"seed": 1000 + index, "strength": 0.7},
    }
    for index, time_range in enumerate(
        ["0-10s", "10-25s", "25-45s", "45-60s", "60-75s", "75-90s"],
        start=1,
    )
]
HTTPX_CLIENT = httpx.Client


class RecordingGridProvider:
    def __init__(self):
        self.prompts: list[str] = []

    def generate(self, *, prompt, config):
        self.prompts.append(prompt)
        call_number = len(self.prompts)
        image = Image.new("RGB", (1600, 900), "white")
        draw = ImageDraw.Draw(image)
        colors = ["red", "green", "blue", "yellow"]
        for index, color in enumerate(colors):
            left = (index % 2) * 800
            top = (index // 2) * 450
            image.paste(color, (left, top, left + 800, top + 450))
            draw.line(
                (left + 20, top + 20 + call_number, left + 780, top + 430),
                fill="black",
                width=8,
            )
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        return GeneratedImage(
            content=buffer.getvalue(),
            mime_type="image/png",
            provider="fake",
            model=config.model,
            task_id=f"g2-{call_number}",
        )


def _workflow_path(tmp_path):
    path = tmp_path / "ltx_workflow.json"
    path.write_text(
        json.dumps(build_sanitized_ltx23_workflow(), ensure_ascii=False),
        encoding="utf-8",
    )
    return path


def test_stage_eight_generates_and_uploads_one_grid_per_segment(tmp_path, monkeypatch):
    provider = RecordingGridProvider()
    uploaded: list[str] = []

    def fake_upload(endpoint, local_path, *, destination_name, client=None):
        uploaded.append(destination_name)
        return destination_name

    monkeypatch.setattr(
        "relief_story_agent.orchestrator.upload_grid_image",
        fake_upload,
    )
    orchestrator = StoryRunOrchestrator(
        provider=FakeModelProvider.minimal_success(),
        store=InMemoryRunStore(),
        grid_image_provider=provider,
    )
    run = orchestrator.prepare_run(
        RunRequest(
            idea="six segments",
            approval_mode="auto",
            output_root=str(tmp_path / "runs"),
            creation_spec={"duration_seconds": 0},
            comfyui=ComfyUIRunConfig(
                enabled=True,
                workflow_api_path=str(_workflow_path(tmp_path)),
            ),
        )
    )
    run.final_storyboard = SIX_SHOTS
    orchestrator.store.save(run)

    orchestrator._run_four_grid_asset(run)

    assert len(provider.prompts) == 6
    assert len(run.segment_renders) == 6
    assert len(uploaded) == 6
    assert all(segment.grid_image_asset for segment in run.segment_renders)
    assert all(segment.grid_image_asset.upload_status == "accepted" for segment in run.segment_renders)
    assert [segment.status for segment in run.segment_renders] == ["image_ready"] * 6
    assert len({segment.grid_image_asset.local_path for segment in run.segment_renders}) == 6
    assert "image prompt 2" not in provider.prompts[0]
    assert "image prompt 1" not in provider.prompts[1]


def test_stage_eight_resume_reuses_completed_segment_images(tmp_path, monkeypatch):
    provider = RecordingGridProvider()
    monkeypatch.setattr(
        "relief_story_agent.orchestrator.upload_grid_image",
        lambda endpoint, local_path, *, destination_name, client=None: destination_name,
    )
    orchestrator = StoryRunOrchestrator(
        provider=FakeModelProvider.minimal_success(),
        store=InMemoryRunStore(),
        grid_image_provider=provider,
    )
    run = orchestrator.prepare_run(
        RunRequest(
            idea="resume segments",
            approval_mode="auto",
            output_root=str(tmp_path / "runs"),
            creation_spec={"duration_seconds": 0},
            comfyui=ComfyUIRunConfig(
                enabled=True,
                workflow_api_path=str(_workflow_path(tmp_path)),
            ),
        )
    )
    run.final_storyboard = SIX_SHOTS[:2]

    orchestrator._run_four_grid_asset(run)
    first_paths = [segment.grid_image_asset.local_path for segment in run.segment_renders]
    orchestrator._run_four_grid_asset(run)

    assert len(provider.prompts) == 2
    assert [segment.grid_image_asset.local_path for segment in run.segment_renders] == first_paths


def _segment_video_run(tmp_path, *, timeout_seconds=1.0):
    orchestrator = StoryRunOrchestrator(
        provider=FakeModelProvider.minimal_success(),
        store=InMemoryRunStore(),
    )
    run = orchestrator.prepare_run(
        RunRequest(
            idea="sequential video",
            approval_mode="auto",
            output_root=str(tmp_path / "runs"),
            creation_spec={"duration_seconds": 0},
            comfyui=ComfyUIRunConfig(
                enabled=True,
                endpoint="http://comfy.local",
                workflow_api_path=str(_workflow_path(tmp_path)),
                wait_for_completion=True,
                download_outputs=False,
                output_timeout_seconds=timeout_seconds,
                output_poll_interval_seconds=0,
            ),
        )
    )
    run.final_storyboard = SIX_SHOTS[:2]
    run.segment_renders = build_segment_render_plan(
        run.final_storyboard,
        target_duration_seconds=0,
    )
    for segment in run.segment_renders:
        segment.grid_image_asset = GridImageAsset(
            source="generated",
            local_path=str(tmp_path / f"{segment.segment_id}.png"),
            sha256=str(segment.order) * 64,
            mime_type="image/png",
            width=2048,
            height=1152,
            byte_size=100,
            comfyui_filename=f"{segment.segment_id}.png",
            upload_status="accepted",
        )
        segment.grid_image_checkpoint = "workflow_patched"
        segment.status = "image_ready"
    orchestrator.store.save(run)
    return orchestrator, run


def test_comfyui_segments_submit_strictly_after_previous_output(tmp_path, monkeypatch):
    orchestrator, run = _segment_video_run(tmp_path)
    sequence: list[tuple[str, str]] = []
    prompt_segments: dict[str, str] = {}

    def handler(request: httpx.Request):
        if request.url.path.startswith("/object_info/"):
            node_type = request.url.path.rsplit("/", 1)[-1]
            return httpx.Response(200, json={node_type: {}})
        if request.url.path == "/prompt":
            payload = json.loads(request.content)
            prompt_id = payload["prompt_id"]
            segment_id = payload["extra_data"]["relief_story_agent"]["segment_id"]
            prompt_segments[prompt_id] = segment_id
            sequence.append(("prompt", segment_id))
            return httpx.Response(200, json={"prompt_id": prompt_id})
        if request.url.path.startswith("/history/"):
            prompt_id = request.url.path.rsplit("/", 1)[-1]
            segment_id = prompt_segments[prompt_id]
            sequence.append(("history", segment_id))
            return httpx.Response(
                200,
                json={
                    prompt_id: {
                        "outputs": {
                            "79": {
                                "videos": [
                                    {
                                        "filename": f"{segment_id}.mp4",
                                        "subfolder": "",
                                        "type": "output",
                                    }
                                ]
                            }
                        }
                    }
                },
            )
        raise AssertionError(f"unexpected request: {request.url}")

    monkeypatch.setattr(
        "relief_story_agent.orchestrator.httpx.Client",
        lambda **kwargs: HTTPX_CLIENT(transport=httpx.MockTransport(handler)),
    )

    orchestrator._run_comfyui(run)

    first, second = [segment.segment_id for segment in run.segment_renders]
    assert sequence == [
        ("prompt", first),
        ("history", first),
        ("prompt", second),
        ("history", second),
    ]
    assert [segment.status for segment in run.segment_renders] == [
        "completed",
        "completed",
    ]


def test_active_segment_timeout_extends_monitoring_without_failing_run(
    tmp_path,
    monkeypatch,
):
    orchestrator, run = _segment_video_run(tmp_path, timeout_seconds=0)
    prompt_id = ""

    def handler(request: httpx.Request):
        nonlocal prompt_id
        if request.url.path.startswith("/object_info/"):
            node_type = request.url.path.rsplit("/", 1)[-1]
            return httpx.Response(200, json={node_type: {}})
        if request.url.path == "/prompt":
            payload = json.loads(request.content)
            prompt_id = payload["prompt_id"]
            return httpx.Response(200, json={"prompt_id": prompt_id})
        if request.url.path == f"/history/{prompt_id}":
            return httpx.Response(200, json={})
        if request.url.path == "/queue":
            return httpx.Response(
                200,
                json={"queue_running": [[0, prompt_id, {}, {}]], "queue_pending": []},
            )
        raise AssertionError(f"unexpected request: {request.url}")

    monkeypatch.setattr(
        "relief_story_agent.orchestrator.httpx.Client",
        lambda **kwargs: HTTPX_CLIENT(transport=httpx.MockTransport(handler)),
    )

    orchestrator._execute(run, start_stage="comfyui")

    assert run.status == "running"
    assert run.current_stage == "comfyui"
    assert run.segment_renders[0].status == "running"
    assert run.segment_renders[1].status == "image_ready"
    assert len(run.comfyui_prompt_ids) == 1
    assert any(
        event.event_type == "segment_monitoring_extended" for event in run.events
    )
