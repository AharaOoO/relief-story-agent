from __future__ import annotations

import copy
import json

import httpx
import pytest

import relief_story_agent.comfyui as comfyui
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw

from relief_story_agent.api import create_app
from relief_story_agent.comfyui import (
    connect_comfyui,
    preview_storyboard_submission,
    submit_storyboard,
    upload_grid_image,
)
from relief_story_agent.grid_image import validate_grid_image
from relief_story_agent.ltx_workflow import (
    find_ltx_injection_points,
    find_ltx_widget_patch_points,
    litegraph_to_api_prompt,
    patch_ltx_litegraph_workflow,
    patch_ltx_widget_workflow,
)
from relief_story_agent.models import (
    ComfyUIConnectionRequest,
    ComfyUIRunConfig,
    GridImageAsset,
    GridImageConfig,
)
from relief_story_agent.orchestrator import InMemoryRunStore, StoryRunOrchestrator
from relief_story_agent.providers import FakeModelProvider
from relief_story_agent.smoke_comfyui import ComfyUISmokeRequest
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


def test_api_comfyui_connect_reaches_queue_and_analyzes_ltx_workflow(tmp_path, monkeypatch):
    workflow_path = _write_sanitized_workflow(tmp_path)
    requests: list[str] = []

    def handler(request: httpx.Request):
        requests.append(str(request.url))
        if request.url.path == "/queue":
            return httpx.Response(
                200,
                json={
                    "queue_running": [["running", "prompt-a"]],
                    "queue_pending": [["pending", "prompt-b"], ["pending", "prompt-c"]],
                },
            )
        if request.url.path == "/object_info":
            return httpx.Response(
                200,
                json={
                    "FixturePassthrough": {},
                    "JWString": {},
                    "LoadImage": {},
                    "ParseJsonNode": {},
                    "RandomNoise": {},
                    "TD_LTXVAddGuideFromGrid": {},
                    "VHS_VideoCombine": {},
                },
            )
        return httpx.Response(404)

    monkeypatch.setattr(
        "relief_story_agent.comfyui.httpx.Client",
        lambda *args, **kwargs: HTTPX_CLIENT(transport=httpx.MockTransport(handler)),
    )
    client = TestClient(
        create_app(
            StoryRunOrchestrator(
                provider=FakeModelProvider.minimal_success(),
                store=InMemoryRunStore(),
            )
        )
    )

    response = client.post(
        "/api/comfyui/connect",
        json={
            "endpoint": "http://comfy.local",
            "workflow_api_path": str(workflow_path),
        },
    )

    body = response.json()
    assert response.status_code == 200
    assert body["ready"] is True
    assert body["connected"] is True
    assert body["endpoint"] == "http://comfy.local"
    assert body["queue"] == {"running": 1, "pending": 2}
    assert body["workflow"]["adapter_mode"] == "litegraph_ltx_auto_injection"
    assert body["workflow"]["ltx_injection_points"]["grid_image_node_id"] == "196"
    assert body["workflow"]["grid_shape"] == {"columns": 2, "rows": 2}
    assert body["suggested_config"]["endpoint"] == "http://comfy.local"
    assert body["suggested_config"]["workflow_api_path"] == str(workflow_path)
    assert requests == ["http://comfy.local/queue", "http://comfy.local/object_info"]


def test_connect_comfyui_reports_missing_runtime_node_types(tmp_path):
    workflow_path = tmp_path / "missing_node_workflow.json"
    workflow_path.write_text(
        json.dumps(
            {
                "version": 0.4,
                "nodes": [
                    {
                        "id": 1,
                        "type": "CLIPTextEncode",
                        "title": "CLIP Text Encode (Positive Prompt)",
                        "widgets_values": ["prompt"],
                    },
                    {
                        "id": 2,
                        "type": "MissingSampler",
                        "widgets_values": [],
                    },
                ],
                "links": [],
            }
        ),
        encoding="utf-8",
    )

    def handler(request: httpx.Request):
        if request.url.path == "/queue":
            return httpx.Response(200, json={"queue_running": [], "queue_pending": []})
        if request.url.path == "/object_info":
            return httpx.Response(200, json={"CLIPTextEncode": {}})
        return httpx.Response(404)

    report = connect_comfyui(
        ComfyUIConnectionRequest(
            endpoint="http://comfy.local",
            workflow_api_path=str(workflow_path),
        ),
        client=HTTPX_CLIENT(transport=httpx.MockTransport(handler)),
    )

    node_check = next(check for check in report["checks"] if check["name"] == "comfyui_node_types")
    assert report["ready"] is False
    assert node_check["status"] == "failed"
    assert node_check["details"]["missing_node_types"] == ["MissingSampler"]
    assert report["suggested_actions"][0]["code"] == "install_or_enable_comfyui_nodes"


def test_connect_comfyui_uses_direct_http_client_by_default(monkeypatch):
    created_clients: list[dict] = []

    def handler(request: httpx.Request):
        assert request.url.path == "/queue"
        return httpx.Response(200, json={"queue_running": [], "queue_pending": []})

    def client_factory(*args, **kwargs):
        created_clients.append(kwargs)
        return HTTPX_CLIENT(transport=httpx.MockTransport(handler), trust_env=False)

    monkeypatch.setattr("relief_story_agent.comfyui.httpx.Client", client_factory)

    report = connect_comfyui(ComfyUIConnectionRequest(endpoint="127.0.0.1:8188/queue"))

    assert report["connected"] is True
    assert created_clients[0].get("trust_env") is False


def test_comfyui_endpoint_models_accept_common_address_box_inputs():
    connection = ComfyUIConnectionRequest(endpoint=" 127.0.0.1:8188/queue?view=1 ")
    run_config = ComfyUIRunConfig(endpoint="http://localhost:8188/")
    smoke_request = ComfyUISmokeRequest(
        workflow_path="D:/workflow.json",
        comfyui_base_url="localhost:8188/queue",
        final_storyboard=[{"shot_id": 1, "image_prompt": "frame"}],
        manual_grid_image_path="D:/grid.png",
    )

    assert connection.endpoint == "http://127.0.0.1:8188"
    assert run_config.endpoint == "http://localhost:8188"
    assert smoke_request.comfyui_base_url == "http://localhost:8188"


def test_api_comfyui_connect_reports_unreachable_endpoint(monkeypatch):
    def handler(request: httpx.Request):
        raise httpx.ConnectError("offline", request=request)

    monkeypatch.setattr(
        "relief_story_agent.comfyui.httpx.Client",
        lambda *args, **kwargs: HTTPX_CLIENT(transport=httpx.MockTransport(handler)),
    )
    client = TestClient(
        create_app(
            StoryRunOrchestrator(
                provider=FakeModelProvider.minimal_success(),
                store=InMemoryRunStore(),
            )
        )
    )

    response = client.post(
        "/api/comfyui/connect",
        json={"endpoint": "http://127.0.0.1:8188"},
    )

    body = response.json()
    assert response.status_code == 200
    assert body["ready"] is False
    assert body["connected"] is False
    assert body["checks"][0]["name"] == "comfyui_endpoint"
    assert body["checks"][0]["status"] == "failed"
    assert body["suggested_actions"][0]["code"] == "start_or_check_comfyui"
    assert "offline" in body["checks"][0]["message"]


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


def _ltx_widget_workflow_file(tmp_path):
    path = tmp_path / "ltx_widget_workflow.json"
    path.write_text(
        json.dumps(
            {
                "version": 0.4,
                "nodes": [
                    {
                        "id": 10,
                        "type": "LoadImage",
                        "inputs": [],
                        "outputs": [{"name": "IMAGE", "type": "IMAGE", "links": [100]}],
                        "widgets_values": ["example.png", "image"],
                    },
                    {
                        "id": 20,
                        "type": "CLIPTextEncode",
                        "title": "CLIP Text Encode (Negative Prompt)",
                        "inputs": [{"name": "clip", "type": "CLIP", "link": 101}],
                        "outputs": [{"name": "CONDITIONING", "type": "CONDITIONING", "links": [102]}],
                        "widgets_values": ["old negative"],
                    },
                    {
                        "id": 21,
                        "type": "CLIPTextEncode",
                        "title": "CLIP Text Encode (Positive Prompt)",
                        "inputs": [{"name": "clip", "type": "CLIP", "link": 103}],
                        "outputs": [{"name": "CONDITIONING", "type": "CONDITIONING", "links": [104]}],
                        "widgets_values": ["old positive"],
                    },
                    {
                        "id": 30,
                        "type": "RandomNoise",
                        "inputs": [],
                        "outputs": [{"name": "NOISE", "type": "NOISE", "links": [105]}],
                        "widgets_values": [42, "fixed"],
                    },
                    {
                        "id": 40,
                        "type": "SaveVideo",
                        "inputs": [{"name": "video", "type": "VIDEO", "link": 106}],
                        "outputs": [],
                        "widgets_values": ["old_prefix", "auto", "auto"],
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


def test_submit_storyboard_uses_direct_http_client_by_default(tmp_path, monkeypatch):
    config = ComfyUIRunConfig(
        enabled=True,
        endpoint="http://127.0.0.1:8188",
        workflow_api_path=str(_workflow_file(tmp_path)),
        placeholder_map={
            "positive": {
                "node": "1",
                "input": "text",
                "source": "comfyui_inputs.positive",
            }
        },
    )
    storyboard = [
        {
            "shot_id": 1,
            "image_prompt": "fallback prompt",
            "comfyui_inputs": {"positive": "compact LTX prompt"},
        }
    ]
    created_clients: list[dict] = []

    def handler(request: httpx.Request):
        assert request.url.path == "/prompt"
        payload = json.loads(request.content)
        return httpx.Response(200, json={"prompt_id": payload["prompt_id"]})

    def client_factory(*args, **kwargs):
        created_clients.append(kwargs)
        return HTTPX_CLIENT(transport=httpx.MockTransport(handler), trust_env=False)

    monkeypatch.setattr("relief_story_agent.comfyui.httpx.Client", client_factory)

    submissions = submit_storyboard(config, storyboard, "run_direct_local")

    assert submissions[0].status == "accepted"
    assert created_clients[0].get("trust_env") is False


def test_submit_storyboard_enriches_litegraph_workflow_with_runtime_object_info(tmp_path):
    workflow_path = tmp_path / "workflow.json"
    workflow_path.write_text(
        json.dumps(
            {
                "version": 0.4,
                "nodes": [
                    {
                        "id": 1,
                        "type": "LoadImage",
                        "inputs": [{"name": "image", "type": "IMAGE", "widget": {"name": "image"}}],
                        "widgets_values": ["old.png", "image"],
                    },
                    {
                        "id": 2,
                        "type": "CLIPTextEncode",
                        "title": "Positive Prompt",
                        "widgets_values": ["old prompt"],
                    },
                    {
                        "id": 3,
                        "type": "CheckpointLoaderSimple",
                        "widgets_values": ["ltx-2.3.safetensors"],
                    },
                    {
                        "id": 4,
                        "type": "EmptyLTXVLatentVideo",
                        "inputs": [
                            {"name": "width", "type": "INT", "widget": {"name": "width"}, "link": 41},
                            {"name": "height", "type": "INT", "widget": {"name": "height"}, "link": 42},
                            {"name": "length", "type": "INT", "widget": {"name": "length"}, "link": 43},
                        ],
                        "widgets_values": [960, 544, 121, 1],
                    },
                    {
                        "id": 5,
                        "type": "SaveVideo",
                        "widgets_values": ["old_prefix", "video/h264-mp4", "h264"],
                    },
                ],
                "links": [
                    [41, 11, 0, 4, 0, "INT"],
                    [42, 12, 0, 4, 1, "INT"],
                    [43, 13, 0, 4, 2, "INT"],
                ],
            }
        ),
        encoding="utf-8",
    )
    asset = GridImageAsset(
        source="manual",
        local_path=str(tmp_path / "grid.png"),
        sha256="c" * 64,
        mime_type="image/png",
        width=1024,
        height=1024,
        byte_size=100,
        comfyui_filename="uploaded_grid.png",
        upload_status="accepted",
    )
    submitted: list[dict] = []
    requests: list[str] = []

    def handler(request: httpx.Request):
        requests.append(request.url.path)
        if request.url.path == "/object_info":
            return httpx.Response(
                200,
                json={
                    "LoadImage": {"input": {"required": {"image": ["COMBO", {}]}}},
                    "CLIPTextEncode": {"input": {"required": {"text": ["STRING", {}]}}},
                    "CheckpointLoaderSimple": {
                        "input": {"required": {"ckpt_name": ["COMBO", {}]}},
                    },
                    "EmptyLTXVLatentVideo": {
                        "input": {
                            "required": {
                                "width": ["INT", {}],
                                "height": ["INT", {}],
                                "length": ["INT", {}],
                                "batch_size": ["INT", {}],
                            }
                        },
                    },
                    "SaveVideo": {"input": {"required": {"filename_prefix": ["STRING", {}]}}},
                },
            )
        if request.url.path == "/prompt":
            payload = json.loads(request.content)
            submitted.append(payload)
            return httpx.Response(200, json={"prompt_id": payload["prompt_id"]})
        return httpx.Response(404)

    submissions = submit_storyboard(
        ComfyUIRunConfig(enabled=True, endpoint="http://comfy.local", workflow_api_path=str(workflow_path)),
        [{"shot_id": 1, "image_prompt": "quiet scene"}],
        "runtime_run",
        duration_seconds=4,
        client=HTTPX_CLIENT(transport=httpx.MockTransport(handler)),
        grid_image_asset=asset,
    )

    prompt = submitted[0]["prompt"]
    assert requests == ["/object_info", "/prompt"]
    assert submissions[0].status == "accepted"
    assert prompt["3"]["inputs"]["ckpt_name"] == "ltx-2.3.safetensors"
    assert prompt["4"]["inputs"]["width"] == ["11", 0]
    assert prompt["4"]["inputs"]["height"] == ["12", 0]
    assert prompt["4"]["inputs"]["length"] == ["13", 0]
    assert prompt["4"]["inputs"]["batch_size"] == 1


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


def test_ltx_widget_patch_points_detect_common_integrated_workflow(tmp_path):
    workflow = json.loads(_ltx_widget_workflow_file(tmp_path).read_text(encoding="utf-8"))

    points = find_ltx_widget_patch_points(workflow)

    assert points.positive_prompt_node_ids == ("21",)
    assert points.negative_prompt_node_ids == ("20",)
    assert points.seed_node_ids == ("30",)
    assert points.filename_prefix_node_ids == ("40",)
    assert points.image_node_ids == ("10",)


def test_ltx_widget_patch_writes_gemma_prompt_without_overwriting_api_key():
    workflow = {
        "version": 0.4,
        "nodes": [
            {
                "id": 1,
                "type": "PrimitiveString",
                "outputs": [{"name": "STRING", "type": "STRING", "links": [11]}],
                "widgets_values": ["secret-key"],
            },
            {
                "id": 2,
                "type": "GemmaAPITextEncode",
                "title": "Gemma API Text Encode - POSITIVE",
                "inputs": [{"name": "api_key", "type": "STRING", "widget": {"name": "api_key"}, "link": 11}],
                "outputs": [{"name": "conditioning", "type": "CONDITIONING", "links": [12]}],
                "widgets_values": ["", "old prompt", "legacy-model-slot", "ltx-2.3.safetensors"],
            },
        ],
        "links": [[11, 1, 0, 2, 0, "STRING"]],
    }

    patched = patch_ltx_widget_workflow(
        workflow,
        ltx_payload={"prompt": "new prompt", "negative_prompt": "new negative"},
    )

    assert patched["2"]["inputs"]["api_key"] == ["1", 0]
    assert patched["2"]["inputs"]["prompt"] == "new prompt"
    assert "enhance_prompt" not in patched["2"]["inputs"]
    assert patched["2"]["inputs"]["ckpt_name"] == "ltx-2.3.safetensors"
    assert workflow["nodes"][1]["widgets_values"] == ["", "old prompt", "legacy-model-slot", "ltx-2.3.safetensors"]


def test_litegraph_to_api_prompt_uses_object_info_for_required_widgets():
    workflow = {
        "version": 0.4,
        "nodes": [
            {
                "id": 1,
                "type": "CheckpointLoaderSimple",
                "inputs": [],
                "widgets_values": ["ltx-2.3.safetensors"],
            },
            {
                "id": 2,
                "type": "EmptyLTXVLatentVideo",
                "inputs": [
                    {"name": "width", "type": "INT", "widget": {"name": "width"}, "link": 11},
                    {"name": "height", "type": "INT", "widget": {"name": "height"}, "link": 12},
                    {"name": "length", "type": "INT", "widget": {"name": "length"}, "link": 13},
                ],
                "widgets_values": [960, 544, 121, 1],
            },
        ],
        "links": [
            [11, 10, 0, 2, 0, "INT"],
            [12, 11, 0, 2, 1, "INT"],
            [13, 12, 0, 2, 2, "INT"],
        ],
    }
    object_info = {
        "CheckpointLoaderSimple": {
            "input": {"required": {"ckpt_name": ["COMBO", {}]}},
        },
        "EmptyLTXVLatentVideo": {
            "input": {
                "required": {
                    "width": ["INT", {}],
                    "height": ["INT", {}],
                    "length": ["INT", {}],
                    "batch_size": ["INT", {}],
                }
            },
        },
    }

    prompt = litegraph_to_api_prompt(workflow, object_info=object_info)

    assert prompt["1"]["inputs"]["ckpt_name"] == "ltx-2.3.safetensors"
    assert prompt["2"]["inputs"]["width"] == ["10", 0]
    assert prompt["2"]["inputs"]["height"] == ["11", 0]
    assert prompt["2"]["inputs"]["length"] == ["12", 0]
    assert prompt["2"]["inputs"]["batch_size"] == 1


def test_litegraph_to_api_prompt_expands_dynamic_combo_widgets_from_object_info():
    workflow = {
        "version": 0.4,
        "nodes": [
            {
                "id": 1,
                "type": "ResizeImageMaskNode",
                "inputs": [{"name": "input", "type": "IMAGE", "link": 21}],
                "widgets_values": ["scale longer dimension", 1536, "lanczos"],
            },
            {
                "id": 2,
                "type": "ResizeImageMaskNode",
                "inputs": [
                    {"name": "input", "type": "IMAGE", "link": 22},
                    {"name": "resize_type.multiple", "type": "INT", "widget": {"name": "resize_type.multiple"}, "link": 23},
                ],
                "widgets_values": ["scale to multiple", 64, "lanczos"],
            },
        ],
        "links": [
            [21, 10, 0, 1, 0, "IMAGE"],
            [22, 11, 0, 2, 0, "IMAGE"],
            [23, 12, 0, 2, 1, "INT"],
        ],
    }
    object_info = {
        "ResizeImageMaskNode": {
            "input": {
                "required": {
                    "input": ["IMAGE", {}],
                    "resize_type": [
                        "COMFY_DYNAMICCOMBO_V3",
                        {
                            "options": [
                                {
                                    "key": "scale longer dimension",
                                    "inputs": {"required": {"longer_size": ["INT", {}]}},
                                },
                                {
                                    "key": "scale to multiple",
                                    "inputs": {"required": {"multiple": ["INT", {}]}},
                                },
                            ]
                        },
                    ],
                    "scale_method": ["COMBO", {}],
                }
            }
        }
    }

    prompt = litegraph_to_api_prompt(workflow, object_info=object_info)

    assert prompt["1"]["inputs"]["resize_type"] == "scale longer dimension"
    assert prompt["1"]["inputs"]["resize_type.longer_size"] == 1536
    assert prompt["1"]["inputs"]["scale_method"] == "lanczos"
    assert prompt["2"]["inputs"]["resize_type"] == "scale to multiple"
    assert prompt["2"]["inputs"]["resize_type.multiple"] == ["12", 0]
    assert prompt["2"]["inputs"]["scale_method"] == "lanczos"


def test_litegraph_to_api_prompt_reconciles_runtime_combo_asset_names_from_object_info():
    workflow = {
        "version": 0.4,
        "nodes": [
            {
                "id": 1,
                "type": "CheckpointLoaderSimple",
                "widgets_values": ["ltx-2.3-22b-dev.safetensors"],
            },
            {
                "id": 2,
                "type": "LTXAVTextEncoderLoader",
                "widgets_values": [
                    "comfy_gemma_3_12B_it.safetensors",
                    "ltx-2.3-22b-dev.safetensors",
                    "default",
                ],
            },
            {
                "id": 3,
                "type": "LoraLoaderModelOnly",
                "widgets_values": [
                    "ltxv/ltx2/ltx-2.3-22b-distilled-lora-384.safetensors",
                    0.5,
                ],
            },
        ],
        "links": [],
    }
    object_info = {
        "CheckpointLoaderSimple": {
            "input": {
                "required": {
                    "ckpt_name": [
                        ["sdpose_wholebody_fp16.safetensors", "DasiwaLTX23Safetensors_solsticecoinV2.safetensors"],
                        {},
                    ],
                }
            },
        },
        "LTXAVTextEncoderLoader": {
            "input": {
                "required": {
                    "text_encoder": [
                        "COMBO",
                        {"options": ["clip_l.safetensors", "gemma_3_12B_it_fpmixed.safetensors"]},
                    ],
                    "ckpt_name": [
                        "COMBO",
                        {"options": ["sdpose_wholebody_fp16.safetensors", "DasiwaLTX23Safetensors_solsticecoinV2.safetensors"]},
                    ],
                    "device": ["COMBO", {"options": ["default", "cpu"]}],
                }
            },
        },
        "LoraLoaderModelOnly": {
            "input": {
                "required": {
                    "lora_name": [
                        "COMBO",
                        {
                            "options": [
                                "WAN2.2/FastWan_T2V_14B_480p_lora_rank_128_bf16.safetensors",
                                "LTX2.3/ltx-2.3-22b-distilled-1.1_lora-dynamic_fro09_avg_rank_111_bf16.safetensors",
                            ]
                        },
                    ],
                    "strength_model": ["FLOAT", {}],
                }
            },
        },
    }

    prompt = litegraph_to_api_prompt(workflow, object_info=object_info)

    assert prompt["1"]["inputs"]["ckpt_name"] == "DasiwaLTX23Safetensors_solsticecoinV2.safetensors"
    assert prompt["2"]["inputs"]["text_encoder"] == "gemma_3_12B_it_fpmixed.safetensors"
    assert prompt["2"]["inputs"]["ckpt_name"] == "DasiwaLTX23Safetensors_solsticecoinV2.safetensors"
    assert (
        prompt["3"]["inputs"]["lora_name"]
        == "LTX2.3/ltx-2.3-22b-distilled-1.1_lora-dynamic_fro09_avg_rank_111_bf16.safetensors"
    )


def test_analyze_workflow_detects_ltx_widget_patch_mode(tmp_path):
    workflow_path = _ltx_widget_workflow_file(tmp_path)
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
    assert body["adapter_mode"] == "litegraph_ltx_widget_patch"
    assert body["placeholder_map_required"] is False
    assert body["grid_asset_required"] is True
    assert body["ltx_widget_patch_points"] == {
        "positive_prompt_node_ids": ["21"],
        "negative_prompt_node_ids": ["20"],
        "seed_node_ids": ["30"],
        "filename_prefix_node_ids": ["40"],
        "image_node_ids": ["10"],
    }


def test_preview_widget_ltx_workflow_patches_existing_widgets(tmp_path):
    workflow_path = _ltx_widget_workflow_file(tmp_path)
    asset = GridImageAsset(
        source="manual",
        local_path=str(tmp_path / "grid.png"),
        sha256="b" * 64,
        mime_type="image/png",
        width=1024,
        height=1024,
        byte_size=100,
        comfyui_filename="uploaded_grid.png",
        upload_status="accepted",
    )

    preview = preview_storyboard_submission(
        ComfyUIRunConfig(enabled=True, workflow_api_path=str(workflow_path)),
        [
            {
                "shot_id": 1,
                "time_range": "0-4s",
                "image_prompt": "quiet convenience store window",
                "negative_prompt": "shouting, violence",
                "comfyui_inputs": {"seed": 777},
            }
        ],
        "widget_run",
        duration_seconds=4,
        include_workflow=True,
        grid_image_asset=asset,
    )

    item = preview["items"][0]
    workflow = item["workflow"]
    assert item["submission_key"] == "ltx_widget"
    assert [replacement["key"] for replacement in item["replacements"]] == [
        "image",
        "positive_prompt",
        "negative_prompt",
        "seed",
        "filename_prefix",
    ]
    assert workflow["10"]["inputs"]["image"] == "uploaded_grid.png"
    assert workflow["21"]["inputs"]["text"] == "quiet convenience store window"
    assert workflow["20"]["inputs"]["text"] == "shouting, violence"
    assert workflow["30"]["inputs"]["noise_seed"] == 777
    assert workflow["40"]["inputs"]["filename_prefix"] == "widget_run"


def test_preview_storyboard_submission_can_include_runtime_object_info_enriched_workflow(tmp_path):
    workflow_path = tmp_path / "widget_runtime_workflow.json"
    workflow_path.write_text(
        json.dumps(
            {
                "version": 0.4,
                "nodes": [
                    {
                        "id": 10,
                        "type": "LoadImage",
                        "widgets_values": ["example.png", "image"],
                    },
                    {
                        "id": 21,
                        "type": "CLIPTextEncode",
                        "title": "Positive Prompt",
                        "widgets_values": ["old prompt"],
                    },
                    {
                        "id": 30,
                        "type": "CheckpointLoaderSimple",
                        "widgets_values": ["ltx-2.3-22b-dev.safetensors"],
                    },
                ],
                "links": [],
            }
        ),
        encoding="utf-8",
    )
    asset = GridImageAsset(
        source="manual",
        local_path=str(tmp_path / "grid.png"),
        sha256="d" * 64,
        mime_type="image/png",
        width=1024,
        height=1024,
        byte_size=100,
        comfyui_filename="uploaded_grid.png",
        upload_status="accepted",
    )

    preview = preview_storyboard_submission(
        ComfyUIRunConfig(enabled=True, workflow_api_path=str(workflow_path)),
        [{"shot_id": 1, "image_prompt": "quiet scene"}],
        "runtime_preview",
        include_workflow=True,
        grid_image_asset=asset,
        object_info={
            "LoadImage": {"input": {"required": {"image": ["COMBO", {}]}}},
            "CLIPTextEncode": {"input": {"required": {"text": ["STRING", {}]}}},
            "CheckpointLoaderSimple": {
                "input": {
                    "required": {
                        "ckpt_name": [
                            ["sdpose_wholebody_fp16.safetensors", "DasiwaLTX23Safetensors_solsticecoinV2.safetensors"],
                            {},
                        ]
                    }
                }
            },
        },
    )

    workflow = preview["items"][0]["workflow"]
    assert workflow["30"]["inputs"]["ckpt_name"] == "DasiwaLTX23Safetensors_solsticecoinV2.safetensors"


def test_discover_workflows_recommends_ltx_widget_candidate(tmp_path):
    good = _ltx_widget_workflow_file(tmp_path)
    unsupported = tmp_path / "plain.json"
    unsupported.write_text(json.dumps({"hello": "world"}), encoding="utf-8")

    report = comfyui.discover_workflows([tmp_path], endpoint="127.0.0.1:8188/queue")

    assert report["recommended"]["path"] == str(good)
    assert report["items"][0]["adapter_mode"] == "litegraph_ltx_widget_patch"
    assert report["items"][0]["status"] == "recommended"
    assert report["items"][1]["status"] == "unsupported"


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


def test_discover_workflows_ranks_ltx_grid_candidate(tmp_path):
    good = _write_sanitized_workflow(tmp_path)
    unsupported = tmp_path / "plain.json"
    unsupported.write_text(json.dumps({"hello": "world"}), encoding="utf-8")

    report = comfyui.discover_workflows([tmp_path], endpoint="127.0.0.1:8188/queue")

    assert report["endpoint"] == "http://127.0.0.1:8188"
    assert report["total_candidates"] == 2
    assert report["recommended"]["path"] == str(good)
    assert report["recommended"]["status"] == "recommended"
    assert report["items"][0]["path"] == str(good)
    assert report["items"][0]["adapter_mode"] == "litegraph_ltx_auto_injection"
    assert report["items"][0]["grid_shape"] == {"columns": 2, "rows": 2}
    assert report["items"][1]["status"] == "unsupported"


def test_api_comfyui_discover_workflows_returns_candidates(tmp_path):
    good = _ltx_litegraph_workflow_file(tmp_path)
    client = TestClient(
        create_app(
            StoryRunOrchestrator(
                provider=FakeModelProvider.minimal_success(),
                store=InMemoryRunStore(),
            )
        )
    )

    response = client.post(
        "/api/comfyui/discover-workflows",
        json={
            "endpoint": "127.0.0.1:8188/queue",
            "search_roots": [str(tmp_path)],
            "max_results": 5,
        },
    )

    body = response.json()
    assert response.status_code == 200
    assert body["recommended"]["path"] == str(good)
    assert body["items"][0]["status"] == "recommended"
