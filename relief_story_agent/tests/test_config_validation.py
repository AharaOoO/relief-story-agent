import json

import httpx
from fastapi.testclient import TestClient

from relief_story_agent.api import create_app
from relief_story_agent.config_validation import validate_run_configuration
from relief_story_agent.model_config import ModelConfigRegistry
from relief_story_agent.models import ComfyUIRunConfig, GridImageConfig, RunRequest, StageModelConfig
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


def test_preflight_rejects_missing_manual_grid_image(tmp_path):
    request = RunRequest(
        idea="manual missing",
        comfyui=ComfyUIRunConfig(
            enabled=True,
            workflow_api_path=str(_write_sanitized_workflow(tmp_path)),
            grid_image=GridImageConfig(
                mode="manual_override",
                manual_image_path=str(tmp_path / "missing.png"),
            ),
        ),
    )

    result = validate_run_configuration(request, ModelConfigRegistry())
    check = next(item for item in result["checks"] if item["name"] == "grid_image")

    assert check["status"] == "failed"
    assert "not found" in check["message"]


def test_config_validation_reports_template_workflow_and_secret_errors(tmp_path):
    bad_writer = tmp_path / "bad_writer.md"
    bad_writer.write_text("missing script placeholder", encoding="utf-8")
    registry = ModelConfigRegistry(
        profiles={
            "gpt": StageModelConfig(
                api_key_env="MISSING_TEST_KEY",
                model="test-model",
            )
        },
        stages={"gpt_prompt_writer": "gpt"},
        environ={},
    )
    app = create_app(
        StoryRunOrchestrator(
            provider=FakeModelProvider.minimal_success(),
            store=InMemoryRunStore(),
            model_registry=registry,
        )
    )
    client = TestClient(app)

    response = client.post(
        "/api/config/validate",
        json={
            "idea": "validate",
            "template_paths": {
                "prompt_writer_template_path": str(bad_writer),
                "prompt_audit_template_path": str(tmp_path / "missing_audit.md"),
            },
            "comfyui": {
                "enabled": True,
                "workflow_api_path": str(tmp_path / "missing_workflow.json"),
            },
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["passed"] is False
    failed = {check["name"]: check for check in body["checks"] if check["status"] == "failed"}
    assert "model_environment" in failed
    assert "prompt_writer_template" in failed
    assert "prompt_audit_template" in failed
    assert "comfyui_workflow" in failed


def test_config_validation_accepts_valid_templates_and_workflow(tmp_path):
    writer = tmp_path / "writer.md"
    writer.write_text("writer {{script_json}} {{duration_seconds}}", encoding="utf-8")
    audit = tmp_path / "audit.md"
    audit.write_text("audit {{script_json}} {{storyboard_json}}", encoding="utf-8")
    workflow = tmp_path / "workflow_api.json"
    workflow.write_text(
        json.dumps(
            {
                "1": {
                    "class_type": "PromptNode",
                    "inputs": {"text": "old"},
                }
            }
        ),
        encoding="utf-8",
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
        "/api/config/validate",
        json={
            "idea": "validate",
            "template_paths": {
                "prompt_writer_template_path": str(writer),
                "prompt_audit_template_path": str(audit),
            },
            "comfyui": {
                "enabled": True,
                "workflow_api_path": str(workflow),
                "placeholder_map": {
                    "positive": {
                        "node": "1",
                        "input": "text",
                        "source": "image_prompt",
                    }
                },
            },
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["passed"] is True
    assert all(check["status"] != "failed" for check in body["checks"])


def test_config_validation_accepts_litegraph_ltx_workflow(tmp_path):
    workflow = tmp_path / "ltx_litegraph.json"
    workflow.write_text(
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
    client = TestClient(
        create_app(
            StoryRunOrchestrator(
                provider=FakeModelProvider.minimal_success(),
                store=InMemoryRunStore(),
            )
        )
    )

    response = client.post(
        "/api/config/validate",
        json={
            "idea": "litegraph ltx",
            "comfyui": {
                "enabled": True,
                "workflow_api_path": str(workflow),
            },
        },
    )

    body = response.json()
    workflow_check = next(check for check in body["checks"] if check["name"] == "comfyui_workflow")
    assert body["passed"] is True
    assert workflow_check["status"] == "passed"
    assert workflow_check["details"]["format"] == "litegraph"
    assert workflow_check["details"]["ltx_mode"] == "litegraph_ltx_auto_injection"
    assert workflow_check["details"]["node_count"] == 3
    assert workflow_check["details"]["link_count"] == 0
    assert workflow_check["details"]["api_node_count"] == 3
    assert workflow_check["details"]["ltx_injection_points"] == {
        "json_node_id": "202",
        "seed_node_id": "37",
        "filename_prefix_node_id": "79",
    }


def test_config_diagnose_reports_output_root_and_suggested_actions(tmp_path):
    output_root = tmp_path / "diagnose_outputs"
    workflow = tmp_path / "workflow_api.json"
    workflow.write_text(
        json.dumps({"1": {"class_type": "PromptNode", "inputs": {"text": "old"}}}),
        encoding="utf-8",
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
        "/api/config/diagnose",
        json={
            "idea": "diagnose",
            "output_root": str(output_root),
            "comfyui": {
                "enabled": True,
                "workflow_api_path": str(workflow),
                "placeholder_map": {
                    "positive": {"node": "1", "input": "text", "source": "image_prompt"}
                },
            },
        },
    )

    body = response.json()
    assert response.status_code == 200
    assert body["ready"] is True
    assert body["summary"]["failed"] == 0
    assert body["summary"]["passed"] >= 1
    checks = {check["name"]: check for check in body["checks"]}
    assert checks["output_root"]["status"] == "passed"
    assert checks["output_root"]["details"]["path"] == str(output_root)
    assert body["suggested_actions"] == []


def test_config_diagnose_includes_file_provenance(tmp_path):
    writer = tmp_path / "writer.md"
    writer.write_text("writer {{script_json}}", encoding="utf-8")
    audit = tmp_path / "audit.md"
    audit.write_text("audit {{script_json}} {{storyboard_json}}", encoding="utf-8")
    workflow = tmp_path / "workflow_api.json"
    workflow.write_text(
        json.dumps(
            {
                "1": {"class_type": "PromptNode", "inputs": {"text": "old"}},
                "2": {"class_type": "SeedNode", "inputs": {"seed": 0}},
            }
        ),
        encoding="utf-8",
    )
    placeholder_map = tmp_path / "placeholder_map.json"
    placeholder_map.write_text(
        json.dumps(
            {
                "positive": {"node": "1", "input": "text", "source": "image_prompt"},
                "seed": {"node": "2", "input": "seed", "source": "comfyui_inputs.seed"},
            }
        ),
        encoding="utf-8",
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
        "/api/config/diagnose",
        json={
            "idea": "diagnose provenance",
            "template_paths": {
                "prompt_writer_template_path": str(writer),
                "prompt_audit_template_path": str(audit),
            },
            "comfyui": {
                "enabled": True,
                "workflow_api_path": str(workflow),
                "placeholder_map_path": str(placeholder_map),
            },
        },
    )

    body = response.json()
    assert response.status_code == 200
    files = body["provenance"]["files"]
    assert set(files) == {
        "prompt_writer_template",
        "prompt_audit_template",
        "comfyui_workflow",
        "placeholder_map",
    }
    assert files["prompt_writer_template"]["path"] == str(writer)
    assert files["prompt_writer_template"]["exists"] is True
    assert files["prompt_writer_template"]["size_bytes"] > 0
    assert len(files["prompt_writer_template"]["sha256"]) == 64
    assert files["placeholder_map"]["path"] == str(placeholder_map)
    assert files["placeholder_map"]["exists"] is True
    assert len(files["placeholder_map"]["sha256"]) == 64
    assert len(body["provenance"]["fingerprint"]) == 64


def test_config_diagnose_flags_unwritable_output_root(tmp_path):
    output_file = tmp_path / "not_a_directory.txt"
    output_file.write_text("occupied", encoding="utf-8")
    client = TestClient(
        create_app(
            StoryRunOrchestrator(
                provider=FakeModelProvider.minimal_success(),
                store=InMemoryRunStore(),
            )
        )
    )

    response = client.post(
        "/api/config/diagnose",
        json={
            "idea": "bad output",
            "output_root": str(output_file),
        },
    )

    body = response.json()
    assert body["ready"] is False
    checks = {check["name"]: check for check in body["checks"]}
    assert checks["output_root"]["status"] == "failed"
    assert body["suggested_actions"][0]["code"] == "fix_output_root"


def test_batch_config_validation_reports_each_item(tmp_path):
    workflow = tmp_path / "workflow_api.json"
    workflow.write_text(
        json.dumps({"1": {"class_type": "PromptNode", "inputs": {"text": "old"}}}),
        encoding="utf-8",
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
        "/api/config/validate-batch",
        json={
            "items": [
                {
                    "idea": "valid",
                    "comfyui": {
                        "enabled": True,
                        "workflow_api_path": str(workflow),
                        "placeholder_map": {
                            "positive": {
                                "node": "1",
                                "input": "text",
                                "source": "image_prompt",
                            }
                        },
                    },
                },
                {
                    "idea": "invalid",
                    "comfyui": {
                        "enabled": True,
                        "workflow_api_path": str(tmp_path / "missing.json"),
                    },
                },
            ]
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["passed"] is False
    assert body["summary"] == {"total": 2, "passed": 1, "failed": 1}
    assert body["items"][0]["passed"] is True
    assert body["items"][1]["passed"] is False
    assert body["items"][1]["idea"] == "invalid"


def test_batch_config_diagnose_reports_item_summaries_and_actions(tmp_path):
    output_file = tmp_path / "not_a_directory.txt"
    output_file.write_text("occupied", encoding="utf-8")
    client = TestClient(
        create_app(
            StoryRunOrchestrator(
                provider=FakeModelProvider.minimal_success(),
                store=InMemoryRunStore(),
            )
        )
    )

    response = client.post(
        "/api/config/diagnose-batch",
        json={
            "defaults": {"output_root": str(tmp_path / "ok_outputs")},
            "items": [
                {"idea": "valid"},
                {"idea": "bad output", "output_root": str(output_file)},
            ],
        },
    )

    body = response.json()
    assert response.status_code == 200
    assert body["ready"] is False
    assert body["summary"]["total"] == 2
    assert body["summary"]["ready"] == 1
    assert body["summary"]["blocked"] == 1
    assert body["items"][0]["ready"] is True
    assert body["items"][1]["ready"] is False
    assert body["items"][1]["suggested_actions"][0]["code"] == "fix_output_root"


def test_batch_config_validation_applies_shared_defaults(tmp_path):
    workflow = tmp_path / "workflow_api.json"
    workflow.write_text(
        json.dumps({"1": {"class_type": "PromptNode", "inputs": {"text": "old"}}}),
        encoding="utf-8",
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
        "/api/config/validate-batch",
        json={
            "defaults": {
                "comfyui": {
                    "enabled": True,
                    "workflow_api_path": str(workflow),
                    "placeholder_map": {
                        "positive": {
                            "node": "1",
                            "input": "text",
                            "source": "image_prompt",
                        }
                    },
                }
            },
            "items": [
                {"idea": "inherits valid workflow"},
                {"idea": "also inherits valid workflow"},
            ],
        },
    )

    body = response.json()
    assert body["passed"] is True
    assert body["summary"] == {"total": 2, "passed": 2, "failed": 0}


def test_config_validation_reports_missing_placeholder_map_file(tmp_path):
    workflow = tmp_path / "workflow_api.json"
    workflow.write_text(
        json.dumps({"1": {"class_type": "PromptNode", "inputs": {"text": "old"}}}),
        encoding="utf-8",
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
        "/api/config/validate",
        json={
            "idea": "missing map",
            "comfyui": {
                "enabled": True,
                "workflow_api_path": str(workflow),
                "placeholder_map_path": str(tmp_path / "missing_map.json"),
            },
        },
    )

    body = response.json()
    assert body["passed"] is False
    workflow_check = next(check for check in body["checks"] if check["name"] == "comfyui_workflow")
    assert workflow_check["status"] == "failed"
    assert "Placeholder map file not found" in workflow_check["message"]


def test_config_validation_can_check_comfyui_connection(tmp_path, monkeypatch):
    workflow = tmp_path / "workflow_api.json"
    workflow.write_text(
        json.dumps({"1": {"class_type": "PromptNode", "inputs": {"text": "old"}}}),
        encoding="utf-8",
    )

    def handler(request: httpx.Request):
        assert request.url.path == "/queue"
        return httpx.Response(200, json={"queue_running": [], "queue_pending": []})

    monkeypatch.setattr(
        "relief_story_agent.config_validation.httpx.Client",
        lambda **kwargs: HTTPX_CLIENT(transport=httpx.MockTransport(handler)),
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
        "/api/config/validate?check_comfyui_connection=true",
        json={
            "idea": "valid",
            "comfyui": {
                "enabled": True,
                "endpoint": "http://comfy.local",
                "workflow_api_path": str(workflow),
                "placeholder_map": {
                    "positive": {
                        "node": "1",
                        "input": "text",
                        "source": "image_prompt",
                    }
                },
            },
        },
    )

    body = response.json()
    assert body["passed"] is True
    checks = {check["name"]: check for check in body["checks"]}
    assert checks["comfyui_endpoint"]["status"] == "passed"
    assert checks["comfyui_endpoint"]["details"]["queue_pending"] == 0


def test_config_validation_reports_comfyui_connection_failure(tmp_path, monkeypatch):
    workflow = tmp_path / "workflow_api.json"
    workflow.write_text(
        json.dumps({"1": {"class_type": "PromptNode", "inputs": {"text": "old"}}}),
        encoding="utf-8",
    )

    def handler(request: httpx.Request):
        raise httpx.ConnectError("connection refused", request=request)

    monkeypatch.setattr(
        "relief_story_agent.config_validation.httpx.Client",
        lambda **kwargs: HTTPX_CLIENT(transport=httpx.MockTransport(handler)),
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
        "/api/config/validate?check_comfyui_connection=true",
        json={
            "idea": "invalid",
            "comfyui": {
                "enabled": True,
                "endpoint": "http://comfy.local",
                "workflow_api_path": str(workflow),
                "placeholder_map": {
                    "positive": {
                        "node": "1",
                        "input": "text",
                        "source": "image_prompt",
                    }
                },
            },
        },
    )

    body = response.json()
    assert body["passed"] is False
    failed = {check["name"]: check for check in body["checks"] if check["status"] == "failed"}
    assert "comfyui_endpoint" in failed


def test_batch_config_validation_can_check_comfyui_connection(tmp_path, monkeypatch):
    workflow = tmp_path / "workflow_api.json"
    workflow.write_text(
        json.dumps({"1": {"class_type": "PromptNode", "inputs": {"text": "old"}}}),
        encoding="utf-8",
    )
    calls = 0

    def handler(request: httpx.Request):
        nonlocal calls
        calls += 1
        return httpx.Response(200, json={"queue_running": [], "queue_pending": []})

    monkeypatch.setattr(
        "relief_story_agent.config_validation.httpx.Client",
        lambda **kwargs: HTTPX_CLIENT(transport=httpx.MockTransport(handler)),
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
        "/api/config/validate-batch?check_comfyui_connection=true",
        json={
            "items": [
                {
                    "idea": "valid",
                    "comfyui": {
                        "enabled": True,
                        "endpoint": "http://comfy.local",
                        "workflow_api_path": str(workflow),
                        "placeholder_map": {
                            "positive": {
                                "node": "1",
                                "input": "text",
                                "source": "image_prompt",
                            }
                        },
                    },
                }
            ]
        },
    )

    body = response.json()
    assert body["passed"] is True
    assert calls == 1
    assert any(
        check["name"] == "comfyui_endpoint"
        for check in body["items"][0]["checks"]
    )


def test_create_run_with_preflight_rejects_invalid_configuration_without_state(tmp_path):
    store = InMemoryRunStore()
    client = TestClient(
        create_app(
            StoryRunOrchestrator(
                provider=FakeModelProvider.minimal_success(),
                store=store,
            )
        )
    )

    response = client.post(
        "/api/runs",
        params={"preflight": "true"},
        json={
            "idea": "invalid run",
            "template_paths": {
                "prompt_writer_template_path": str(tmp_path / "missing_writer.md"),
            },
        },
    )

    assert response.status_code == 400
    body = response.json()
    assert body["detail"]["message"] == "preflight validation failed"
    assert body["detail"]["validation"]["passed"] is False
    assert store.list_runs() == []


def test_create_batch_with_preflight_rejects_invalid_configuration_without_state(tmp_path):
    store = InMemoryRunStore()
    client = TestClient(
        create_app(
            StoryRunOrchestrator(
                provider=FakeModelProvider.minimal_success(),
                store=store,
            )
        )
    )

    response = client.post(
        "/api/batches",
        params={"preflight": "true"},
        json={
            "items": [
                {
                    "idea": "invalid batch item",
                    "comfyui": {
                        "enabled": True,
                        "workflow_api_path": str(tmp_path / "missing_workflow.json"),
                    },
                }
            ],
        },
    )

    assert response.status_code == 400
    body = response.json()
    assert body["detail"]["message"] == "preflight validation failed"
    assert body["detail"]["validation"]["passed"] is False
    assert store.list_batches() == []
    assert store.list_runs() == []


def test_create_run_with_passing_preflight_still_creates_state():
    store = InMemoryRunStore()
    client = TestClient(
        create_app(
            StoryRunOrchestrator(
                provider=FakeModelProvider.minimal_success(),
                store=store,
            )
        )
    )

    response = client.post(
        "/api/runs",
        params={"preflight": "true"},
        json={"idea": "valid run", "approval_mode": "manual"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "awaiting_approval"
    assert len(store.list_runs()) == 1
