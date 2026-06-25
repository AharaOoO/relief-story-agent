from __future__ import annotations

from typing import Any

from .config_validation import validate_batch_configuration
from .model_config import ModelConfigRegistry
from .models import BatchRunRequest, RunRequest


def build_batch_plan(
    request: BatchRunRequest,
    model_registry: ModelConfigRegistry,
    *,
    check_comfyui_connection: bool = False,
) -> dict[str, Any]:
    items = [
        _planned_item(index, item)
        for index, item in enumerate(request.resolved_items())
    ]
    execution_order = sorted(
        items,
        key=lambda item: (-item["queue_priority"], item["index"]),
    )
    for position, item in enumerate(execution_order, start=1):
        item["position"] = position
    return {
        "will_enqueue": False,
        "item_count": len(items),
        "failure_policy": request.failure_policy.model_dump(),
        "items": items,
        "execution_order": execution_order,
        "validation": validate_batch_configuration(
            request,
            model_registry,
            check_comfyui_connection=check_comfyui_connection,
        ),
    }


def _planned_item(index: int, item: RunRequest) -> dict[str, Any]:
    return {
        "index": index,
        "idea": item.idea,
        "queue_priority": item.queue_priority,
        "approval_mode": item.approval_mode,
        "preferred_series": item.preferred_series,
        "preferred_style": item.preferred_style,
        "duration_seconds": item.duration_seconds,
        "auto_select_core": item.auto_select_core,
        "output_root": item.output_root or "",
        "comfyui_enabled": bool(item.comfyui and item.comfyui.enabled),
        "workflow_api_path": (
            item.comfyui.workflow_api_path
            if item.comfyui and item.comfyui.workflow_api_path
            else ""
        ),
        "placeholder_map_path": (
            item.comfyui.placeholder_map_path
            if item.comfyui and item.comfyui.placeholder_map_path
            else ""
        ),
        "prompt_writer_template_path": item.template_paths.prompt_writer_template_path or "",
        "prompt_audit_template_path": item.template_paths.prompt_audit_template_path or "",
        "model_profiles": dict(item.model_profiles),
    }
