from __future__ import annotations

import json
import subprocess
import sys
import tomllib
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_cli_help_lists_core_local_commands():
    completed = subprocess.run(
        [sys.executable, "-m", "relief_story_agent.cli", "--help"],
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert completed.returncode == 0
    assert "serve" in completed.stdout
    assert "smoke-comfyui" in completed.stdout
    assert "connect-comfyui" in completed.stdout
    assert "setup" in completed.stdout
    assert "acceptance" in completed.stdout
    assert "diagnose" in completed.stdout


def test_console_script_points_to_unified_cli():
    pyproject = tomllib.loads((PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8"))

    assert pyproject["project"]["scripts"]["relief-story-agent"] == "relief_story_agent.cli:main"


def test_cli_diagnose_run_reports_ready_configuration(tmp_path):
    request_path = tmp_path / "run_request.json"
    request_path.write_text(
        json.dumps(
            {
                "idea": "quiet local diagnosis",
                "output_root": str(tmp_path / "outputs"),
            }
        ),
        encoding="utf-8",
    )
    model_config_path = tmp_path / "models.json"
    model_config_path.write_text(json.dumps({"profiles": {}, "stages": {}}), encoding="utf-8")

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "relief_story_agent.cli",
            "diagnose",
            "--request",
            str(request_path),
            "--model-config",
            str(model_config_path),
            "--pretty",
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert completed.returncode == 0
    body = json.loads(completed.stdout)
    assert body["kind"] == "run"
    assert body["ready"] is True
    assert body["summary"]["failed"] == 0


def test_cli_diagnose_returns_nonzero_for_blocked_configuration(tmp_path):
    request_path = tmp_path / "run_request.json"
    request_path.write_text(json.dumps({"idea": "missing key"}), encoding="utf-8")
    model_config_path = tmp_path / "models.json"
    model_config_path.write_text(
        json.dumps(
            {
                "profiles": {
                    "writer": {
                        "api_key_env": "MISSING_DIAGNOSE_TEST_KEY",
                        "model": "writer-model",
                    }
                },
                "stages": {"chief_screenwriter": "writer"},
            }
        ),
        encoding="utf-8",
    )

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "relief_story_agent.cli",
            "diagnose",
            "--request",
            str(request_path),
            "--model-config",
            str(model_config_path),
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert completed.returncode == 1
    body = json.loads(completed.stdout)
    assert body["ready"] is False
    assert body["suggested_actions"][0]["code"] == "configure_model_environment"


def test_cli_diagnose_auto_detects_batch_request(tmp_path):
    request_path = tmp_path / "batch_request.json"
    request_path.write_text(
        json.dumps(
            {
                "items": [
                    {"idea": "first item"},
                    {"idea": "second item"},
                ]
            }
        ),
        encoding="utf-8",
    )

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "relief_story_agent.cli",
            "diagnose",
            "--request",
            str(request_path),
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert completed.returncode == 0
    body = json.loads(completed.stdout)
    assert body["kind"] == "batch"
    assert body["ready"] is True
    assert body["summary"]["total"] == 2
