from __future__ import annotations

import json
import subprocess
import sys
import tomllib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from urllib.parse import parse_qs, urlparse


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
    assert "discover-comfyui-workflows" in completed.stdout
    assert "setup" in completed.stdout
    assert "acceptance" in completed.stdout
    assert "acceptance-status" in completed.stdout
    assert "diagnose" in completed.stdout
    assert "pipeline-schema" in completed.stdout
    assert "local-bootstrap" in completed.stdout
    assert "local-doctor" in completed.stdout
    assert "local-readiness" in completed.stdout
    assert "local-demo" in completed.stdout
    assert "comfyui-outputs" in completed.stdout
    assert "run" in completed.stdout
    assert "batch-plan" in completed.stdout
    assert "batch" in completed.stdout
    assert "export-batch" in completed.stdout
    assert "recovery-plan" in completed.stdout
    assert "recover-batch" in completed.stdout
    assert "run-status" in completed.stdout
    assert "runs" in completed.stdout
    assert "batch-status" in completed.stdout
    assert "batches" in completed.stdout
    assert "scheduler" in completed.stdout
    assert "run-events" in completed.stdout
    assert "run-artifacts" in completed.stdout
    assert "run-timeline" in completed.stdout
    assert "run-audit" in completed.stdout
    assert "batch-artifacts" in completed.stdout
    assert "batch-timeline" in completed.stdout
    assert "batch-health" in completed.stdout
    assert "validate-export" in completed.stdout
    assert "validate-export-zip" in completed.stdout


def test_console_script_points_to_unified_cli():
    pyproject = tomllib.loads((PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8"))

    assert pyproject["project"]["scripts"]["relief-story-agent"] == "relief_story_agent.cli:main"


def test_cli_rejects_unknown_arguments_for_local_subcommands(tmp_path):
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "relief_story_agent.cli",
            "acceptance",
            "--output-dir",
            str(tmp_path),
            "--unknown-evidence-flag",
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert completed.returncode != 0
    assert "unrecognized arguments: --unknown-evidence-flag" in completed.stderr


def test_cli_discover_comfyui_workflows_scans_local_directory(tmp_path):
    workflow_path = tmp_path / "ltx_litegraph.json"
    workflow_path.write_text(
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
                        "widgets_values": ["old_prefix"],
                    },
                ],
                "links": [[1, 202, 0, 999, 0, "STRING"]],
            }
        ),
        encoding="utf-8",
    )

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "relief_story_agent.cli",
            "discover-comfyui-workflows",
            "--search-root",
            str(tmp_path),
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )

    body = json.loads(completed.stdout)
    assert completed.returncode == 0
    assert body["recommended"]["path"] == str(workflow_path)
    assert body["items"][0]["status"] == "recommended"


def test_cli_discover_comfyui_workflows_returns_zero_when_no_recommendation(tmp_path):
    unsupported = tmp_path / "plain.json"
    unsupported.write_text('{"hello": "world"}', encoding="utf-8")

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "relief_story_agent.cli",
            "discover-comfyui-workflows",
            "--search-root",
            str(tmp_path),
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )

    body = json.loads(completed.stdout)
    assert completed.returncode == 0
    assert body["recommended"] == {}
    assert body["items"][0]["status"] == "unsupported"


def test_cli_discover_comfyui_workflows_reports_invalid_schema_without_traceback(tmp_path):
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "relief_story_agent.cli",
            "discover-comfyui-workflows",
            "--search-root",
            str(tmp_path),
            "--max-results",
            "0",
            "--pretty",
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert completed.returncode == 1
    assert "Traceback" not in completed.stderr
    body = json.loads(completed.stdout)
    assert body["status"] == "invalid_request"
    assert body["path"] == "discover-comfyui-workflows"
    assert "Invalid request" in body["error"]


def test_cli_comfyui_outputs_queries_and_downloads_prompt_outputs(tmp_path):
    with _ComfyUIHistoryServer(video_bytes=b"cli-video") as server:
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "relief_story_agent.cli",
                "comfyui-outputs",
                "--endpoint",
                server.url,
                "--prompt-id",
                "prompt_cli",
                "--artifact-dir",
                str(tmp_path),
                "--download",
                "--pretty",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )

    assert completed.returncode == 0
    body = json.loads(completed.stdout)
    assert body["ready"] is True
    assert body["actual_outputs"][0]["filename"] == "cli.mp4"
    assert Path(body["actual_outputs"][0]["local_path"]).read_bytes() == b"cli-video"
    assert [request["path"] for request in server.requests] == [
        "/history/prompt_cli",
        "/view",
    ]


def test_cli_comfyui_outputs_reports_invalid_request_schema_with_path(tmp_path):
    request_path = tmp_path / "outputs_request.json"
    request_path.write_text(json.dumps({"prompt_ids": []}), encoding="utf-8")

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "relief_story_agent.cli",
            "comfyui-outputs",
            "--request",
            str(request_path),
            "--pretty",
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert completed.returncode == 1
    assert "Traceback" not in completed.stderr
    body = json.loads(completed.stdout)
    assert body["status"] == "invalid_request"
    assert body["path"] == str(request_path)
    assert "Invalid request" in body["error"]


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


def test_cli_diagnose_reports_invalid_request_schema_without_traceback(tmp_path):
    request_path = tmp_path / "batch_request.json"
    request_path.write_text(json.dumps({"items": []}), encoding="utf-8")

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "relief_story_agent.cli",
            "diagnose",
            "--request",
            str(request_path),
            "--pretty",
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert completed.returncode == 1
    assert "Traceback" not in completed.stderr
    body = json.loads(completed.stdout)
    assert body["status"] == "invalid_request"
    assert body["path"] == str(request_path)
    assert "Invalid request" in body["error"]


def test_cli_model_check_reports_invalid_run_request_schema_without_traceback(tmp_path):
    request_path = tmp_path / "run_request.json"
    request_path.write_text(
        json.dumps({"output_root": str(tmp_path / "outputs")}),
        encoding="utf-8",
    )
    model_config_path = tmp_path / "models.json"
    model_config_path.write_text(json.dumps({"profiles": {}, "stages": {}}), encoding="utf-8")

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "relief_story_agent.cli",
            "model-check",
            "--model-config",
            str(model_config_path),
            "--run-request",
            str(request_path),
            "--pretty",
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert completed.returncode == 1
    assert "Traceback" not in completed.stderr
    body = json.loads(completed.stdout)
    assert body["status"] == "invalid_request"
    assert body["path"] == str(request_path)
    assert "Invalid request" in body["error"]


def test_cli_run_posts_request_to_api(tmp_path):
    request_path = tmp_path / "run.json"
    request_path.write_text(json.dumps({"idea": "cli run"}), encoding="utf-8")
    server = _CliApiServer({"run_id": "run_cli", "status": "queued"})

    with server:
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "relief_story_agent.cli",
                "run",
                "--server",
                server.url,
                "--request",
                str(request_path),
                "--preflight",
                "--check-comfyui-connection",
                "--pretty",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )

    assert completed.returncode == 0
    assert json.loads(completed.stdout)["run_id"] == "run_cli"
    recorded = server.requests[0]
    assert recorded["path"] == "/api/runs"
    assert recorded["query"] == {
        "preflight": ["true"],
        "check_comfyui_connection": ["true"],
    }
    assert recorded["json"] == {"idea": "cli run"}


def test_cli_post_command_reports_api_connection_error_without_traceback(tmp_path):
    request_path = tmp_path / "run.json"
    request_path.write_text(json.dumps({"idea": "api missing"}), encoding="utf-8")

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "relief_story_agent.cli",
            "run",
            "--server",
            "http://127.0.0.1:9",
            "--request",
            str(request_path),
            "--timeout-seconds",
            "0.1",
            "--pretty",
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert completed.returncode == 1
    assert "Traceback" not in completed.stderr
    body = json.loads(completed.stdout)
    assert body["status"] == "api_error"
    assert body["ready"] is False
    assert body["method"] == "POST"
    assert "/api/runs" in body["url"]
    assert "Unable to reach API" in body["error"]


def test_cli_run_reports_invalid_request_json_without_traceback(tmp_path):
    request_path = tmp_path / "run.json"
    request_path.write_text("{not valid json", encoding="utf-8")

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "relief_story_agent.cli",
            "run",
            "--server",
            "http://127.0.0.1:9",
            "--request",
            str(request_path),
            "--pretty",
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert completed.returncode == 1
    assert "Traceback" not in completed.stderr
    body = json.loads(completed.stdout)
    assert body["status"] == "invalid_request"
    assert body["path"] == str(request_path)
    assert "Invalid JSON" in body["error"]


def test_cli_connect_comfyui_reports_invalid_request_schema_without_traceback(tmp_path):
    request_path = tmp_path / "connect.json"
    request_path.write_text(json.dumps({"timeout_seconds": 0}), encoding="utf-8")

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "relief_story_agent.cli",
            "connect-comfyui",
            "--request",
            str(request_path),
            "--pretty",
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert completed.returncode == 1
    assert "Traceback" not in completed.stderr
    body = json.loads(completed.stdout)
    assert body["status"] == "invalid_request"
    assert body["path"] == str(request_path)
    assert "Invalid request" in body["error"]


def test_cli_batch_plan_posts_without_enqueueing(tmp_path):
    request_path = tmp_path / "batch.json"
    request_path.write_text(json.dumps({"items": [{"idea": "one"}]}), encoding="utf-8")
    server = _CliApiServer({"will_enqueue": False, "items": [{"index": 0}]})

    with server:
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "relief_story_agent.cli",
                "batch-plan",
                "--server",
                server.url,
                "--request",
                str(request_path),
                "--check-comfyui-connection",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )

    assert completed.returncode == 0
    assert json.loads(completed.stdout)["will_enqueue"] is False
    recorded = server.requests[0]
    assert recorded["path"] == "/api/batches/plan"
    assert recorded["query"] == {"check_comfyui_connection": ["true"]}
    assert recorded["json"] == {"items": [{"idea": "one"}]}


def test_cli_batch_posts_request_to_api(tmp_path):
    request_path = tmp_path / "batch.json"
    request_path.write_text(json.dumps({"items": [{"idea": "one"}]}), encoding="utf-8")
    server = _CliApiServer({"batch_id": "batch_cli", "status": "queued"})

    with server:
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "relief_story_agent.cli",
                "batch",
                "--server",
                server.url,
                "--request",
                str(request_path),
                "--preflight",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )

    assert completed.returncode == 0
    assert json.loads(completed.stdout)["batch_id"] == "batch_cli"
    recorded = server.requests[0]
    assert recorded["path"] == "/api/batches"
    assert recorded["query"] == {"preflight": ["true"]}


def test_cli_export_batch_posts_export_request():
    server = _CliApiServer({"export_dir": "D:/exports/batch_cli", "zip_path": "D:/exports/batch_cli.zip"})

    with server:
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "relief_story_agent.cli",
                "export-batch",
                "--server",
                server.url,
                "--batch-id",
                "batch_cli",
                "--export-root",
                "D:/exports",
                "--include-zip",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )

    assert completed.returncode == 0
    assert json.loads(completed.stdout)["zip_path"] == "D:/exports/batch_cli.zip"
    recorded = server.requests[0]
    assert recorded["path"] == "/api/batches/batch_cli/export"
    assert recorded["json"] == {"export_root": "D:/exports", "include_zip": True}


def test_cli_run_prints_server_error_body_without_traceback(tmp_path):
    request_path = tmp_path / "run.json"
    request_path.write_text(json.dumps({"idea": "bad run"}), encoding="utf-8")
    server = _CliApiServer(
        {"detail": {"message": "preflight validation failed"}},
        status_code=400,
    )

    with server:
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "relief_story_agent.cli",
                "run",
                "--server",
                server.url,
                "--request",
                str(request_path),
                "--preflight",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )

    assert completed.returncode == 1
    assert json.loads(completed.stdout)["detail"]["message"] == "preflight validation failed"
    assert "Traceback" not in completed.stderr


def test_cli_recovery_plan_gets_batch_recovery_plan():
    server = _CliApiServer({"batch_id": "batch_cli", "summary": {"auto": 1}})

    with server:
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "relief_story_agent.cli",
                "recovery-plan",
                "--server",
                server.url,
                "--batch-id",
                "batch_cli",
                "--pretty",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )

    assert completed.returncode == 0
    assert json.loads(completed.stdout)["summary"]["auto"] == 1
    recorded = server.requests[0]
    assert recorded["method"] == "GET"
    assert recorded["path"] == "/api/batches/batch_cli/recovery-plan"


def test_cli_run_status_gets_run_detail():
    server = _CliApiServer({"run_id": "run_cli", "status": "completed"})

    with server:
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "relief_story_agent.cli",
                "run-status",
                "--server",
                server.url,
                "--run-id",
                "run_cli",
                "--pretty",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )

    assert completed.returncode == 0
    assert json.loads(completed.stdout)["run_id"] == "run_cli"
    recorded = server.requests[0]
    assert recorded["method"] == "GET"
    assert recorded["path"] == "/api/runs/run_cli"


def test_cli_get_command_reports_api_connection_error_without_traceback():
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "relief_story_agent.cli",
            "run-status",
            "--server",
            "http://127.0.0.1:9",
            "--run-id",
            "run_missing_api",
            "--timeout-seconds",
            "0.1",
            "--pretty",
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert completed.returncode == 1
    assert "Traceback" not in completed.stderr
    body = json.loads(completed.stdout)
    assert body["status"] == "api_error"
    assert body["ready"] is False
    assert body["method"] == "GET"
    assert "/api/runs/run_missing_api" in body["url"]
    assert "Unable to reach API" in body["error"]


def test_cli_runs_lists_runs_with_filters():
    server = _CliApiServer({"items": [{"run_id": "run_cli", "status": "failed"}]})

    with server:
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "relief_story_agent.cli",
                "runs",
                "--server",
                server.url,
                "--status",
                "failed",
                "--parent-batch-id",
                "batch_cli",
                "--limit",
                "5",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )

    assert completed.returncode == 0
    assert json.loads(completed.stdout)["items"][0]["run_id"] == "run_cli"
    recorded = server.requests[0]
    assert recorded["method"] == "GET"
    assert recorded["path"] == "/api/runs"
    assert recorded["query"] == {
        "status": ["failed"],
        "parent_batch_id": ["batch_cli"],
        "limit": ["5"],
    }


def test_cli_batch_status_gets_batch_detail():
    server = _CliApiServer({"batch_id": "batch_cli", "status": "running"})

    with server:
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "relief_story_agent.cli",
                "batch-status",
                "--server",
                server.url,
                "--batch-id",
                "batch_cli",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )

    assert completed.returncode == 0
    assert json.loads(completed.stdout)["batch_id"] == "batch_cli"
    recorded = server.requests[0]
    assert recorded["method"] == "GET"
    assert recorded["path"] == "/api/batches/batch_cli"


def test_cli_batches_lists_batches_with_filters():
    server = _CliApiServer({"items": [{"batch_id": "batch_cli", "status": "completed"}]})

    with server:
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "relief_story_agent.cli",
                "batches",
                "--server",
                server.url,
                "--status",
                "completed",
                "--limit",
                "10",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )

    assert completed.returncode == 0
    assert json.loads(completed.stdout)["items"][0]["batch_id"] == "batch_cli"
    recorded = server.requests[0]
    assert recorded["method"] == "GET"
    assert recorded["path"] == "/api/batches"
    assert recorded["query"] == {"status": ["completed"], "limit": ["10"]}


def test_cli_scheduler_gets_scheduler_status():
    server = _CliApiServer({"queue_depth": 1, "active_items": []})

    with server:
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "relief_story_agent.cli",
                "scheduler",
                "--server",
                server.url,
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )

    assert completed.returncode == 0
    assert json.loads(completed.stdout)["queue_depth"] == 1
    recorded = server.requests[0]
    assert recorded["method"] == "GET"
    assert recorded["path"] == "/api/scheduler"


def test_cli_local_doctor_gets_running_server_report():
    server = _CliApiServer({"ready": True, "summary": {"failed": 0}})

    with server:
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "relief_story_agent.cli",
                "local-doctor",
                "--server",
                server.url,
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )

    assert completed.returncode == 0
    assert json.loads(completed.stdout)["ready"] is True
    recorded = server.requests[0]
    assert recorded["method"] == "GET"
    assert recorded["path"] == "/api/local/doctor"


def test_cli_local_doctor_can_request_comfyui_check():
    server = _CliApiServer({"ready": True, "summary": {"failed": 0}})

    with server:
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "relief_story_agent.cli",
                "local-doctor",
                "--server",
                server.url,
                "--check-comfyui-connection",
                "--comfyui-endpoint",
                "127.0.0.1:8188/queue",
                "--comfyui-timeout-seconds",
                "3",
                "--comfyui-workflow-path",
                "D:/ComfyUI/workflows/ltx23.json",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )

    assert completed.returncode == 0
    recorded = server.requests[0]
    assert recorded["path"] == "/api/local/doctor"
    assert recorded["query"] == {
        "check_comfyui_connection": ["true"],
        "comfyui_endpoint": ["127.0.0.1:8188/queue"],
        "comfyui_timeout_seconds": ["3.0"],
        "comfyui_workflow_path": ["D:/ComfyUI/workflows/ltx23.json"],
    }


def test_cli_local_readiness_gets_combined_setup_report():
    server = _CliApiServer({"ready_for_release": False, "suggested_actions": ["run_local_acceptance"]})

    with server:
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "relief_story_agent.cli",
                "local-readiness",
                "--server",
                server.url,
                "--acceptance-report",
                "D:/relief_story_config/acceptance/acceptance_report.json",
                "--check-comfyui-connection",
                "--comfyui-endpoint",
                "127.0.0.1:8188/queue",
                "--comfyui-timeout-seconds",
                "3",
                "--comfyui-workflow-path",
                "D:/ComfyUI/workflows/ltx23.json",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )

    assert completed.returncode == 0
    assert json.loads(completed.stdout)["suggested_actions"] == ["run_local_acceptance"]
    recorded = server.requests[0]
    assert recorded["method"] == "GET"
    assert recorded["path"] == "/api/local/readiness"
    assert recorded["query"] == {
        "acceptance_report_path": ["D:/relief_story_config/acceptance/acceptance_report.json"],
        "check_comfyui_connection": ["true"],
        "comfyui_endpoint": ["127.0.0.1:8188/queue"],
        "comfyui_timeout_seconds": ["3.0"],
        "comfyui_workflow_path": ["D:/ComfyUI/workflows/ltx23.json"],
    }


def test_cli_run_events_gets_incremental_events():
    server = _CliApiServer({"run_id": "run_cli", "events": [{"sequence": 13, "type": "stage_started"}]})

    with server:
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "relief_story_agent.cli",
                "run-events",
                "--server",
                server.url,
                "--run-id",
                "run_cli",
                "--after",
                "12",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )

    assert completed.returncode == 0
    assert json.loads(completed.stdout)["events"][0]["sequence"] == 13
    recorded = server.requests[0]
    assert recorded["method"] == "GET"
    assert recorded["path"] == "/api/runs/run_cli/events"
    assert recorded["query"] == {"after": ["12"]}


def test_cli_run_artifacts_gets_run_artifact_index():
    server = _CliApiServer({"run_id": "run_cli", "manifest": "00_manifest.json"})

    with server:
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "relief_story_agent.cli",
                "run-artifacts",
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
    assert json.loads(completed.stdout)["manifest"] == "00_manifest.json"
    recorded = server.requests[0]
    assert recorded["method"] == "GET"
    assert recorded["path"] == "/api/runs/run_cli/artifacts"


def test_cli_run_audit_gets_run_audit_report():
    server = _CliApiServer({"run_id": "run_cli", "valid": True})

    with server:
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "relief_story_agent.cli",
                "run-audit",
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
    assert json.loads(completed.stdout)["valid"] is True
    recorded = server.requests[0]
    assert recorded["method"] == "GET"
    assert recorded["path"] == "/api/runs/run_cli/audit"


def test_cli_batch_artifacts_gets_batch_artifact_index():
    server = _CliApiServer({"batch_id": "batch_cli", "publish_ready": 2})

    with server:
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "relief_story_agent.cli",
                "batch-artifacts",
                "--server",
                server.url,
                "--batch-id",
                "batch_cli",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )

    assert completed.returncode == 0
    assert json.loads(completed.stdout)["publish_ready"] == 2
    recorded = server.requests[0]
    assert recorded["method"] == "GET"
    assert recorded["path"] == "/api/batches/batch_cli/artifacts"


def test_cli_batch_health_gets_health_report():
    server = _CliApiServer({"batch_id": "batch_cli", "summary": {"failed": 0}})

    with server:
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "relief_story_agent.cli",
                "batch-health",
                "--server",
                server.url,
                "--batch-id",
                "batch_cli",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )

    assert completed.returncode == 0
    assert json.loads(completed.stdout)["summary"]["failed"] == 0
    recorded = server.requests[0]
    assert recorded["method"] == "GET"
    assert recorded["path"] == "/api/batches/batch_cli/health"


def test_cli_recover_batch_posts_dry_run_and_action_codes():
    server = _CliApiServer({"batch_id": "batch_cli", "dry_run": True})

    with server:
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "relief_story_agent.cli",
                "recover-batch",
                "--server",
                server.url,
                "--batch-id",
                "batch_cli",
                "--dry-run",
                "--action-code",
                "retry_from_stage",
                "--action-code",
                "refresh_comfyui_outputs",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )

    assert completed.returncode == 0
    recorded = server.requests[0]
    assert recorded["method"] == "POST"
    assert recorded["path"] == "/api/batches/batch_cli/recover"
    assert recorded["json"] == {
        "dry_run": True,
        "action_codes": ["retry_from_stage", "refresh_comfyui_outputs"],
    }


def test_cli_validate_export_posts_validation_request():
    server = _CliApiServer({"valid": True, "report_path": "D:/exports/batch_cli/validation_report.json"})

    with server:
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "relief_story_agent.cli",
                "validate-export",
                "--server",
                server.url,
                "--batch-id",
                "batch_cli",
                "--export-dir",
                "D:/exports/batch_cli",
                "--save-report",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )

    assert completed.returncode == 0
    recorded = server.requests[0]
    assert recorded["path"] == "/api/batches/batch_cli/export/validate"
    assert recorded["json"] == {"export_dir": "D:/exports/batch_cli", "save_report": True}


def test_cli_validate_export_returns_nonzero_when_report_is_invalid():
    server = _CliApiServer({"valid": False, "errors": ["missing publish_index.json"]})

    with server:
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "relief_story_agent.cli",
                "validate-export",
                "--server",
                server.url,
                "--batch-id",
                "batch_cli",
                "--export-dir",
                "D:/exports/batch_cli",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )

    assert completed.returncode == 1
    assert json.loads(completed.stdout)["valid"] is False


def test_cli_validate_export_zip_posts_zip_validation_request():
    server = _CliApiServer({"valid": True, "report_path": "D:/exports/batch_cli.zip.validation.json"})

    with server:
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "relief_story_agent.cli",
                "validate-export-zip",
                "--server",
                server.url,
                "--batch-id",
                "batch_cli",
                "--zip-path",
                "D:/exports/batch_cli.zip",
                "--expected-sha256",
                "abc123",
                "--expected-size-bytes",
                "42",
                "--save-report",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )

    assert completed.returncode == 0
    recorded = server.requests[0]
    assert recorded["path"] == "/api/batches/batch_cli/export/validate-zip"
    assert recorded["json"] == {
        "zip_path": "D:/exports/batch_cli.zip",
        "expected_sha256": "abc123",
        "expected_size_bytes": 42,
        "save_report": True,
    }


def test_cli_validate_export_zip_returns_nonzero_when_report_is_invalid():
    server = _CliApiServer({"valid": False, "errors": ["sha256 mismatch"]})

    with server:
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "relief_story_agent.cli",
                "validate-export-zip",
                "--server",
                server.url,
                "--batch-id",
                "batch_cli",
                "--zip-path",
                "D:/exports/batch_cli.zip",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )

    assert completed.returncode == 1
    assert json.loads(completed.stdout)["valid"] is False


class _CliApiServer:
    def __init__(self, response: dict, *, status_code: int = 200):
        self.response = response
        self.status_code = status_code
        self.requests: list[dict] = []
        self._server: ThreadingHTTPServer | None = None
        self._thread: Thread | None = None

    @property
    def url(self) -> str:
        assert self._server is not None
        host, port = self._server.server_address
        return f"http://{host}:{port}"

    def __enter__(self):
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                parsed = urlparse(self.path)
                owner.requests.append(
                    {
                        "method": "GET",
                        "path": parsed.path,
                        "query": parse_qs(parsed.query),
                        "json": {},
                    }
                )
                self._write_json_response()

            def do_POST(self):
                length = int(self.headers.get("content-length") or "0")
                raw_body = self.rfile.read(length).decode("utf-8")
                parsed = urlparse(self.path)
                owner.requests.append(
                    {
                        "method": "POST",
                        "path": parsed.path,
                        "query": parse_qs(parsed.query),
                        "json": json.loads(raw_body) if raw_body else {},
                    }
                )
                self._write_json_response()

            def _write_json_response(self):
                body = json.dumps(owner.response).encode("utf-8")
                self.send_response(owner.status_code)
                self.send_header("content-type", "application/json")
                self.send_header("content-length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, format, *args):
                return

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._thread = Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, exc_type, exc, tb):
        assert self._server is not None
        self._server.shutdown()
        self._server.server_close()
        if self._thread is not None:
            self._thread.join(timeout=5)


class _ComfyUIHistoryServer:
    def __init__(self, *, video_bytes: bytes):
        self.video_bytes = video_bytes
        self.requests: list[dict] = []
        self._server: ThreadingHTTPServer | None = None
        self._thread: Thread | None = None

    @property
    def url(self) -> str:
        assert self._server is not None
        host, port = self._server.server_address
        return f"http://{host}:{port}"

    def __enter__(self):
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                parsed = urlparse(self.path)
                owner.requests.append(
                    {
                        "method": "GET",
                        "path": parsed.path,
                        "query": parse_qs(parsed.query),
                    }
                )
                if parsed.path.startswith("/history/"):
                    prompt_id = parsed.path.rsplit("/", 1)[-1]
                    body = json.dumps(
                        {
                            prompt_id: {
                                "outputs": {
                                    "12": {
                                        "videos": [
                                            {
                                                "filename": "cli.mp4",
                                                "subfolder": "",
                                                "type": "output",
                                            }
                                        ]
                                    }
                                }
                            }
                        }
                    ).encode("utf-8")
                    self.send_response(200)
                    self.send_header("content-type", "application/json")
                    self.send_header("content-length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                    return
                if parsed.path == "/view":
                    self.send_response(200)
                    self.send_header("content-type", "video/mp4")
                    self.send_header("content-length", str(len(owner.video_bytes)))
                    self.end_headers()
                    self.wfile.write(owner.video_bytes)
                    return
                self.send_response(404)
                self.end_headers()

            def log_message(self, format, *args):
                return

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._thread = Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, exc_type, exc, tb):
        assert self._server is not None
        self._server.shutdown()
        self._server.server_close()
        if self._thread is not None:
            self._thread.join(timeout=5)
