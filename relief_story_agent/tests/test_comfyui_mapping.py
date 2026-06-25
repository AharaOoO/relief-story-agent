from __future__ import annotations

import copy
import json

import httpx
import pytest

from fastapi.testclient import TestClient
from PIL import Image, ImageDraw

from relief_story_agent.api import create_app
from relief_story_agent.comfyui import preview_storyboard_submission, submit_storyboard, upload_grid_image
from relief_story_agent.grid_image import validate_grid_image
from relief_story_agent.ltx_workflow import find_ltx_injection_points, patch_ltx_litegraph_workflow
from relief_story_agent.models import ComfyUIRunConfig, GridImageAsset, GridImageConfig
from relief_story_agent.orchestrator import InMemoryRunStore, StoryRunOrchestrator
from relief_story_agent.providers import FakeModelProvider
from relief_story_agent.tests.fixtures.ltx23_workflow_factory import build_sanitized_ltx23_workflow


HTTPX_CLIENT = httpx.Client


def _write_sanitized_workflow(tmp_path):
    path = tmp_path / "ltx23_fixture.json"
    path.write_text(
        json.dumps(build_sanitized_ltx23_workflow(), ensure_ascii=False),
        encoding="utf-8",
    )
    return path


def test_real_shape_fixture_detects_all_four_injection_points():
    workflow = build_sanitized_ltx23_workflow()

    points = find_ltx_injection_points(workflow)

    assert len(workflow["nodes"]) == 60
    assert points.json_node_id == "202"
    assert points.seed_node_id == "37"
    assert points.filename_prefix_node_id == "79"
    assert points.grid_image_node_id == "196"
    assert points.grid_image_input == "image"
    assert points.grid_columns == 2
    assert points.grid_rows == 2


def test_patch_changes_only_declared_four_inputs():
    workflow = build_sanitized_ltx23_workflow()
    original = copy.deepcopy(workflow)

    patched = patch_ltx_litegraph_workflow(
        workflow,
        ltx_payload={
            "prompt": "new",
            "frame_indices": "0,24,48,72",
            "strengths": "0.7,0.7,0.7,0.7",
            "duration_seconds": 4,
        },
        seed=99,
        filename_prefix="run_demo",
        grid_image_filename="run_demo_hash.png",
    )

    assert workflow == original
    assert patched["196"]["inputs"]["image"] == "run_demo_hash.png"
    assert patched["37"]["inputs"]["noise_seed"] == 99
    assert patched["79"]["inputs"]["filename_prefix"] == "run_demo"
    assert '"prompt": "new"' in patched["202"]["inputs"]["text"]


def test_grid_topology_rejects_ambiguous_upstream_load_images():
    workflow = build_sanitized_ltx23_workflow()
    workflow["nodes"].append(
        {
            "id": 197,
            "type": "LoadImage",
            "inputs": [{"name": "image", "widget": {"name": "image"}}],
            "outputs": [{"name": "IMAGE"}],
            "widgets_values": ["other.png"],
        }
    )
    workflow["links"].append([452, 197, 0, 221, 0, "IMAGE"])

    with pytest.raises(ValueError, match="exactly one"):
        find_ltx_injection_points(workflow)


def test_upload_grid_image_posts_multipart_and_normalizes_filename(tmp_path):
    image_path = tmp_path / "grid.png"
    image_path.write_bytes(b"image-bytes")
    requests = []

    def handler(request: httpx.Request):
        requests.append(request)
        assert request.url.path == "/upload/image"
        assert "multipart/form-data" in request.headers["content-type"]
        return httpx.Response(
            200,
            json={"name": "run_demo_hash.png", "subfolder": "", "type": "input"},
        )

    result = upload_grid_image(
        "http://comfy.local",
        image_path,
        destination_name="run_demo_hash.png",
        client=HTTPX_CLIENT(transport=httpx.MockTransport(handler)),
    )

    assert result == "run_demo_hash.png"
    assert len(requests) == 1


def test_preview_reports_four_replacements_without_side_effects(tmp_path):
    workflow_path = tmp_path / "workflow.json"
    workflow_path.write_text(
        json.dumps(build_sanitized_ltx23_workflow(), ensure_ascii=False),
        encoding="utf-8",
    )
    asset = GridImageAsset(
        source="manual",
        local_path=str(tmp_path / "grid.png"),
        sha256="a" * 64,
        mime_type="image/png",
        width=1024,
        height=1024,
        byte_size=100,
        comfyui_filename="run_demo_aaaaaaaaaaaa.png",
        upload_status="accepted",
    )

    preview = preview_storyboard_submission(
        ComfyUIRunConfig(enabled=True, workflow_api_path=str(workflow_path)),
        [
            {
                "shot_id": 1,
                "time_range": "0-4s",
                "image_prompt": "frame",
                "comfyui_inputs": {"seed": 7},
            }
        ],
        "run_demo",
        duration_seconds=4,
        grid_image_asset=asset,
    )

    replacements = preview["items"][0]["replacements"]
    assert [item["key"] for item in replacements] == [
        "grid_image",
        "ltx_payload",
        "seed",
        "filename_prefix",
    ]
    assert preview["will_enqueue"] is False


def test_analyze_workflow_reports_grid_requirements(tmp_path):
    workflow_path = _write_sanitized_workflow(tmp_path)
    app = create_app(StoryRunOrchestrator(provider=FakeModelProvider.minimal_success()))

    with TestClient(app) as client:
        response = client.post(
            "/api/comfyui/analyze-workflow",
            json={
                "comfyui": {
                    "enabled": True,
                    "workflow_api_path": str(workflow_path),
                }
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["grid_asset_required"] is True
    assert body["ltx_injection_points"]["grid_image_node_id"] == "196"
    assert body["grid_shape"] == {"columns": 2, "rows": 2}


def test_preview_manual_path_validates_without_upload_or_generation(tmp_path, monkeypatch):
    image_path = tmp_path / "manual.png"
    image = Image.new("RGB", (1024, 1024), "white")
    draw = ImageDraw.Draw(image)
    for index, color in enumerate(["red", "green", "blue", "yellow"]):
        left = (index % 2) * 512
        top = (index // 2) * 512
        image.paste(color, (left, top, left + 512, top + 512))
        draw.line((left + 20, top + 20, left + 492, top + 492), fill="black", width=8)
    image.save(image_path)
    workflow_path = _write_sanitized_workflow(tmp_path)
    monkeypatch.setattr(
        "relief_story_agent.comfyui.upload_grid_image",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("preview must not upload")
        ),
    )

    preview = preview_storyboard_submission(
        ComfyUIRunConfig(
            enabled=True,
            workflow_api_path=str(workflow_path),
            grid_image=GridImageConfig(
                mode="manual_override",
                manual_image_path=str(image_path),
            ),
        ),
        [{"shot_id": 1, "time_range": "0-4s", "image_prompt": "frame"}],
        "preview_manual",
        duration_seconds=4,
    )

    image_replacement = preview["items"][0]["replacements"][0]
    assert image_replacement["key"] == "grid_image"
    assert image_replacement["resolution"] == "exact_manual_asset"
    assert preview["will_enqueue"] is False


def test_preview_and_submission_do_not_mutate_60_node_fixture(tmp_path, monkeypatch):
    workflow = build_sanitized_ltx23_workflow()
    original = copy.deepcopy(workflow)
    workflow_path = tmp_path / "immutable_workflow.json"
    workflow_path.write_text(json.dumps(workflow), encoding="utf-8")
    image_path = tmp_path / "manual.png"
    image = Image.new("RGB", (1024, 1024), "white")
    draw = ImageDraw.Draw(image)
    for index, color in enumerate(["red", "green", "blue", "yellow"]):
        left = (index % 2) * 512
        top = (index // 2) * 512
        image.paste(color, (left, top, left + 512, top + 512))
        draw.line((left + 20, top + 20, left + 492, top + 492), fill="black", width=8)
    image.save(image_path)
    validated = validate_grid_image(
        image_path,
        min_dimension=512,
        max_bytes=10_000_000,
    )
    asset = GridImageAsset(
        source="manual",
        local_path=str(image_path),
        sha256=validated.sha256,
        mime_type=validated.mime_type,
        width=validated.width,
        height=validated.height,
        byte_size=validated.byte_size,
        comfyui_filename="immutable.png",
        upload_status="accepted",
    )
    config = ComfyUIRunConfig(enabled=True, workflow_api_path=str(workflow_path))
    storyboard = [{"shot_id": 1, "time_range": "0-4s", "image_prompt": "frame"}]
    preview_storyboard_submission(
        config,
        storyboard,
        "immutable",
        duration_seconds=4,
        grid_image_asset=asset,
    )
    monkeypatch.setattr(
        "relief_story_agent.comfyui.enqueue_workflow",
        lambda *args, **kwargs: kwargs["prompt_id"],
    )
    submit_storyboard(
        config,
        storyboard,
        "immutable",
        duration_seconds=4,
        grid_image_asset=asset,
    )

    persisted = json.loads(workflow_path.read_text(encoding="utf-8"))
    assert persisted == original
    assert len(persisted["nodes"]) == 60


def _workflow_file(tmp_path):
    path = tmp_path / "workflow_api.json"
    path.write_text(
        json.dumps(
            {
                "1": {"class_type": "PromptNode", "inputs": {"text": "old"}},
                "2": {"class_type": "SeedNode", "inputs": {"seed": 0}},
            }
        ),
        encoding="utf-8",
    )
    return path


def _ltx_litegraph_workflow_file(tmp_path):
    path = tmp_path / "ltx_litegraph.json"
    path.write_text(
        json.dumps(
            {
                "version": 0.4,
                "nodes": [
                    {
                        "id": 202,
                        "type": "JWString",
                        "inputs": [{"name": "text", "type": "STRING", "widget": {"name": "text"}}],
                        "outputs": [{"name": "STRING", "type": "STRING", "links": [1]}],
                        "widgets_values": [
                            json.dumps(
                                {
                                    "prompt": "old prompt",
                                    "negative_prompt": "old negative",
                                    "frame_indices": "0,24,48,72",
                                    "strengths": "0.7,0.7,0.8,0.8",
                                    "duration_seconds": 4,
                                    "fps": 24,
                                    "shots": [],
                                },
                                ensure_ascii=False,
                            )
                        ],
                    },
                    {
                        "id": 37,
                        "type": "RandomNoise",
                        "inputs": [{"name": "noise_seed", "type": "INT", "widget": {"name": "noise_seed"}}],
                        "widgets_values": [123],
                    },
                    {
                        "id": 79,
                        "type": "VHS_VideoCombine",
                        "inputs": [
                            {"name": "filename_prefix", "type": "STRING", "widget": {"name": "filename_prefix"}}
                        ],
                        "widgets_values": {"filename_prefix": "old_prefix"},
                    },
                ],
                "links": [],
            }
        ),
        encoding="utf-8",
    )
    return path


def test_submit_storyboard_loads_placeholder_map_file_and_inline_overrides(tmp_path):
    map_path = tmp_path / "placeholder_map.json"
    map_path.write_text(
        json.dumps(
            {
                "placeholder_map": {
                    "positive": {
                        "node": "1",
                        "input": "text",
                        "source": "comfyui_inputs.positive",
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    config = ComfyUIRunConfig(
        enabled=True,
        endpoint="http://comfy.local",
        workflow_api_path=str(_workflow_file(tmp_path)),
        placeholder_map_path=str(map_path),
        placeholder_map={
            "seed": {"node": "2", "input": "seed", "source": "comfyui_inputs.seed"}
        },
    )
    storyboard = [
        {
            "shot_id": 1,
            "image_prompt": "fallback prompt",
            "comfyui_inputs": {"positive": "compact LTX keyframe prompt", "seed": 777},
        }
    ]
    posted_payloads: list[dict] = []

    def handler(request: httpx.Request):
        assert request.url.path == "/prompt"
        payload = json.loads(request.content)
        posted_payloads.append(payload)
        return httpx.Response(200, json={"prompt_id": payload["prompt_id"]})

    submit_storyboard(
        config,
        storyboard,
        "run_mapping_file",
        client=HTTPX_CLIENT(transport=httpx.MockTransport(handler)),
    )

    prompt = posted_payloads[0]["prompt"]
    assert prompt["1"]["inputs"]["text"] == "compact LTX keyframe prompt"
    assert prompt["2"]["inputs"]["seed"] == 777


def test_submit_storyboard_reports_missing_placeholder_source(tmp_path):
    config = ComfyUIRunConfig(
        enabled=True,
        endpoint="http://comfy.local",
        workflow_api_path=str(_workflow_file(tmp_path)),
        placeholder_map={
            "positive": {
                "node": "1",
                "input": "text",
                "source": "comfyui_inputs.positive",
            }
        },
    )
    storyboard = [{"shot_id": 1, "image_prompt": "fallback prompt", "comfyui_inputs": {}}]

    with pytest.raises(
        ValueError,
        match="placeholder_map 'positive' source 'comfyui_inputs.positive' was not found",
    ):
        submit_storyboard(config, storyboard, "run_missing_source")


def test_preview_storyboard_submission_reports_patched_workflow_without_enqueueing(tmp_path):
    config = ComfyUIRunConfig(
        enabled=True,
        endpoint="http://comfy.local",
        workflow_api_path=str(_workflow_file(tmp_path)),
        placeholder_map={
            "positive": {"node": "1", "input": "text", "source": "comfyui_inputs.positive"},
            "seed": {"node": "2", "input": "seed", "source": "comfyui_inputs.seed"},
        },
    )
    storyboard = [
        {
            "shot_id": 1,
            "image_prompt": "fallback prompt",
            "comfyui_inputs": {"positive": "quiet four-grid keyframe", "seed": 1234},
        }
    ]

    preview = preview_storyboard_submission(
        config,
        storyboard,
        "run_preview",
        duration_seconds=90,
    )
    submitted: list[dict] = []

    def handler(request: httpx.Request):
        payload = json.loads(request.content)
        submitted.append(payload)
        return httpx.Response(200, json={"prompt_id": payload["prompt_id"]})

    submissions = submit_storyboard(
        config,
        storyboard,
        "run_preview",
        duration_seconds=90,
        client=HTTPX_CLIENT(transport=httpx.MockTransport(handler)),
    )

    assert preview["will_enqueue"] is False
    assert preview["planned_count"] == 1
    assert preview["items"][0]["submission_key"] == "shot:1"
    assert preview["items"][0]["prompt_id"] == submissions[0].prompt_id
    assert preview["items"][0]["content_fingerprint"] == submissions[0].content_fingerprint
    assert preview["items"][0]["replacements"] == [
        {
            "key": "positive",
            "node": "1",
            "input": "text",
            "source": "comfyui_inputs.positive",
            "value_preview": "quiet four-grid keyframe",
        },
        {
            "key": "seed",
            "node": "2",
            "input": "seed",
            "source": "comfyui_inputs.seed",
            "value_preview": "1234",
        },
    ]
    assert submitted[0]["prompt_id"] == preview["items"][0]["prompt_id"]


def test_api_comfyui_preview_returns_plan_without_creating_run(tmp_path):
    workflow_path = _workflow_file(tmp_path)
    client = TestClient(
        create_app(
            StoryRunOrchestrator(
                provider=FakeModelProvider.minimal_success(),
                store=InMemoryRunStore(),
            )
        )
    )

    response = client.post(
        "/api/comfyui/preview",
        json={
            "run_id": "run_api_preview",
            "duration_seconds": 90,
            "comfyui": {
                "enabled": True,
                "endpoint": "http://comfy.local",
                "workflow_api_path": str(workflow_path),
                "placeholder_map": {
                    "positive": {
                        "node": "1",
                        "input": "text",
                        "source": "image_prompt",
                    }
                },
            },
            "storyboard": [
                {
                    "shot_id": 1,
                    "image_prompt": "preview prompt",
                    "comfyui_inputs": {"seed": 42},
                }
            ],
        },
    )

    body = response.json()
    assert response.status_code == 200
    assert body["will_enqueue"] is False
    assert body["workflow_format"] == "api"
    assert body["items"][0]["submission_key"] == "shot:1"
    assert body["items"][0]["replacements"][0]["value_preview"] == "preview prompt"


def test_api_comfyui_analyze_workflow_detects_litegraph_ltx_auto_injection(tmp_path):
    workflow_path = _ltx_litegraph_workflow_file(tmp_path)
    client = TestClient(
        create_app(
            StoryRunOrchestrator(
                provider=FakeModelProvider.minimal_success(),
                store=InMemoryRunStore(),
            )
        )
    )

    response = client.post(
        "/api/comfyui/analyze-workflow",
        json={
            "comfyui": {
                "enabled": True,
                "workflow_api_path": str(workflow_path),
            }
        },
    )

    body = response.json()
    assert response.status_code == 200
    assert body["workflow_format"] == "litegraph"
    assert body["adapter_mode"] == "litegraph_ltx_auto_injection"
    assert body["placeholder_map_required"] is False
    assert body["node_count"] == 3
    assert body["api_node_count"] == 3
    assert body["ltx_injection_points"] == {
        "json_node_id": "202",
        "seed_node_id": "37",
        "filename_prefix_node_id": "79",
    }
    assert body["suggested_config"]["workflow_api_path"] == str(workflow_path)
    assert body["suggested_config"]["placeholder_map"] == {}
    assert body["warnings"] == []


def test_api_comfyui_analyze_workflow_reports_api_placeholder_map_mode(tmp_path):
    workflow_path = _workflow_file(tmp_path)
    client = TestClient(
        create_app(
            StoryRunOrchestrator(
                provider=FakeModelProvider.minimal_success(),
                store=InMemoryRunStore(),
            )
        )
    )

    response = client.post(
        "/api/comfyui/analyze-workflow",
        json={
            "comfyui": {
                "enabled": True,
                "workflow_api_path": str(workflow_path),
                "placeholder_map": {
                    "positive": {"node": "1", "input": "text", "source": "image_prompt"}
                },
            }
        },
    )

    body = response.json()
    assert response.status_code == 200
    assert body["workflow_format"] == "api"
    assert body["adapter_mode"] == "api_placeholder_map"
    assert body["placeholder_map_required"] is True
    assert body["placeholder_map_keys"] == ["positive"]
    assert body["node_count"] == 2
    assert body["suggested_config"]["placeholder_map"]["positive"]["source"] == "image_prompt"
