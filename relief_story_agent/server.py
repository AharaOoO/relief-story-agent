from __future__ import annotations

import argparse

import uvicorn

from .api import create_app
from .image_providers import OpenAICompatibleGridImageProvider
from .model_config import ModelConfigRegistry
from .orchestrator import InMemoryRunStore, StoryRunOrchestrator
from .providers import OpenAICompatibleProvider
from .resource_limits import ExecutionResourceLimits
from .scheduler import PersistentRunScheduler
from .storage import JsonFileRunStore


def build_app(
    state_dir: str | None = None,
    provider: OpenAICompatibleProvider | None = None,
    model_config_path: str | None = None,
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
        grid_image_provider=OpenAICompatibleGridImageProvider(),
        resource_limits=limits,
    )
    scheduler = PersistentRunScheduler(
        orchestrator,
        max_workers=max_workers,
        lease_seconds=lease_seconds,
        recovery_poll_seconds=recovery_poll_seconds,
    )
    return create_app(orchestrator, scheduler=scheduler)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8891, type=int)
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
    args = parser.parse_args()
    uvicorn.run(
        build_app(
            state_dir=args.state_dir,
            model_config_path=args.model_config,
            max_workers=args.max_workers,
            lease_seconds=args.lease_seconds,
            recovery_poll_seconds=args.recovery_poll_seconds,
            image_generation_concurrency=args.image_generation_concurrency,
            comfyui_submission_concurrency=args.comfyui_submission_concurrency,
        ),
        host=args.host,
        port=args.port,
    )


if __name__ == "__main__":
    main()
