from __future__ import annotations

import json
import os
import re
import uuid
from pathlib import Path
from typing import Any

import httpx

from .comfyui import resolve_placeholder_map
from .grid_image import validate_grid_image
from .ltx_workflow import detect_workflow_format, find_ltx_injection_points, litegraph_to_api_prompt
from .model_config import ModelConfigRegistry
from .models import BatchRunRequest, RunRequest
from .pipeline import stage_ids_for_run
from .provenance import build_run_configuration_provenance


SUPPORTED_TEMPLATE_PLACEHOLDERS = {
    "script_json",
    "storyboard_json",
    "audit_json",
    "duration_seconds",
    "preferred_style",
    "workflow_context",
}


def validate_run_configuration(
    request: RunRequest,
    model_registry: ModelConfigRegistry,
    *,
    check_comfyui_connection: bool = False,
) -> dict[str, Any]:
    checks = [
        _validate_model_environment(model_registry),
        _validate_template(
            "prompt_writer_template",
            request.template_paths.prompt_writer_template_path,
            required=("script_json",),
        ),
        _validate_template(
            "prompt_audit_template",
            request.template_paths.prompt_audit_template_path,
            required=("script_json", "storyboard_json"),
        ),
        _validate_comfyui_workflow(request),
        _validate_grid_image_config(request),
        _validate_output_root(request),
        _validate_execution_policy(request),
    ]
    if check_comfyui_connection:
        checks.append(_validate_comfyui_endpoint(request))
    return {
        "passed": all(check["status"] != "failed" for check in checks),
        "checks": checks,
    }


def diagnose_run_configuration(
    request: RunRequest,
    model_registry: ModelConfigRegistry,
    *,
    check_comfyui_connection: bool = False,
) -> dict[str, Any]:
    validation = validate_run_configuration(
        request,
        model_registry,
        check_comfyui_connection=check_comfyui_connection,
    )
    summary = _summarize_checks(validation["checks"])
    return {
        "ready": summary["failed"] == 0,
        "passed": validation["passed"],
        "summary": summary,
        "checks": validation["checks"],
        "suggested_actions": _suggest_actions_for_checks(validation["checks"]),
        "provenance": build_run_configuration_provenance(request),
    }


def validate_batch_configuration(
    request: BatchRunRequest,
    model_registry: ModelConfigRegistry,
    *,
    check_comfyui_connection: bool = False,
) -> dict[str, Any]:
    items = []
    for index, item in enumerate(request.resolved_items()):
        result = validate_run_configuration(
            item,
            model_registry,
            check_comfyui_connection=check_comfyui_connection,
        )
        items.append(
            {
                "index": index,
                "idea": item.idea,
                "passed": result["passed"],
                "checks": result["checks"],
            }
        )
    failed = sum(1 for item in items if not item["passed"])
    passed = len(items) - failed
    return {
        "passed": failed == 0,
        "summary": {
            "total": len(items),
            "passed": passed,
            "failed": failed,
        },
        "items": items,
    }


def diagnose_batch_configuration(
    request: BatchRunRequest,
    model_registry: ModelConfigRegistry,
    *,
    check_comfyui_connection: bool = False,
) -> dict[str, Any]:
    items = []
    for index, item in enumerate(request.resolved_items()):
        result = diagnose_run_configuration(
            item,
            model_registry,
            check_comfyui_connection=check_comfyui_connection,
        )
        items.append(
            {
                "index": index,
                "idea": item.idea,
                "ready": result["ready"],
                "summary": result["summary"],
                "checks": result["checks"],
                "suggested_actions": result["suggested_actions"],
                "provenance": result["provenance"],
            }
        )
    ready_count = sum(1 for item in items if item["ready"])
    blocked_count = len(items) - ready_count
    return {
        "ready": blocked_count == 0,
        "summary": {
            "total": len(items),
            "ready": ready_count,
            "blocked": blocked_count,
            "suggested_actions": _count_batch_actions(items),
        },
        "items": items,
    }


def _validate_model_environment(model_registry: ModelConfigRegistry) -> dict[str, Any]:
    status = model_registry.status()
    missing = status.get("missing_environment_variables") or []
    if missing:
        return _check(
            "model_environment",
            "failed",
            "Missing model API key environment variable(s).",
            {"missing_environment_variables": missing},
        )
    return _check(
        "model_environment",
        "passed",
        "Model profile environment variables are configured.",
        {"profile_count": len(status.get("profiles") or {})},
    )


def _validate_template(
    name: str,
    path: str | None,
    *,
    required: tuple[str, ...],
) -> dict[str, Any]:
    if not path:
        return _check(name, "passed", "Using built-in default template.")
    template_path = Path(path)
    if not template_path.exists():
        return _check(name, "failed", f"Template file not found: {path}")
    try:
        text = template_path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        return _check(name, "failed", f"Template must be UTF-8: {exc}")
    missing = [key for key in required if "{{" + key + "}}" not in text]
    if missing:
        return _check(
            name,
            "failed",
            f"Template missing required placeholder(s): {', '.join(missing)}",
        )
    unsupported = sorted(
        {
            key.strip()
            for key in re.findall(r"{{\s*([^{}]+?)\s*}}", text)
            if key.strip() not in SUPPORTED_TEMPLATE_PLACEHOLDERS
        }
    )
    if unsupported:
        return _check(
            name,
            "failed",
            f"Unsupported template placeholder(s): {', '.join(unsupported)}",
        )
    return _check(name, "passed", "Template is readable and placeholders are valid.")


def _validate_comfyui_workflow(request: RunRequest) -> dict[str, Any]:
    config = request.comfyui
    if not config or not config.enabled:
        return _check("comfyui_workflow", "skipped", "ComfyUI is disabled.")
    if not config.workflow_api_path:
        return _check("comfyui_workflow", "failed", "workflow_api_path is required.")
    workflow_path = Path(config.workflow_api_path)
    if not workflow_path.exists():
        return _check(
            "comfyui_workflow",
            "failed",
            f"Workflow file not found: {config.workflow_api_path}",
        )
    try:
        workflow = json.loads(workflow_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return _check("comfyui_workflow", "failed", f"Workflow JSON is invalid: {exc}")
    if not isinstance(workflow, dict):
        return _check("comfyui_workflow", "failed", "Workflow JSON must be an object.")
    try:
        placeholder_map = resolve_placeholder_map(config)
        workflow_format = detect_workflow_format(workflow)
        details: dict[str, Any] = {
            "format": workflow_format,
            "placeholder_map_keys": sorted(placeholder_map.keys()),
        }
        if workflow_format == "litegraph":
            points = find_ltx_injection_points(workflow)
            details.update(
                {
                    "ltx_mode": "litegraph_ltx_auto_injection",
                    "node_count": len(workflow.get("nodes") or []),
                    "link_count": len(workflow.get("links") or []),
                    "api_node_count": len(litegraph_to_api_prompt(workflow)),
                }
            )
            details["ltx_injection_points"] = _ltx_injection_points_payload(points)
        else:
            _validate_placeholder_map_targets(workflow, placeholder_map)
        return _check("comfyui_workflow", "passed", "Workflow is readable.", details)
    except Exception as exc:
        return _check("comfyui_workflow", "failed", f"Workflow validation failed: {exc}")


def _validate_grid_image_config(request: RunRequest) -> dict[str, Any]:
    config = request.comfyui
    if not config or not config.enabled:
        return _check("grid_image", "skipped", "ComfyUI is disabled.")
    if not _workflow_requires_grid_image(config.workflow_api_path):
        return _check("grid_image", "skipped", "Workflow does not require a grid image.")
    image = config.grid_image
    if image.effective_mode() == "manual_override":
        path = Path(image.manual_image_path or "")
        if not path.is_file():
            return _check("grid_image", "failed", f"Manual grid image not found: {path}")
        try:
            validated = validate_grid_image(
                path,
                min_dimension=image.min_dimension,
                max_bytes=image.max_bytes,
            )
        except ValueError as exc:
            return _check("grid_image", "failed", str(exc))
        return _check(
            "grid_image",
            "passed",
            "Manual grid image is valid.",
            {"path": str(path), "sha256": validated.sha256},
        )
    if not image.api_key and not os.environ.get(image.api_key_env):
        return _check(
            "grid_image",
            "failed",
            f"Missing environment variable for image API key: {image.api_key_env}",
        )
    return _check(
        "grid_image",
        "passed",
        "Automatic grid image provider is configured.",
        {"provider": image.provider, "model": image.model},
    )


def _workflow_requires_grid_image(path: str | None) -> bool:
    if not path:
        return False
    workflow_path = Path(path)
    if not workflow_path.exists():
        return False
    try:
        workflow = json.loads(workflow_path.read_text(encoding="utf-8"))
        if detect_workflow_format(workflow) != "litegraph":
            return False
        return find_ltx_injection_points(workflow).grid_image_node_id is not None
    except Exception:
        return False


def _ltx_injection_points_payload(points) -> dict[str, Any]:
    payload = {
        "json_node_id": points.json_node_id,
        "seed_node_id": points.seed_node_id,
        "filename_prefix_node_id": points.filename_prefix_node_id,
    }
    if points.grid_image_node_id is not None:
        payload.update(
            {
                "grid_image_node_id": points.grid_image_node_id,
                "grid_image_input": points.grid_image_input,
                "grid_columns": points.grid_columns,
                "grid_rows": points.grid_rows,
            }
        )
    return payload


def _validate_comfyui_endpoint(request: RunRequest) -> dict[str, Any]:
    config = request.comfyui
    if not config or not config.enabled:
        return _check("comfyui_endpoint", "skipped", "ComfyUI is disabled.")
    base_url = config.endpoint.rstrip("/")
    try:
        with httpx.Client(timeout=5.0) as client:
            response = client.get(f"{base_url}/queue")
            response.raise_for_status()
            payload = response.json()
    except Exception as exc:
        return _check(
            "comfyui_endpoint",
            "failed",
            f"Cannot reach ComfyUI /queue: {exc}",
            {"endpoint": config.endpoint},
        )
    queue_running = payload.get("queue_running") or []
    queue_pending = payload.get("queue_pending") or []
    return _check(
        "comfyui_endpoint",
        "passed",
        "ComfyUI /queue is reachable.",
        {
            "endpoint": config.endpoint,
            "queue_running": len(queue_running),
            "queue_pending": len(queue_pending),
        },
    )


def _validate_output_root(request: RunRequest) -> dict[str, Any]:
    if not request.output_root:
        return _check("output_root", "skipped", "No output_root configured; using runtime default.")
    output_root = Path(request.output_root)
    try:
        if output_root.exists() and not output_root.is_dir():
            return _check(
                "output_root",
                "failed",
                f"output_root is not a directory: {request.output_root}",
                {"path": request.output_root},
            )
        output_root.mkdir(parents=True, exist_ok=True)
        probe = output_root / f".relief_story_agent_write_test_{uuid.uuid4().hex}"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
    except Exception as exc:
        return _check(
            "output_root",
            "failed",
            f"Cannot write to output_root: {exc}",
            {"path": request.output_root},
        )
    return _check(
        "output_root",
        "passed",
        "output_root is writable.",
        {"path": request.output_root},
    )


def _validate_execution_policy(request: RunRequest) -> dict[str, Any]:
    planned_stages = _planned_stage_ids(request)
    minimum = len(planned_stages)
    policy = request.execution_policy
    details = {
        "planned_stages": planned_stages,
        "minimum_required_stage_executions": minimum,
        "max_total_stage_executions": policy.max_total_stage_executions,
        "max_stage_executions": dict(policy.max_stage_executions),
    }
    if policy.max_total_stage_executions and policy.max_total_stage_executions < minimum:
        return _check(
            "execution_policy",
            "failed",
            "execution_policy max_total_stage_executions is too low for the planned pipeline.",
            details,
        )
    return _check(
        "execution_policy",
        "passed",
        "execution_policy covers the planned pipeline.",
        details,
    )


def _planned_stage_ids(request: RunRequest) -> list[str]:
    requires_grid = _workflow_requires_grid_image(
        request.comfyui.workflow_api_path if request.comfyui else None
    )
    return stage_ids_for_run(
        requires_grid_asset=requires_grid,
        writes_artifacts=bool(request.output_root or requires_grid),
        comfyui_enabled=bool(request.comfyui and request.comfyui.enabled),
    )


def _validate_placeholder_map_targets(workflow: dict[str, Any], placeholder_map: dict[str, Any]) -> None:
    for key, target in placeholder_map.items():
        node_id = str(target.node)
        node = workflow.get(node_id)
        if not isinstance(node, dict):
            raise ValueError(f"placeholder_map {key!r} references missing node {node_id!r}")
        inputs = node.get("inputs")
        if not isinstance(inputs, dict) or target.input not in inputs:
            raise ValueError(
                f"placeholder_map {key!r} references missing input {target.input!r}"
            )


def _check(
    name: str,
    status: str,
    message: str,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "name": name,
        "status": status,
        "message": message,
        "details": details or {},
    }


def _summarize_checks(checks: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "total": len(checks),
        "passed": sum(1 for check in checks if check["status"] == "passed"),
        "failed": sum(1 for check in checks if check["status"] == "failed"),
        "skipped": sum(1 for check in checks if check["status"] == "skipped"),
    }


def _suggest_actions_for_checks(checks: list[dict[str, Any]]) -> list[dict[str, str]]:
    actions = []
    for check in checks:
        if check["status"] != "failed":
            continue
        name = check["name"]
        if name == "model_environment":
            code = "configure_model_environment"
            label = "Configure model API keys"
        elif name in {"prompt_writer_template", "prompt_audit_template"}:
            code = "fix_prompt_template"
            label = "Fix prompt template"
        elif name == "comfyui_workflow":
            code = "fix_comfyui_workflow"
            label = "Fix ComfyUI workflow or mapping"
        elif name == "comfyui_endpoint":
            code = "start_or_check_comfyui"
            label = "Start or check ComfyUI"
        elif name == "output_root":
            code = "fix_output_root"
            label = "Fix output directory"
        elif name == "execution_policy":
            code = "fix_execution_policy"
            label = "Increase execution policy budget"
        else:
            code = "manual_review_configuration"
            label = "Review configuration"
        actions.append(
            {
                "code": code,
                "label": label,
                "check": name,
                "description": check["message"],
            }
        )
    return actions


def _count_batch_actions(items: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        for action in item.get("suggested_actions") or []:
            code = str(action.get("code") or "")
            if code:
                counts[code] = counts.get(code, 0) + 1
    return counts
