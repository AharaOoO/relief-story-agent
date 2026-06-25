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
        },
        "limits": {
            "default_api_port": DEFAULT_API_PORT,
            "default_ui_port": 5173,
            "default_comfyui_port": 8188,
        },
        "endpoints": {
            "health": "/api/health",
            "metrics": "/api/metrics",
            "pipeline_schema": "/api/pipeline/schema",
            "model_config": "/api/config/models",
            "diagnose_run": "/api/config/diagnose",
            "diagnose_batch": "/api/config/diagnose-batch",
            "runs": "/api/runs",
            "run_detail": "/api/runs/{run_id}",
            "run_events": "/api/runs/{run_id}/events",
            "run_audit": "/api/runs/{run_id}/audit",
            "run_artifacts": "/api/runs/{run_id}/artifacts",
            "batches": "/api/batches",
            "batch_plan": "/api/batches/plan",
            "batch_health": "/api/batches/{batch_id}/health",
            "batch_recovery_plan": "/api/batches/{batch_id}/recovery-plan",
            "comfyui_connect": "/api/comfyui/connect",
            "comfyui_preview": "/api/comfyui/preview",
            "smoke_comfyui": "/api/smoke/comfyui",
        },
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
