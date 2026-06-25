from __future__ import annotations

from fastapi.testclient import TestClient

from relief_story_agent.api import create_app
from relief_story_agent.local_runtime import (
    LocalRuntimeConfig,
    build_local_bootstrap,
    build_local_doctor,
)
from relief_story_agent.orchestrator import StoryRunOrchestrator
from relief_story_agent.providers import FakeModelProvider
from relief_story_agent.server import build_app


def test_build_local_bootstrap_exposes_ui_ports_and_core_endpoints():
    bootstrap = build_local_bootstrap(
        LocalRuntimeConfig(
            api_host="127.0.0.1",
            api_port=8891,
            ui_origin="http://127.0.0.1:5173",
            allowed_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
        )
    )

    assert bootstrap["api"]["base_url"] == "http://127.0.0.1:8891"
    assert bootstrap["ui"]["recommended_dev_origin"] == "http://127.0.0.1:5173"
    assert "http://localhost:5173" in bootstrap["ui"]["allowed_origins"]
    assert bootstrap["comfyui"]["default_endpoint"] == "http://127.0.0.1:8188"
    assert bootstrap["comfyui"]["doctor_endpoint"] == "/api/local/doctor"
    assert bootstrap["endpoints"]["health"] == "/api/health"
    assert bootstrap["endpoints"]["local_doctor"] == "/api/local/doctor"
    assert bootstrap["endpoints"]["local_acceptance_status"] == "/api/local/acceptance-status"
    assert bootstrap["endpoints"]["pipeline_schema"] == "/api/pipeline/schema"
    assert bootstrap["endpoints"]["run_audit"] == "/api/runs/{run_id}/audit"
    assert bootstrap["endpoints"]["run_timeline"] == "/api/runs/{run_id}/timeline"
    assert bootstrap["endpoints"]["batch_timeline"] == "/api/batches/{batch_id}/timeline"
    assert bootstrap["endpoints"]["local_setup_bundle"] == "/api/local/setup-bundle"
    assert bootstrap["endpoints"]["model_check"] == "/api/config/model-check"
    assert bootstrap["endpoints"]["comfyui_connect"] == "/api/comfyui/connect"
    assert bootstrap["endpoints"]["comfyui_discover_workflows"] == "/api/comfyui/discover-workflows"
    assert bootstrap["endpoints"]["comfyui_outputs"] == "/api/comfyui/outputs"


def test_api_local_bootstrap_returns_runtime_config_for_ui_shell():
    app = create_app(
        StoryRunOrchestrator(provider=FakeModelProvider.minimal_success()),
        local_runtime=LocalRuntimeConfig(
            api_host="127.0.0.1",
            api_port=8899,
            ui_origin="http://127.0.0.1:5174",
        ),
    )
    client = TestClient(app)

    response = client.get("/api/local/bootstrap")

    assert response.status_code == 200
    body = response.json()
    assert body["api"]["base_url"] == "http://127.0.0.1:8899"
    assert body["ui"]["recommended_dev_origin"] == "http://127.0.0.1:5174"
    assert body["limits"]["default_api_port"] == 8891


def test_server_build_app_allows_local_ui_cors_origin(tmp_path):
    app = build_app(
        state_dir=str(tmp_path / "state"),
        provider=FakeModelProvider.minimal_success(),
        host="127.0.0.1",
        port=8899,
        ui_origin="http://127.0.0.1:5174",
    )
    client = TestClient(app)

    response = client.options(
        "/api/health",
        headers={
            "Origin": "http://127.0.0.1:5174",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:5174"


def test_build_local_doctor_reports_missing_model_environment():
    report = build_local_doctor(
        bootstrap=build_local_bootstrap(),
        model_status={
            "profiles": {
                "writer": {
                    "api_key_env": "MISSING_KEY",
                    "secret_required": True,
                    "secret_configured": False,
                }
            },
            "stages": {"chief_screenwriter": "writer"},
            "missing_environment_variables": ["MISSING_KEY"],
        },
        resource_status={"image_generation_concurrency": 2, "comfyui_submission_concurrency": 1},
        scheduler_enabled=True,
        state_persistent=True,
    )

    checks = {check["id"]: check for check in report["checks"]}
    assert report["ready"] is False
    assert checks["model_environment"]["status"] == "fail"
    assert checks["model_environment"]["details"]["missing_environment_variables"] == ["MISSING_KEY"]
    assert "configure_model_environment" in report["suggested_actions"]


def test_build_local_doctor_flags_placeholder_model_profiles():
    report = build_local_doctor(
        bootstrap=build_local_bootstrap(),
        model_status={
            "profiles": {
                "writer": {
                    "base_url": "https://YOUR_PROVIDER_ENDPOINT/v1",
                    "model": "YOUR_MODEL",
                    "api_key_env": "WRITER_KEY",
                    "secret_required": True,
                    "secret_configured": True,
                }
            },
            "stages": {"chief_screenwriter": "writer"},
            "missing_environment_variables": [],
        },
        resource_status={"image_generation_concurrency": 2, "comfyui_submission_concurrency": 1},
        scheduler_enabled=True,
        state_persistent=True,
    )

    checks = {check["id"]: check for check in report["checks"]}
    assert report["ready"] is False
    assert checks["model_profiles"]["status"] == "fail"
    assert checks["model_profiles"]["details"]["placeholder_profiles"] == ["writer"]
    assert "fix_model_profiles" in report["suggested_actions"]


def test_build_local_doctor_reports_comfyui_connection_failure():
    report = build_local_doctor(
        bootstrap=build_local_bootstrap(),
        model_status={"profiles": {}, "stages": {}, "missing_environment_variables": []},
        resource_status={"image_generation_concurrency": 2, "comfyui_submission_concurrency": 1},
        scheduler_enabled=True,
        state_persistent=True,
        comfyui_status={
            "checked": True,
            "connected": False,
            "endpoint": "http://127.0.0.1:8188",
            "message": "Cannot reach ComfyUI /queue: offline",
        },
    )

    checks = {check["id"]: check for check in report["checks"]}
    assert report["ready"] is False
    assert checks["comfyui_connection"]["status"] == "fail"
    assert checks["comfyui_connection"]["details"]["endpoint"] == "http://127.0.0.1:8188"
    assert "start_or_check_comfyui" in report["suggested_actions"]


def test_build_local_doctor_fails_when_comfyui_runtime_is_connected_but_not_ready():
    report = build_local_doctor(
        bootstrap=build_local_bootstrap(),
        model_status={"profiles": {}, "stages": {}, "missing_environment_variables": []},
        resource_status={"image_generation_concurrency": 2, "comfyui_submission_concurrency": 1},
        scheduler_enabled=True,
        state_persistent=True,
        comfyui_status={
            "checked": True,
            "connected": True,
            "ready": False,
            "endpoint": "http://127.0.0.1:8188",
            "queue": {"running": 0, "pending": 0},
            "message": "ComfyUI is missing node types required by the workflow.",
            "checks": [
                {
                    "name": "comfyui_node_types",
                    "status": "failed",
                    "message": "ComfyUI is missing node types required by the workflow.",
                    "details": {"missing_node_types": ["MissingSampler"]},
                }
            ],
            "suggested_actions": ["install_or_enable_comfyui_nodes"],
        },
    )

    checks = {check["id"]: check for check in report["checks"]}
    assert report["ready"] is False
    assert checks["comfyui_connection"]["status"] == "fail"
    assert checks["comfyui_connection"]["details"]["ready"] is False
    assert checks["comfyui_connection"]["details"]["checks"][0]["name"] == "comfyui_node_types"
    assert "start_or_check_comfyui" in report["suggested_actions"]


def test_api_local_doctor_reports_ready_when_runtime_is_configured(tmp_path):
    app = build_app(
        state_dir=str(tmp_path / "state"),
        provider=FakeModelProvider.minimal_success(),
        host="127.0.0.1",
        port=8899,
        ui_origin="http://127.0.0.1:5174",
    )
    client = TestClient(app)

    response = client.get("/api/local/doctor")

    assert response.status_code == 200
    body = response.json()
    assert body["bootstrap"]["api"]["base_url"] == "http://127.0.0.1:8899"
    assert body["summary"]["failed"] == 0
    assert body["checks"][0]["id"] == "api"


def test_api_local_doctor_can_ping_comfyui_when_requested(tmp_path, monkeypatch):
    calls = []

    def fake_connect(request):
        calls.append(request)
        return {
            "connected": True,
            "ready": True,
            "endpoint": request.endpoint,
            "queue": {"running": 1, "pending": 2},
            "checks": [
                {
                    "name": "comfyui_endpoint",
                    "status": "passed",
                    "message": "ComfyUI /queue is reachable.",
                    "details": {},
                }
            ],
        }

    monkeypatch.setattr("relief_story_agent.api.connect_comfyui", fake_connect)
    app = build_app(
        state_dir=str(tmp_path / "state"),
        provider=FakeModelProvider.minimal_success(),
        host="127.0.0.1",
        port=8899,
    )
    client = TestClient(app)

    response = client.get(
        "/api/local/doctor",
        params={
            "check_comfyui_connection": "true",
            "comfyui_endpoint": "127.0.0.1:8188/queue",
            "comfyui_timeout_seconds": "3",
        },
    )

    body = response.json()
    checks = {check["id"]: check for check in body["checks"]}
    assert response.status_code == 200
    assert calls[0].endpoint == "http://127.0.0.1:8188"
    assert calls[0].timeout_seconds == 3
    assert checks["comfyui_connection"]["status"] == "pass"
    assert checks["comfyui_connection"]["details"]["queue"] == {"running": 1, "pending": 2}


def test_api_local_doctor_passes_workflow_path_to_comfyui_connection(tmp_path, monkeypatch):
    calls = []

    def fake_connect(request):
        calls.append(request)
        return {
            "connected": True,
            "ready": False,
            "endpoint": request.endpoint,
            "queue": {"running": 0, "pending": 0},
            "checks": [
                {
                    "name": "comfyui_endpoint",
                    "status": "passed",
                    "message": "ComfyUI /queue is reachable.",
                    "details": {},
                },
                {
                    "name": "comfyui_node_types",
                    "status": "failed",
                    "message": "ComfyUI is missing node types required by the workflow.",
                    "details": {"missing_node_types": ["MissingSampler"]},
                },
            ],
            "suggested_actions": ["install_or_enable_comfyui_nodes"],
        }

    monkeypatch.setattr("relief_story_agent.api.connect_comfyui", fake_connect)
    app = build_app(
        state_dir=str(tmp_path / "state"),
        provider=FakeModelProvider.minimal_success(),
        host="127.0.0.1",
        port=8899,
    )
    client = TestClient(app)
    workflow_path = tmp_path / "workflow.json"
    workflow_path.write_text("{}", encoding="utf-8")

    response = client.get(
        "/api/local/doctor",
        params={
            "check_comfyui_connection": "true",
            "comfyui_endpoint": "127.0.0.1:8188/queue",
            "comfyui_workflow_path": str(workflow_path),
        },
    )

    body = response.json()
    checks = {check["id"]: check for check in body["checks"]}
    assert response.status_code == 200
    assert calls[0].workflow_api_path == str(workflow_path)
    assert body["ready"] is False
    assert checks["comfyui_connection"]["status"] == "fail"
