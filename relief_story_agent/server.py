from __future__ import annotations

import argparse
import json

import uvicorn

from .api import create_app
from .image_providers import GridImageProviderRouter
from .local_runtime import DEFAULT_COMFYUI_ENDPOINT, DEFAULT_UI_ORIGIN, LocalRuntimeConfig
from .model_config import ModelConfigRegistry
from .orchestrator import InMemoryRunStore, StoryRunOrchestrator
from .providers import OpenAICompatibleProvider
from .resource_limits import ExecutionResourceLimits
from .scheduler import PersistentRunScheduler
from .storage import JsonFileRunStore


def _model_config_error_payload(path: str, error: str) -> dict:
    return {
        "status": "invalid_request",
        "ready": False,
        "path": path,
        "error": error,
    }


def _model_config_error(path: str, exc: Exception) -> dict:
    if isinstance(exc, OSError):
        message = f"Unable to read model config: {exc}"
    else:
        message = f"Invalid model config: {exc}"
    return _model_config_error_payload(path, message)


def build_app(
    state_dir: str | None = None,
    provider: OpenAICompatibleProvider | None = None,
    model_config_path: str | None = None,
    host: str = "127.0.0.1",
    port: int = 8891,
    ui_origin: str = DEFAULT_UI_ORIGIN,
    cors_origin: list[str] | None = None,
    comfyui_endpoint: str = DEFAULT_COMFYUI_ENDPOINT,
    max_workers: int = 2,
    lease_seconds: float = 300.0,
    recovery_poll_seconds: float = 5.0,
    image_generation_concurrency: int = 2,
    comfyui_submission_concurrency: int = 1,
):
    store = JsonFileRunStore(state_dir) if state_dir else InMemoryRunStore()
    registry = (
        ModelConfigRegistry.from_file(model_config_path)
        if model_config_path
        else ModelConfigRegistry()
    )
    limits = ExecutionResourceLimits(
        image_generation_concurrency=image_generation_concurrency,
        comfyui_submission_concurrency=comfyui_submission_concurrency,
    )
    orchestrator = StoryRunOrchestrator(
        provider=provider or OpenAICompatibleProvider(),
        store=store,
        model_registry=registry,
        grid_image_provider=GridImageProviderRouter(),
        resource_limits=limits,
    )
    scheduler = PersistentRunScheduler(
        orchestrator,
        max_workers=max_workers,
        lease_seconds=lease_seconds,
        recovery_poll_seconds=recovery_poll_seconds,
    )
    return create_app(
        orchestrator,
        scheduler=scheduler,
        local_runtime=LocalRuntimeConfig(
            api_host=host,
            api_port=port,
            ui_origin=ui_origin,
            allowed_origins=cors_origin or [],
            comfyui_endpoint=comfyui_endpoint,
        ),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8891, type=int)
    parser.add_argument("--ui-origin", default=DEFAULT_UI_ORIGIN, help="Local UI origin allowed by CORS.")
    parser.add_argument(
        "--cors-origin",
        action="append",
        default=[],
        help="Extra allowed local UI origin. Repeat for multiple origins.",
    )
    parser.add_argument(
        "--comfyui-endpoint",
        default=DEFAULT_COMFYUI_ENDPOINT,
        help="Default ComfyUI endpoint advertised to local UI bootstrap.",
    )
    parser.add_argument("--state-dir", default=None, help="Optional directory for persistent run and batch JSON state.")
    parser.add_argument(
        "--model-config",
        default=None,
        help="Optional JSON model profile registry. API keys must use api_key_env.",
    )
    parser.add_argument("--max-workers", default=2, type=int)
    parser.add_argument("--lease-seconds", default=300.0, type=float)
    parser.add_argument(
        "--recovery-poll-seconds",
        default=5.0,
        type=float,
        help="How often the scheduler scans persistent state for queued or expired running tasks.",
    )
    parser.add_argument("--image-generation-concurrency", default=2, type=int)
    parser.add_argument("--comfyui-submission-concurrency", default=1, type=int)
    args = parser.parse_args(argv)
    try:
        app = build_app(
            state_dir=args.state_dir,
            model_config_path=args.model_config,
            host=args.host,
            port=args.port,
            ui_origin=args.ui_origin,
            cors_origin=args.cors_origin,
            comfyui_endpoint=args.comfyui_endpoint,
            max_workers=args.max_workers,
            lease_seconds=args.lease_seconds,
            recovery_poll_seconds=args.recovery_poll_seconds,
            image_generation_concurrency=args.image_generation_concurrency,
            comfyui_submission_concurrency=args.comfyui_submission_concurrency,
        )
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        if not args.model_config:
            raise
        print(json.dumps(_model_config_error(args.model_config, exc), ensure_ascii=False))
        return 1
    uvicorn.run(app, host=args.host, port=args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
