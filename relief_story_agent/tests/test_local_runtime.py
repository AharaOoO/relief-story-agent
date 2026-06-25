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
    assert bootstrap["endpoints"]["health"] == "/api/health"
    assert bootstrap["endpoints"]["pipeline_schema"] == "/api/pipeline/schema"
    assert bootstrap["endpoints"]["run_audit"] == "/api/runs/{run_id}/audit"
    assert bootstrap["endpoints"]["comfyui_connect"] == "/api/comfyui/connect"


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
