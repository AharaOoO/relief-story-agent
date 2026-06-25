from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from fastapi.testclient import TestClient

from relief_story_agent.api import create_app
from relief_story_agent.model_config import ModelConfigRegistry
from relief_story_agent.models import BatchRunRequest, ComfyUIConnectionRequest, RunRequest
from relief_story_agent.orchestrator import StoryRunOrchestrator
from relief_story_agent.providers import FakeModelProvider
from relief_story_agent.setup_wizard import write_local_config_bundle


def test_write_local_config_bundle_creates_deployable_files(tmp_path):
    result = write_local_config_bundle(
        tmp_path,
        workflow_path="C:/ComfyUI/workflows/ltx23_four_grid.json",
        comfyui_endpoint="http://127.0.0.1:8188",
        output_root="D:/relief_story_runs",
    )

    expected_keys = {
        "model_config",
        "run_request",
        "batch_request",
        "comfyui_connect",
        "prompt_writer_template",
        "prompt_audit_template",
    }
    assert expected_keys.issubset(result)
    for path in result.values():
        if not isinstance(path, str):
            continue
        assert Path(path).exists()
    assert result["files"]["model_config"]["exists"] is True
    assert result["files"]["model_config"]["path"] == result["model_config"]
    assert result["checks"]["workflow_path"]["status"] == "warn"
    assert result["checks"]["workflow_path"]["path"] == "C:/ComfyUI/workflows/ltx23_four_grid.json"
    assert result["checks"]["comfyui_endpoint"]["normalized"] == "http://127.0.0.1:8188"
    assert "relief-story-agent local-doctor" in result["next_commands"]["doctor"]
    assert result["next_endpoints"]["local_doctor"] == "/api/local/doctor"

    ModelConfigRegistry.from_file(result["model_config"], environ={})
    run_payload = json.loads(Path(result["run_request"]).read_text(encoding="utf-8"))
    batch_payload = json.loads(Path(result["batch_request"]).read_text(encoding="utf-8"))
    connect_payload = json.loads(Path(result["comfyui_connect"]).read_text(encoding="utf-8"))
    writer = Path(result["prompt_writer_template"]).read_text(encoding="utf-8")
    audit = Path(result["prompt_audit_template"]).read_text(encoding="utf-8")

    RunRequest.model_validate(run_payload)
    BatchRunRequest.model_validate(batch_payload)
    ComfyUIConnectionRequest.model_validate(connect_payload)
    assert run_payload["comfyui"]["endpoint"] == "http://127.0.0.1:8188"
    assert run_payload["comfyui"]["workflow_api_path"] == "C:/ComfyUI/workflows/ltx23_four_grid.json"
    assert run_payload["output_root"] == "D:/relief_story_runs"
    assert run_payload["execution_policy"]["max_total_stage_executions"] >= 10
    assert run_payload["execution_policy"]["max_stage_executions"]["gpt_prompt_audit"] == 2
    assert batch_payload["defaults"]["comfyui"]["endpoint"] == "http://127.0.0.1:8188"
    assert batch_payload["defaults"]["execution_policy"]["max_total_stage_executions"] >= 10
    assert connect_payload["workflow_api_path"] == "C:/ComfyUI/workflows/ltx23_four_grid.json"
    assert "{{script_json}}" in writer
    assert "{{duration_seconds}}" in writer
    assert "{{preferred_style}}" in writer
    assert "{{script_json}}" in audit
    assert "{{storyboard_json}}" in audit


def test_cli_setup_writes_local_config_bundle(tmp_path):
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "relief_story_agent.cli",
            "setup",
            "--output-dir",
            str(tmp_path),
            "--workflow-path",
            "C:/ComfyUI/workflows/ltx23_four_grid.json",
            "--comfyui-endpoint",
            "http://127.0.0.1:8188",
            "--output-root",
            "D:/relief_story_runs",
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert completed.returncode == 0
    assert "model_config.local.json" in completed.stdout
    assert (tmp_path / "run_request.full-ltx.json").exists()
    assert (tmp_path / "templates" / "prompt_writer.default.md").exists()


def test_setup_wizard_normalizes_comfyui_endpoint_for_generated_files(tmp_path):
    result = write_local_config_bundle(
        tmp_path,
        workflow_path="C:/ComfyUI/workflows/ltx23_four_grid.json",
        comfyui_endpoint="127.0.0.1:8188/queue",
        output_root="D:/relief_story_runs",
    )

    run_payload = json.loads(Path(result["run_request"]).read_text(encoding="utf-8"))
    batch_payload = json.loads(Path(result["batch_request"]).read_text(encoding="utf-8"))
    connect_payload = json.loads(Path(result["comfyui_connect"]).read_text(encoding="utf-8"))

    assert run_payload["comfyui"]["endpoint"] == "http://127.0.0.1:8188"
    assert batch_payload["defaults"]["comfyui"]["endpoint"] == "http://127.0.0.1:8188"
    assert connect_payload["endpoint"] == "http://127.0.0.1:8188"


def test_setup_wizard_next_commands_use_the_normalized_comfyui_endpoint(tmp_path):
    result = write_local_config_bundle(
        tmp_path,
        workflow_path="C:/ComfyUI/workflows/ltx23_four_grid.json",
        comfyui_endpoint="192.168.31.8:8189/queue",
        output_root="D:/relief_story_runs",
    )

    assert result["checks"]["comfyui_endpoint"]["normalized"] == "http://192.168.31.8:8189"
    assert '--comfyui-endpoint "http://192.168.31.8:8189"' in result["next_commands"]["doctor"]


def test_api_local_setup_bundle_writes_config_files_for_ui(tmp_path):
    app = create_app(StoryRunOrchestrator(provider=FakeModelProvider.minimal_success()))
    client = TestClient(app)
    output_dir = tmp_path / "relief_story_config"

    response = client.post(
        "/api/local/setup-bundle",
        json={
            "output_dir": str(output_dir),
            "workflow_path": "C:/ComfyUI/workflows/ltx23_four_grid.json",
            "comfyui_endpoint": "127.0.0.1:8188/queue",
            "output_root": "D:/relief_story_runs",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert Path(body["model_config"]).exists()
    assert Path(body["run_request"]).exists()
    assert Path(body["batch_request"]).exists()
    assert Path(body["comfyui_connect"]).exists()
    assert body["files"]["run_request"]["exists"] is True
    assert body["checks"]["comfyui_endpoint"]["normalized"] == "http://127.0.0.1:8188"
    assert body["next_endpoints"]["create_batch"] == "/api/batches"
    run_payload = json.loads(Path(body["run_request"]).read_text(encoding="utf-8"))
    connect_payload = json.loads(Path(body["comfyui_connect"]).read_text(encoding="utf-8"))
    assert run_payload["comfyui"]["endpoint"] == "http://127.0.0.1:8188"
    assert run_payload["comfyui"]["workflow_api_path"] == "C:/ComfyUI/workflows/ltx23_four_grid.json"
    assert connect_payload["endpoint"] == "http://127.0.0.1:8188"
