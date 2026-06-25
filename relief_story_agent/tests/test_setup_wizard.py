from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from relief_story_agent.model_config import ModelConfigRegistry
from relief_story_agent.models import BatchRunRequest, ComfyUIConnectionRequest, RunRequest
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
        assert Path(path).exists()

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
