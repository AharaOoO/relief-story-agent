from __future__ import annotations

import io
import json

from PIL import Image, ImageDraw

from relief_story_agent.grid_image import GeneratedImage
from relief_story_agent.models import ComfyUIRunConfig, RunRequest
from relief_story_agent.orchestrator import InMemoryRunStore, StoryRunOrchestrator
from relief_story_agent.providers import FakeModelProvider
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
