from __future__ import annotations

from dataclasses import dataclass, field

from .comfyui_endpoint import normalize_comfyui_endpoint


DEFAULT_API_HOST = "127.0.0.1"
DEFAULT_API_PORT = 8891
DEFAULT_UI_ORIGIN = "http://127.0.0.1:5173"
DEFAULT_COMFYUI_ENDPOINT = "http://127.0.0.1:8188"


@dataclass(frozen=True)
class LocalRuntimeConfig:
    api_host: str = DEFAULT_API_HOST
    api_port: int = DEFAULT_API_PORT
    ui_origin: str = DEFAULT_UI_ORIGIN
    comfyui_endpoint: str = DEFAULT_COMFYUI_ENDPOINT
    allowed_origins: list[str] = field(default_factory=list)

    def normalized_allowed_origins(self) -> list[str]:
        origins = [
            self.ui_origin,
            "http://127.0.0.1:5173",
            "http://localhost:5173",
            "http://127.0.0.1:4173",
            "http://localhost:4173",
            "http://127.0.0.1:3000",
            "http://localhost:3000",
        ]
        origins.extend(self.allowed_origins)
        return _dedupe([_normalize_origin(origin) for origin in origins if origin])


def build_local_bootstrap(config: LocalRuntimeConfig | None = None) -> dict:
    runtime = config or LocalRuntimeConfig()
    base_url = f"http://{runtime.api_host}:{runtime.api_port}"
    return {
        "api": {
            "host": runtime.api_host,
            "port": runtime.api_port,
            "base_url": base_url,
            "health_url": f"{base_url}/api/health",
            "docs_url": f"{base_url}/docs",
        },
        "ui": {
            "recommended_dev_origin": _normalize_origin(runtime.ui_origin),
            "allowed_origins": runtime.normalized_allowed_origins(),
            "cors_enabled": True,
        },
        "comfyui": {
            "default_endpoint": normalize_comfyui_endpoint(runtime.comfyui_endpoint),
            "connect_endpoint": "/api/comfyui/connect",
            "discover_workflows_endpoint": "/api/comfyui/discover-workflows",
            "outputs_endpoint": "/api/comfyui/outputs",
        },
        "limits": {
            "default_api_port": DEFAULT_API_PORT,
            "default_ui_port": 5173,
            "default_comfyui_port": 8188,
        },
        "endpoints": {
            "health": "/api/health",
            "local_setup_bundle": "/api/local/setup-bundle",
            "metrics": "/api/metrics",
            "pipeline_schema": "/api/pipeline/schema",
            "model_config": "/api/config/models",
            "model_check": "/api/config/model-check",
            "diagnose_run": "/api/config/diagnose",
            "diagnose_batch": "/api/config/diagnose-batch",
            "runs": "/api/runs",
            "run_detail": "/api/runs/{run_id}",
            "run_events": "/api/runs/{run_id}/events",
            "run_audit": "/api/runs/{run_id}/audit",
            "run_timeline": "/api/runs/{run_id}/timeline",
            "run_artifacts": "/api/runs/{run_id}/artifacts",
            "batches": "/api/batches",
            "batch_plan": "/api/batches/plan",
            "batch_health": "/api/batches/{batch_id}/health",
            "batch_recovery_plan": "/api/batches/{batch_id}/recovery-plan",
            "comfyui_connect": "/api/comfyui/connect",
            "comfyui_discover_workflows": "/api/comfyui/discover-workflows",
            "comfyui_preview": "/api/comfyui/preview",
            "comfyui_outputs": "/api/comfyui/outputs",
            "smoke_comfyui": "/api/smoke/comfyui",
        },
    }


def build_local_doctor(
    *,
    bootstrap: dict,
    model_status: dict,
    resource_status: dict,
    scheduler_enabled: bool,
    state_persistent: bool,
    comfyui_status: dict | None = None,
) -> dict:
    checks = [
        _doctor_check(
            "api",
            "pass",
            "Local API is running.",
            {"base_url": bootstrap["api"]["base_url"]},
        ),
        _doctor_check(
            "ui_bootstrap",
            "pass",
            "UI bootstrap contract is available.",
            {
                "recommended_dev_origin": bootstrap["ui"]["recommended_dev_origin"],
                "allowed_origins": bootstrap["ui"]["allowed_origins"],
            },
        ),
        _model_profiles_check(model_status),
        _model_environment_check(model_status),
        _doctor_check(
            "state_backend",
            "pass" if state_persistent else "warn",
            (
                "Persistent state backend is enabled."
                if state_persistent
                else "State is in-memory; use --state-dir for local deployment."
            ),
            {"persistent": state_persistent},
        ),
        _doctor_check(
            "scheduler",
            "pass" if scheduler_enabled else "warn",
            (
                "Background scheduler is enabled."
                if scheduler_enabled
                else "Background scheduler is not attached."
            ),
            {"enabled": scheduler_enabled},
        ),
        _doctor_check(
            "resource_limits",
            "pass",
            "Resource limits are configured.",
            resource_status,
        ),
    ]
    if comfyui_status and comfyui_status.get("checked"):
        checks.append(_comfyui_connection_check(comfyui_status))
    summary = {
        "passed": sum(1 for check in checks if check["status"] == "pass"),
        "warnings": sum(1 for check in checks if check["status"] == "warn"),
        "failed": sum(1 for check in checks if check["status"] == "fail"),
    }
    return {
        "ready": summary["failed"] == 0,
        "summary": summary,
        "checks": checks,
        "suggested_actions": _doctor_actions(checks),
        "bootstrap": bootstrap,
    }


def _comfyui_connection_check(comfyui_status: dict) -> dict:
    connected = bool(comfyui_status.get("connected"))
    return _doctor_check(
        "comfyui_connection",
        "pass" if connected else "fail",
        (
            "ComfyUI /queue is reachable."
            if connected
            else str(comfyui_status.get("message") or "Cannot reach ComfyUI /queue.")
        ),
        {
            "endpoint": str(comfyui_status.get("endpoint") or ""),
            "queue": comfyui_status.get("queue") or {},
        },
    )


def _model_profiles_check(model_status: dict) -> dict:
    profiles = model_status.get("profiles") or {}
    stages = model_status.get("stages") or {}
    if not profiles or not stages:
        return _doctor_check(
            "model_profiles",
            "warn",
            "No model profiles or stage bindings are configured.",
            {"profile_count": len(profiles), "stage_count": len(stages)},
        )
    placeholder_profiles = [
        name
        for name, profile in sorted(profiles.items())
        if _has_placeholder_value(str(profile.get("model") or ""))
        or _has_placeholder_value(str(profile.get("base_url") or ""))
    ]
    if placeholder_profiles:
        return _doctor_check(
            "model_profiles",
            "fail",
            "Model profile placeholders must be replaced before running.",
            {
                "profile_count": len(profiles),
                "stage_count": len(stages),
                "placeholder_profiles": placeholder_profiles,
            },
        )
    return _doctor_check(
        "model_profiles",
        "pass",
        "Model profiles and stage bindings are configured.",
        {"profile_count": len(profiles), "stage_count": len(stages)},
    )


def _model_environment_check(model_status: dict) -> dict:
    missing = list(model_status.get("missing_environment_variables") or [])
    if missing:
        return _doctor_check(
            "model_environment",
            "fail",
            "Model API key environment variables are missing.",
            {"missing_environment_variables": missing},
        )
    return _doctor_check(
        "model_environment",
        "pass",
        "Required model API key environment variables are configured.",
        {"missing_environment_variables": []},
    )


def _doctor_actions(checks: list[dict]) -> list[str]:
    actions: list[str] = []
    for check in checks:
        if check["status"] == "pass":
            continue
        if check["id"] == "model_profiles":
            details = check.get("details") or {}
            actions.append("fix_model_profiles" if details.get("placeholder_profiles") else "run_setup")
        elif check["id"] == "model_environment":
            actions.append("configure_model_environment")
        elif check["id"] == "state_backend":
            actions.append("restart_with_state_dir")
        elif check["id"] == "scheduler":
            actions.append("start_server_entrypoint")
        elif check["id"] == "comfyui_connection":
            actions.append("start_or_check_comfyui")
        else:
            actions.append("inspect_local_runtime")
    return _dedupe(actions)


def _doctor_check(check_id: str, status: str, message: str, details: dict) -> dict:
    return {
        "id": check_id,
        "status": status,
        "message": message,
        "details": details,
    }


def _normalize_origin(value: str) -> str:
    stripped = str(value or "").strip().rstrip("/")
    if not stripped:
        return DEFAULT_UI_ORIGIN
    if "://" not in stripped:
        stripped = f"http://{stripped}"
    return stripped


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _has_placeholder_value(value: str) -> bool:
    normalized = value.strip().upper()
    return "YOUR_" in normalized or "REPLACE_ME" in normalized or normalized in {"TODO", "TBD"}
