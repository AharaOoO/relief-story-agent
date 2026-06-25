from __future__ import annotations

import time
from pathlib import Path
from typing import Callable

import httpx

from .comfyui import (
    ComfyUIOutputTimeout,
    collect_prompt_outputs,
    download_prompt_outputs,
    wait_for_prompt_outputs,
)
from .models import ComfyUIOutput, ComfyUIOutputRefreshRequest, ComfyUIRunConfig


def refresh_comfyui_prompt_outputs(
    request: ComfyUIOutputRefreshRequest,
    *,
    client: httpx.Client | None = None,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> dict:
    if request.download_outputs and not request.artifact_dir:
        raise ValueError("artifact_dir is required when download_outputs=true")

    config = ComfyUIRunConfig(
        enabled=True,
        endpoint=request.endpoint,
        wait_for_completion=request.wait_for_completion,
        download_outputs=request.download_outputs,
        output_timeout_seconds=request.output_timeout_seconds,
        output_poll_interval_seconds=request.output_poll_interval_seconds,
    )

    diagnostics: dict = {}
    status = "pending"
    error = ""
    try:
        if request.wait_for_completion:
            outputs = wait_for_prompt_outputs(
                config,
                request.prompt_ids,
                timeout_seconds=request.output_timeout_seconds,
                poll_interval_seconds=request.output_poll_interval_seconds,
                client=client,
                sleep_fn=sleep_fn,
            )
        else:
            outputs = collect_prompt_outputs(config, request.prompt_ids, client=client)
    except ComfyUIOutputTimeout as exc:
        status = "timeout"
        error = str(exc)
        diagnostics = exc.diagnostics
        try:
            outputs = collect_prompt_outputs(config, request.prompt_ids, client=client)
        except httpx.HTTPError as collect_exc:
            outputs = []
            status = "error"
            error = f"{error}; {collect_exc}"
    except httpx.HTTPError as exc:
        outputs = []
        status = "error"
        error = str(exc)

    if outputs and request.download_outputs:
        try:
            outputs = download_prompt_outputs(
                outputs,
                Path(request.artifact_dir),
                client=client,
            )
        except httpx.HTTPError as exc:
            status = "error"
            error = str(exc)

    history_ready = _all_requested_prompts_have_outputs(outputs, request.prompt_ids)
    ready = history_ready and status != "error"
    if ready:
        status = "ready"
    elif status not in {"timeout", "error"}:
        status = "pending"

    return {
        "endpoint": config.endpoint,
        "prompt_ids": list(request.prompt_ids),
        "status": status,
        "ready": ready,
        "output_count": len(outputs),
        "video_count": _count_media_type(outputs, "video"),
        "image_count": _count_media_type(outputs, "image"),
        "audio_count": _count_media_type(outputs, "audio"),
        "downloaded_count": len([output for output in outputs if output.local_path]),
        "artifact_dir": str(request.artifact_dir),
        "actual_outputs": [output.model_dump() for output in outputs],
        "diagnostics": diagnostics,
        "error": error,
    }


def _all_requested_prompts_have_outputs(
    outputs: list[ComfyUIOutput],
    prompt_ids: list[str],
) -> bool:
    found = {output.prompt_id for output in outputs}
    return set(prompt_ids).issubset(found)


def _count_media_type(outputs: list[ComfyUIOutput], media_type: str) -> int:
    return len([output for output in outputs if output.media_type == media_type])
