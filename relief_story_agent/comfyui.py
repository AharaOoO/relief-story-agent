from __future__ import annotations

import copy
import hashlib
import json
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.parse import quote, urlencode

import httpx

from .grid_image import compile_four_grid_prompt, deterministic_comfyui_filename, validate_grid_image
from .ltx_workflow import (
    build_ltx_payload_from_storyboard,
    detect_workflow_format,
    find_ltx_injection_points,
    find_ltx_widget_patch_points,
    litegraph_to_api_prompt,
    patch_ltx_litegraph_workflow,
    patch_ltx_widget_workflow,
)
from .models import (
    ComfyUICancellation,
    ComfyUIConnectionRequest,
    ComfyUIOutput,
    ComfyUIRunConfig,
    ComfyUISubmission,
    GridImageAsset,
    PlaceholderTarget,
)


SubmissionUpdateCallback = Callable[[list[ComfyUISubmission]], None]


@dataclass
class PlannedComfyUIWorkflow:
    submission_key: str
    workflow: dict[str, Any]
    workflow_format: str
    replacements: list[dict[str, str]] = field(default_factory=list)
    ltx_payload: dict[str, Any] | None = None


class ComfyUISubmissionUnknown(RuntimeError):
    """Raised when ComfyUI may have accepted a request but no response was received."""


class ComfyUIOutputTimeout(TimeoutError):
    def __init__(self, message: str, diagnostics: dict[str, Any]):
        super().__init__(message)
        self.diagnostics = diagnostics


class ComfyUIWaitCancelled(RuntimeError):
    """Raised when a run cancellation is observed while waiting for outputs."""


def _comfyui_http_client(*, timeout: float) -> httpx.Client:
    return httpx.Client(timeout=timeout, trust_env=False)


def load_workflow(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_placeholder_map(path: str | Path) -> dict[str, PlaceholderTarget]:
    map_path = Path(path)
    if not map_path.exists():
        raise ValueError(f"Placeholder map file not found: {path}")
    try:
        payload = json.loads(map_path.read_text(encoding="utf-8"))
    except UnicodeDecodeError as exc:
        raise ValueError(f"Placeholder map must be UTF-8: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"Placeholder map JSON is invalid: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("Placeholder map JSON must be an object.")
    raw_map = payload.get("placeholder_map", payload)
    if not isinstance(raw_map, dict):
        raise ValueError("Placeholder map JSON field 'placeholder_map' must be an object.")
    return {
        str(key): _normalize_placeholder_target(str(key), value)
        for key, value in raw_map.items()
    }


def resolve_placeholder_map(config: ComfyUIRunConfig) -> dict[str, PlaceholderTarget]:
    resolved: dict[str, PlaceholderTarget] = {}
    if config.placeholder_map_path:
        resolved.update(load_placeholder_map(config.placeholder_map_path))
    for key, value in config.placeholder_map.items():
        resolved[str(key)] = _normalize_placeholder_target(str(key), value)
    return resolved


def analyze_workflow_config(config: ComfyUIRunConfig) -> dict[str, Any]:
    if not config.workflow_api_path:
        raise ValueError("workflow_api_path is required for workflow analysis")
    workflow = load_workflow(config.workflow_api_path)
    workflow_format = detect_workflow_format(workflow)
    if workflow_format == "unknown":
        raise ValueError("Workflow format is unknown; expected ComfyUI API JSON or LiteGraph JSON")

    placeholder_map = resolve_placeholder_map(config)
    warnings: list[str] = []
    base: dict[str, Any] = {
        "workflow_api_path": config.workflow_api_path,
        "workflow_format": workflow_format,
        "placeholder_map_keys": sorted(placeholder_map.keys()),
        "warnings": warnings,
        "suggested_config": {
            "enabled": True,
            "endpoint": config.endpoint,
            "workflow_api_path": config.workflow_api_path,
        },
    }

    if workflow_format == "litegraph":
        try:
            points = find_ltx_injection_points(workflow)
            api_prompt = litegraph_to_api_prompt(workflow)
            if not points.seed_node_id:
                warnings.append("No RandomNoise noise_seed widget was detected; seed injection will be skipped.")
            if not points.filename_prefix_node_id:
                warnings.append("No filename_prefix widget was detected; output prefix injection will be skipped.")
            base.update(
                {
                    "adapter_mode": "litegraph_ltx_auto_injection",
                    "placeholder_map_required": False,
                    "node_count": len(workflow.get("nodes") or []),
                    "link_count": len(workflow.get("links") or []),
                    "api_node_count": len(api_prompt),
                    "grid_asset_required": points.grid_image_node_id is not None,
                    "grid_shape": {
                        "columns": points.grid_columns,
                        "rows": points.grid_rows,
                    },
                    "ltx_injection_points": _ltx_injection_points_payload(points),
                }
            )
            base["suggested_config"]["placeholder_map"] = {}
            base["suggested_config"]["adapter_mode"] = "litegraph_ltx_auto_injection"
            return base
        except ValueError as auto_injection_error:
            try:
                widget_points = find_ltx_widget_patch_points(workflow)
            except ValueError as widget_error:
                raise ValueError(
                    f"{auto_injection_error}; widget patch detection also failed: {widget_error}"
                ) from widget_error
            api_prompt = litegraph_to_api_prompt(workflow)
            if not widget_points.negative_prompt_node_ids:
                warnings.append("No negative prompt widget was detected; negative prompt injection will be skipped.")
            if not widget_points.seed_node_ids:
                warnings.append("No RandomNoise widget was detected; seed injection will be skipped.")
            if not widget_points.filename_prefix_node_ids:
                warnings.append("No SaveVideo/VHS filename prefix widget was detected; output prefix injection will be skipped.")
            base.update(
                {
                    "adapter_mode": "litegraph_ltx_widget_patch",
                    "placeholder_map_required": False,
                    "node_count": len(workflow.get("nodes") or []),
                    "link_count": len(workflow.get("links") or []),
                    "api_node_count": len(api_prompt),
                    "grid_asset_required": bool(widget_points.image_node_ids),
                    "grid_shape": {},
                    "ltx_injection_points": {},
                    "ltx_widget_patch_points": _ltx_widget_points_payload(widget_points),
                }
            )
            base["suggested_config"]["placeholder_map"] = {}
            base["suggested_config"]["adapter_mode"] = "litegraph_ltx_widget_patch"
            return base

    if not placeholder_map:
        warnings.append("API workflow requires a placeholder_map before prompts can be injected.")
    base.update(
        {
            "adapter_mode": "api_placeholder_map",
            "placeholder_map_required": True,
            "node_count": len(workflow),
            "link_count": 0,
            "api_node_count": len(workflow),
            "ltx_injection_points": {},
        }
    )
    base["suggested_config"]["placeholder_map"] = {
        key: target.model_dump()
        for key, target in placeholder_map.items()
    }
    base["suggested_config"]["adapter_mode"] = "api_placeholder_map"
    return base


def connect_comfyui(
    request: ComfyUIConnectionRequest,
    *,
    client: httpx.Client | None = None,
) -> dict[str, Any]:
    endpoint = request.endpoint.rstrip("/")
    checks: list[dict[str, Any]] = []
    queue = {"running": 0, "pending": 0}
    connected = False
    workflow_report: dict[str, Any] = {}

    owns_client = client is None
    active_client = client or _comfyui_http_client(timeout=request.timeout_seconds)
    try:
        try:
            response = active_client.get(f"{endpoint}/queue")
            response.raise_for_status()
            payload = response.json()
            queue_running = payload.get("queue_running") or []
            queue_pending = payload.get("queue_pending") or []
            queue = {"running": len(queue_running), "pending": len(queue_pending)}
            connected = True
            checks.append(
                _diagnostic_check(
                    "comfyui_endpoint",
                    "passed",
                    "ComfyUI /queue is reachable.",
                    {
                        "endpoint": endpoint,
                        "queue_running": queue["running"],
                        "queue_pending": queue["pending"],
                    },
                )
            )
        except Exception as exc:
            checks.append(
                _diagnostic_check(
                    "comfyui_endpoint",
                    "failed",
                    f"Cannot reach ComfyUI /queue: {exc}",
                    {"endpoint": endpoint},
                )
            )

        if request.workflow_api_path:
            workflow_config = ComfyUIRunConfig(
                enabled=True,
                endpoint=endpoint,
                workflow_api_path=request.workflow_api_path,
                placeholder_map_path=request.placeholder_map_path,
                placeholder_map=request.placeholder_map,
            )
            try:
                workflow_report = analyze_workflow_config(workflow_config)
                checks.append(
                    _diagnostic_check(
                        "comfyui_workflow",
                        "passed",
                        "Workflow is readable and injection points were analyzed.",
                        {
                            "workflow_api_path": request.workflow_api_path,
                            "workflow_format": workflow_report.get("workflow_format", ""),
                            "adapter_mode": workflow_report.get("adapter_mode", ""),
                            "grid_asset_required": workflow_report.get("grid_asset_required", False),
                        },
                    )
                )
                if connected:
                    checks.append(
                        _check_runtime_node_types(
                            active_client,
                            endpoint,
                            workflow_config,
                        )
                    )
            except Exception as exc:
                checks.append(
                    _diagnostic_check(
                        "comfyui_workflow",
                        "failed",
                        f"Workflow analysis failed: {exc}",
                        {"workflow_api_path": request.workflow_api_path},
                    )
                )
        else:
            checks.append(
                _diagnostic_check(
                    "comfyui_workflow",
                    "skipped",
                    "No workflow_api_path was provided.",
                )
            )
    finally:
        if owns_client:
            active_client.close()

    ready = connected and all(check["status"] != "failed" for check in checks)
    suggested_config: dict[str, Any] = {
        "enabled": True,
        "endpoint": endpoint,
    }
    if workflow_report:
        suggested_config.update(workflow_report.get("suggested_config") or {})
        suggested_config["endpoint"] = endpoint
    elif request.workflow_api_path:
        suggested_config["workflow_api_path"] = request.workflow_api_path

    return {
        "ready": ready,
        "connected": connected,
        "endpoint": endpoint,
        "queue": queue,
        "workflow": workflow_report,
        "checks": checks,
        "suggested_actions": _suggest_connection_actions(checks),
        "suggested_config": suggested_config,
    }


def discover_workflows(
    search_roots: list[str | Path],
    *,
    endpoint: str = "http://127.0.0.1:8188",
    max_results: int = 25,
    filename_keywords: list[str] | None = None,
    include_unsupported: bool = True,
) -> dict[str, Any]:
    normalized_endpoint = ComfyUIConnectionRequest(endpoint=endpoint).endpoint
    roots = [Path(root) for root in search_roots]
    candidates = _workflow_candidate_paths(roots, filename_keywords or [])
    items = [
        _discover_workflow_item(path, endpoint=normalized_endpoint)
        for path in candidates
    ]
    if not include_unsupported:
        items = [item for item in items if item["status"] != "unsupported"]
    items = sorted(items, key=lambda item: (-int(item["score"]), item["path"]))
    limited_items = items[:max_results]
    recommended = next(
        (item for item in limited_items if item["status"] == "recommended"),
        {},
    )
    return {
        "endpoint": normalized_endpoint,
        "searched_roots": [str(root) for root in roots],
        "total_candidates": len(candidates),
        "returned": len(limited_items),
        "recommended": recommended,
        "items": limited_items,
    }


def _workflow_candidate_paths(roots: list[Path], filename_keywords: list[str]) -> list[Path]:
    normalized_keywords = [keyword.lower() for keyword in filename_keywords if keyword]
    paths: list[Path] = []
    seen: set[str] = set()
    for root in roots:
        if root.is_file() and root.suffix.lower() == ".json":
            candidates = [root]
        elif root.is_dir():
            candidates = root.rglob("*.json")
        else:
            continue
        for candidate in candidates:
            name = candidate.name.lower()
            if normalized_keywords and not any(keyword in name for keyword in normalized_keywords):
                continue
            key = str(candidate.resolve())
            if key in seen:
                continue
            seen.add(key)
            paths.append(candidate)
    return paths


def _discover_workflow_item(path: Path, *, endpoint: str) -> dict[str, Any]:
    base = {
        "path": str(path),
        "filename": path.name,
        "status": "unsupported",
        "score": 0,
        "adapter_mode": "",
        "workflow_format": "",
        "grid_asset_required": False,
        "grid_shape": {},
        "placeholder_map_required": False,
        "ltx_injection_points": {},
        "ltx_widget_patch_points": {},
        "warnings": [],
        "error": "",
        "suggested_config": {},
    }
    try:
        analysis = analyze_workflow_config(
            ComfyUIRunConfig(
                enabled=True,
                endpoint=endpoint,
                workflow_api_path=str(path),
            )
        )
    except Exception as exc:
        base["error"] = str(exc)
        return base

    score = _workflow_discovery_score(analysis)
    status = "recommended" if score >= 80 else "needs_placeholder_map"
    return {
        **base,
        "status": status,
        "score": score,
        "adapter_mode": str(analysis.get("adapter_mode") or ""),
        "workflow_format": str(analysis.get("workflow_format") or ""),
        "grid_asset_required": bool(analysis.get("grid_asset_required")),
        "grid_shape": analysis.get("grid_shape") or {},
        "placeholder_map_required": bool(analysis.get("placeholder_map_required")),
        "ltx_injection_points": analysis.get("ltx_injection_points") or {},
        "ltx_widget_patch_points": analysis.get("ltx_widget_patch_points") or {},
        "warnings": analysis.get("warnings") or [],
        "suggested_config": analysis.get("suggested_config") or {},
    }


def _workflow_discovery_score(analysis: dict[str, Any]) -> int:
    if analysis.get("adapter_mode") == "litegraph_ltx_auto_injection":
        score = 80
        grid_shape = analysis.get("grid_shape") or {}
        if grid_shape.get("columns") == 2 and grid_shape.get("rows") == 2:
            score += 15
        if analysis.get("grid_asset_required"):
            score += 5
        return score
    if analysis.get("adapter_mode") == "litegraph_ltx_widget_patch":
        points = analysis.get("ltx_widget_patch_points") or {}
        score = 75
        if points.get("positive_prompt_node_ids"):
            score += 10
        if points.get("negative_prompt_node_ids"):
            score += 5
        if points.get("seed_node_ids"):
            score += 3
        if points.get("filename_prefix_node_ids"):
            score += 3
        if points.get("image_node_ids"):
            score += 4
        return score
    if analysis.get("adapter_mode") == "api_placeholder_map":
        return 50 if analysis.get("placeholder_map_required") else 60
    return 0


def apply_placeholder_map(
    workflow: dict[str, Any],
    shot: dict[str, Any],
    placeholder_map: dict[str, dict[str, str] | PlaceholderTarget],
) -> dict[str, Any]:
    patched = copy.deepcopy(workflow)
    for key, target in placeholder_map.items():
        target_obj = _normalize_placeholder_target(str(key), target)
        try:
            value = _read_source(shot, target_obj.source)
        except KeyError as exc:
            raise ValueError(
                f"placeholder_map {key!r} source {target_obj.source!r} was not found in shot"
            ) from exc
        try:
            patched[target_obj.node]["inputs"][target_obj.input] = value
        except KeyError as exc:
            raise ValueError(
                f"placeholder_map {key!r} target node {target_obj.node!r} input "
                f"{target_obj.input!r} was not found in workflow"
            ) from exc
    return patched


def upload_grid_image(
    endpoint: str,
    image_path: str | Path,
    *,
    destination_name: str,
    client: httpx.Client | None = None,
) -> str:
    path = Path(image_path)
    owns_client = client is None
    active_client = client or _comfyui_http_client(timeout=120.0)
    try:
        with path.open("rb") as handle:
            response = active_client.post(
                endpoint.rstrip("/") + "/upload/image",
                data={"type": "input", "overwrite": "true"},
                files={"image": (destination_name, handle, _mime_for_path(path))},
            )
        response.raise_for_status()
        payload = response.json()
        name = str(payload.get("name") or destination_name)
        subfolder = str(payload.get("subfolder") or "").strip("/\\")
        return f"{subfolder}/{name}" if subfolder else name
    finally:
        if owns_client:
            active_client.close()


def plan_storyboard_workflows(
    config: ComfyUIRunConfig,
    storyboard: list[dict[str, Any]],
    run_id: str,
    *,
    duration_seconds: int = 90,
    grid_image_asset: GridImageAsset | None = None,
    allow_unuploaded_grid_image: bool = False,
    object_info: dict[str, Any] | None = None,
) -> list[PlannedComfyUIWorkflow]:
    if not config.workflow_api_path:
        raise ValueError("workflow_api_path is required when ComfyUI is enabled")
    workflow = load_workflow(config.workflow_api_path)
    workflow_format = detect_workflow_format(workflow)
    planned_workflows: list[PlannedComfyUIWorkflow] = []
    if workflow_format == "litegraph":
        ltx_payload = build_ltx_payload_from_storyboard(storyboard, duration_seconds=duration_seconds)
        try:
            points = find_ltx_injection_points(workflow)
            grid_image_filename = None
            replacements = []
            if points.grid_image_node_id:
                if not grid_image_asset:
                    raise ValueError("LTX grid workflow requires a grid image asset")
                if grid_image_asset.upload_status != "accepted" and not allow_unuploaded_grid_image:
                    raise ValueError("LTX grid workflow requires an accepted uploaded grid image asset")
                grid_image_filename = grid_image_asset.comfyui_filename
                replacements.append(
                    {
                        "key": "grid_image",
                        "node": points.grid_image_node_id,
                        "input": points.grid_image_input,
                        "source": "grid_image_asset.comfyui_filename",
                        "value_preview": grid_image_asset.comfyui_filename,
                    }
                )
            patched = patch_ltx_litegraph_workflow(
                workflow,
                ltx_payload=ltx_payload,
                seed=_read_storyboard_seed(storyboard),
                filename_prefix=run_id,
                grid_image_filename=grid_image_filename,
                object_info=object_info,
            )
            replacements.append(
                {
                    "key": "ltx_payload",
                    "node": points.json_node_id,
                    "input": "text",
                    "source": "storyboard",
                    "value_preview": _preview_value(ltx_payload),
                }
            )
            if points.seed_node_id:
                replacements.append(
                    {
                        "key": "seed",
                        "node": points.seed_node_id,
                        "input": "noise_seed",
                        "source": "storyboard.comfyui_inputs.seed",
                        "value_preview": _preview_value(_read_storyboard_seed(storyboard)),
                    }
                )
            if points.filename_prefix_node_id:
                replacements.append(
                    {
                        "key": "filename_prefix",
                        "node": points.filename_prefix_node_id,
                        "input": "filename_prefix",
                        "source": "run_id",
                        "value_preview": run_id,
                    }
                )
            planned_workflows.append(
                PlannedComfyUIWorkflow(
                    submission_key="ltx",
                    workflow=patched,
                    workflow_format=workflow_format,
                    replacements=replacements,
                    ltx_payload=ltx_payload,
                )
            )
            return planned_workflows
        except ValueError as auto_injection_error:
            try:
                widget_points = find_ltx_widget_patch_points(workflow)
            except ValueError as widget_error:
                raise ValueError(
                    f"{auto_injection_error}; widget patch detection also failed: {widget_error}"
                ) from widget_error
            image_filename = None
            replacements = []
            if widget_points.image_node_ids:
                if not grid_image_asset:
                    raise ValueError("LTX widget workflow requires a grid image asset")
                if grid_image_asset.upload_status != "accepted" and not allow_unuploaded_grid_image:
                    raise ValueError("LTX widget workflow requires an accepted uploaded grid image asset")
                image_filename = grid_image_asset.comfyui_filename
                replacements.extend(
                    {
                        "key": "image",
                        "node": node_id,
                        "input": "image",
                        "source": "grid_image_asset.comfyui_filename",
                        "value_preview": grid_image_asset.comfyui_filename,
                    }
                    for node_id in widget_points.image_node_ids
                )
            patched = patch_ltx_widget_workflow(
                workflow,
                ltx_payload=ltx_payload,
                seed=_read_storyboard_seed(storyboard),
                filename_prefix=run_id,
                image_filename=image_filename,
                object_info=object_info,
            )
            replacements.extend(
                {
                    "key": "positive_prompt",
                    "node": node_id,
                    "input": "text",
                    "source": "storyboard.prompt",
                    "value_preview": _preview_value(ltx_payload.get("prompt", "")),
                }
                for node_id in widget_points.positive_prompt_node_ids
            )
            replacements.extend(
                {
                    "key": "negative_prompt",
                    "node": node_id,
                    "input": "text",
                    "source": "storyboard.negative_prompt",
                    "value_preview": _preview_value(ltx_payload.get("negative_prompt", "")),
                }
                for node_id in widget_points.negative_prompt_node_ids
            )
            replacements.extend(
                {
                    "key": "seed",
                    "node": node_id,
                    "input": "noise_seed",
                    "source": "storyboard.comfyui_inputs.seed",
                    "value_preview": _preview_value(_read_storyboard_seed(storyboard)),
                }
                for node_id in widget_points.seed_node_ids
            )
            replacements.extend(
                {
                    "key": "filename_prefix",
                    "node": node_id,
                    "input": "filename_prefix",
                    "source": "run_id",
                    "value_preview": run_id,
                }
                for node_id in widget_points.filename_prefix_node_ids
            )
            planned_workflows.append(
                PlannedComfyUIWorkflow(
                    submission_key="ltx_widget",
                    workflow=patched,
                    workflow_format=workflow_format,
                    replacements=replacements,
                    ltx_payload=ltx_payload,
                )
            )
            return planned_workflows

    placeholder_map = resolve_placeholder_map(config)
    for index, shot in enumerate(storyboard, start=1):
        patched = apply_placeholder_map(workflow, shot, placeholder_map)
        planned_workflows.append(
            PlannedComfyUIWorkflow(
                submission_key=f"shot:{index}",
                workflow=patched,
                workflow_format=workflow_format,
                replacements=_placeholder_replacement_preview(shot, placeholder_map),
            )
        )
    return planned_workflows


def preview_storyboard_submission(
    config: ComfyUIRunConfig,
    storyboard: list[dict[str, Any]],
    run_id: str,
    *,
    duration_seconds: int = 90,
    include_workflow: bool = False,
    grid_image_asset: GridImageAsset | None = None,
    allow_unuploaded_grid_image: bool = False,
    object_info: dict[str, Any] | None = None,
) -> dict[str, Any]:
    image_resolution = ""
    if grid_image_asset is None and _workflow_requires_grid_image(config):
        grid_image_asset, image_resolution = _preview_grid_image_asset(
            config,
            storyboard,
            run_id,
        )
        allow_unuploaded_grid_image = True
    planned = plan_storyboard_workflows(
        config,
        storyboard,
        run_id,
        duration_seconds=duration_seconds,
        grid_image_asset=grid_image_asset,
        allow_unuploaded_grid_image=allow_unuploaded_grid_image,
        object_info=object_info,
    )
    workflow_format = planned[0].workflow_format if planned else "unknown"
    items = []
    for item in planned:
        fingerprint = _content_fingerprint(item.workflow)
        submission = _new_submission(run_id, item.submission_key, fingerprint)
        current = {
            "submission_key": item.submission_key,
            "prompt_id": submission.prompt_id,
            "client_id": submission.client_id,
            "content_fingerprint": fingerprint,
            "workflow_format": item.workflow_format,
            "node_count": len(item.workflow),
            "replacements": item.replacements,
        }
        if item.ltx_payload is not None:
            current["ltx_payload"] = item.ltx_payload
        if image_resolution:
            for replacement in current["replacements"]:
                if replacement.get("key") == "grid_image":
                    replacement["resolution"] = image_resolution
        if include_workflow:
            current["workflow"] = item.workflow
        items.append(current)
    return {
        "will_enqueue": False,
        "run_id": run_id,
        "workflow_api_path": config.workflow_api_path or "",
        "workflow_format": workflow_format,
        "planned_count": len(items),
        "items": items,
    }


def _workflow_requires_grid_image(config: ComfyUIRunConfig) -> bool:
    if not config.workflow_api_path:
        return False
    workflow = load_workflow(config.workflow_api_path)
    if detect_workflow_format(workflow) != "litegraph":
        return False
    try:
        return find_ltx_injection_points(workflow).grid_image_node_id is not None
    except ValueError:
        return bool(find_ltx_widget_patch_points(workflow).image_node_ids)


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


def _ltx_widget_points_payload(points) -> dict[str, Any]:
    return {
        "positive_prompt_node_ids": list(points.positive_prompt_node_ids),
        "negative_prompt_node_ids": list(points.negative_prompt_node_ids),
        "seed_node_ids": list(points.seed_node_ids),
        "filename_prefix_node_ids": list(points.filename_prefix_node_ids),
        "image_node_ids": list(points.image_node_ids),
    }


def _check_runtime_node_types(
    client: httpx.Client,
    endpoint: str,
    config: ComfyUIRunConfig,
) -> dict[str, Any]:
    try:
        workflow = load_workflow(config.workflow_api_path or "")
        workflow_format = detect_workflow_format(workflow)
        api_prompt = litegraph_to_api_prompt(workflow) if workflow_format == "litegraph" else workflow
        required = sorted(
            {
                str(node.get("class_type") or "")
                for node in api_prompt.values()
                if isinstance(node, dict) and node.get("class_type")
            }
        )
        response = client.get(f"{endpoint.rstrip('/')}/object_info")
        response.raise_for_status()
        object_info = response.json()
        available = set(object_info.keys()) if isinstance(object_info, dict) else set()
    except Exception as exc:
        return _diagnostic_check(
            "comfyui_node_types",
            "failed",
            f"Cannot verify ComfyUI runtime node types: {exc}",
            {"workflow_api_path": config.workflow_api_path or ""},
        )

    missing = [node_type for node_type in required if node_type not in available]
    details = {
        "required_node_type_count": len(required),
        "missing_node_types": missing,
    }
    if missing:
        return _diagnostic_check(
            "comfyui_node_types",
            "failed",
            "ComfyUI is missing node types required by the workflow.",
            details,
        )
    return _diagnostic_check(
        "comfyui_node_types",
        "passed",
        "ComfyUI runtime exposes every workflow node type.",
        details,
    )


def fetch_workflow_runtime_object_info(
    client: httpx.Client,
    endpoint: str,
    config: ComfyUIRunConfig,
) -> dict[str, Any] | None:
    if not config.workflow_api_path:
        return None
    workflow = load_workflow(config.workflow_api_path)
    if detect_workflow_format(workflow) != "litegraph":
        return None
    response = client.get(f"{endpoint.rstrip('/')}/object_info")
    response.raise_for_status()
    payload = response.json()
    return payload if isinstance(payload, dict) else {}


def _diagnostic_check(
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


def _suggest_connection_actions(checks: list[dict[str, Any]]) -> list[dict[str, str]]:
    actions: list[dict[str, str]] = []
    for check in checks:
        if check.get("status") != "failed":
            continue
        name = str(check.get("name") or "")
        if name == "comfyui_endpoint":
            code = "start_or_check_comfyui"
            label = "Start or check ComfyUI"
        elif name == "comfyui_workflow":
            code = "fix_comfyui_workflow"
            label = "Fix ComfyUI workflow"
        elif name == "comfyui_node_types":
            code = "install_or_enable_comfyui_nodes"
            label = "Install or enable ComfyUI custom nodes"
        else:
            code = "manual_review_comfyui_connection"
            label = "Review ComfyUI connection"
        actions.append(
            {
                "code": code,
                "label": label,
                "check": name,
                "description": str(check.get("message") or ""),
            }
        )
    return actions


def _preview_grid_image_asset(
    config: ComfyUIRunConfig,
    storyboard: list[dict[str, Any]],
    run_id: str,
) -> tuple[GridImageAsset, str]:
    image_config = config.grid_image
    compile_four_grid_prompt(storyboard, max_chars=image_config.prompt_max_chars)
    if image_config.effective_mode() == "manual_override":
        validated = validate_grid_image(
            image_config.manual_image_path or "",
            min_dimension=image_config.min_dimension,
            max_bytes=image_config.max_bytes,
        )
        return (
            GridImageAsset(
                source="manual",
                local_path=str(validated.path),
                sha256=validated.sha256,
                mime_type=validated.mime_type,
                width=validated.width,
                height=validated.height,
                byte_size=validated.byte_size,
                comfyui_filename=deterministic_comfyui_filename(
                    run_id,
                    validated.sha256,
                    validated.mime_type,
                ),
                upload_status="pending",
            ),
            "exact_manual_asset",
        )
    return (
        GridImageAsset(
            source="generated",
            local_path="",
            sha256="0" * 64,
            mime_type="image/png",
            width=1,
            height=1,
            byte_size=1,
            comfyui_filename="pending_generation",
            upload_status="pending",
        ),
        "pending_generation",
    )


def enqueue_workflow(
    endpoint: str,
    workflow: dict[str, Any],
    *,
    prompt_id: str | None = None,
    client_id: str | None = None,
    client: httpx.Client | None = None,
) -> str:
    payload: dict[str, Any] = {"prompt": workflow}
    if prompt_id:
        payload["prompt_id"] = prompt_id
    if client_id:
        payload["client_id"] = client_id
    if client is None:
        with _comfyui_http_client(timeout=30.0) as active_client:
            response = active_client.post(endpoint.rstrip("/") + "/prompt", json=payload)
    else:
        response = client.post(endpoint.rstrip("/") + "/prompt", json=payload)
    response.raise_for_status()
    data = response.json()
    return str(data.get("prompt_id") or data.get("number") or "")


def submit_storyboard(
    config: ComfyUIRunConfig,
    storyboard: list[dict[str, Any]],
    run_id: str,
    *,
    duration_seconds: int = 90,
    existing_submissions: list[ComfyUISubmission] | None = None,
    on_update: SubmissionUpdateCallback | None = None,
    client: httpx.Client | None = None,
    grid_image_asset: GridImageAsset | None = None,
    object_info: dict[str, Any] | None = None,
) -> list[ComfyUISubmission]:
    existing = existing_submissions or []
    submissions: list[ComfyUISubmission] = []
    owns_client = client is None
    active_client = client or _comfyui_http_client(timeout=30.0)
    try:
        if object_info is None:
            object_info = fetch_workflow_runtime_object_info(active_client, config.endpoint, config)
        planned_workflows = plan_storyboard_workflows(
            config,
            storyboard,
            run_id,
            duration_seconds=duration_seconds,
            grid_image_asset=grid_image_asset,
            allow_unuploaded_grid_image=False,
            object_info=object_info,
        )

        for planned in planned_workflows:
            fingerprint = _content_fingerprint(planned.workflow)
            previous = next(
                (
                    item
                    for item in existing
                    if item.submission_key == planned.submission_key
                    and item.content_fingerprint == fingerprint
                ),
                None,
            )
            submission = previous.model_copy(deep=True) if previous else _new_submission(
                run_id,
                planned.submission_key,
                fingerprint,
            )
            submissions.append(submission)
            if submission.status == "accepted":
                continue
            if previous and submission.status in {"prepared", "unknown"}:
                found_prompt_id = _find_existing_submission(
                    active_client,
                    config.endpoint,
                    submission,
                )
                if found_prompt_id:
                    _update_submission(submission, status="accepted", prompt_id=found_prompt_id)
                    _notify(on_update, submissions)
                    continue

            _update_submission(submission, status="prepared", error="")
            _notify(on_update, submissions)
            try:
                returned_prompt_id = enqueue_workflow(
                    config.endpoint,
                    planned.workflow,
                    prompt_id=submission.prompt_id,
                    client_id=submission.client_id,
                    client=active_client,
                )
            except httpx.TransportError as exc:
                _update_submission(submission, status="unknown", error=str(exc))
                _notify(on_update, submissions)
                raise ComfyUISubmissionUnknown(
                    f"ComfyUI submission status is unknown for {submission.submission_key}: {exc}"
                ) from exc
            except Exception as exc:
                _update_submission(submission, status="rejected", error=str(exc))
                _notify(on_update, submissions)
                raise
            _update_submission(
                submission,
                status="accepted",
                prompt_id=returned_prompt_id or submission.prompt_id,
                error="",
            )
            _notify(on_update, submissions)
    finally:
        if owns_client:
            active_client.close()
    return submissions


def enqueue_storyboard(
    config: ComfyUIRunConfig,
    storyboard: list[dict[str, Any]],
    run_id: str,
    *,
    duration_seconds: int = 90,
    grid_image_asset: GridImageAsset | None = None,
) -> list[str]:
    submissions = submit_storyboard(
        config,
        storyboard,
        run_id,
        duration_seconds=duration_seconds,
        grid_image_asset=grid_image_asset,
    )
    return [item.prompt_id for item in submissions if item.status == "accepted"]


def collect_prompt_outputs(
    config: ComfyUIRunConfig,
    prompt_ids: list[str],
    *,
    client: httpx.Client | None = None,
) -> list[ComfyUIOutput]:
    base_url = config.endpoint.rstrip("/")
    owns_client = client is None
    active_client = client or _comfyui_http_client(timeout=30.0)
    outputs: list[ComfyUIOutput] = []
    seen: set[tuple[str, str, str, str, str]] = set()
    try:
        for prompt_id in prompt_ids:
            response = active_client.get(f"{base_url}/history/{prompt_id}")
            if response.status_code == 404:
                response = active_client.get(f"{base_url}/history")
            response.raise_for_status()
            for output in _parse_history_outputs(base_url, prompt_id, response.json()):
                key = (
                    output.prompt_id,
                    output.node_id,
                    output.filename,
                    output.subfolder,
                    output.type,
                )
                if key in seen:
                    continue
                seen.add(key)
                outputs.append(output)
    finally:
        if owns_client:
            active_client.close()
    return outputs


def cancel_prompt_jobs(
    config: ComfyUIRunConfig,
    prompt_ids: list[str],
    *,
    client: httpx.Client | None = None,
) -> list[ComfyUICancellation]:
    base_url = config.endpoint.rstrip("/")
    owns_client = client is None
    active_client = client or _comfyui_http_client(timeout=30.0)
    results: list[ComfyUICancellation] = []
    try:
        for prompt_id in prompt_ids:
            encoded_prompt_id = quote(prompt_id, safe="")
            try:
                response = active_client.post(
                    f"{base_url}/api/jobs/{encoded_prompt_id}/cancel"
                )
            except httpx.HTTPError as exc:
                results.append(
                    ComfyUICancellation(prompt_id=prompt_id, error=str(exc))
                )
                continue
            if 200 <= response.status_code < 300:
                try:
                    payload = response.json()
                except ValueError:
                    payload = {}
                cancelled = bool(payload.get("cancelled")) if isinstance(payload, dict) else False
                results.append(
                    ComfyUICancellation(
                        prompt_id=prompt_id,
                        strategy="job_api",
                        cancelled=cancelled,
                        remote_status="cancelled" if cancelled else "not_found_or_finished",
                    )
                )
                continue
            if response.status_code in {404, 405}:
                try:
                    legacy_response = active_client.post(
                        f"{base_url}/queue",
                        json={"delete": [prompt_id]},
                    )
                except httpx.HTTPError as exc:
                    results.append(
                        ComfyUICancellation(
                            prompt_id=prompt_id,
                            error=str(exc),
                        )
                    )
                    continue
                if 200 <= legacy_response.status_code < 300:
                    results.append(
                        ComfyUICancellation(
                            prompt_id=prompt_id,
                            strategy="legacy_queue",
                            cancelled=True,
                            remote_status="queued_delete_requested",
                        )
                    )
                    continue
                results.append(
                    ComfyUICancellation(
                        prompt_id=prompt_id,
                        remote_status=f"http_{legacy_response.status_code}",
                        error=(
                            "ComfyUI legacy queue deletion returned "
                            f"HTTP {legacy_response.status_code}"
                        ),
                    )
                )
                continue
            results.append(
                ComfyUICancellation(
                    prompt_id=prompt_id,
                    remote_status=f"http_{response.status_code}",
                    error=f"ComfyUI job cancellation returned HTTP {response.status_code}",
                )
            )
    finally:
        if owns_client:
            active_client.close()
    return results


def download_prompt_outputs(
    outputs: list[ComfyUIOutput],
    artifact_dir: str | Path,
    *,
    client: httpx.Client | None = None,
) -> list[ComfyUIOutput]:
    output_dir = Path(artifact_dir) / "comfyui_outputs"
    output_dir.mkdir(parents=True, exist_ok=True)
    owns_client = client is None
    active_client = client or _comfyui_http_client(timeout=120.0)
    downloaded: list[ComfyUIOutput] = []
    reserved: set[Path] = set()
    try:
        for output in outputs:
            if not output.url:
                downloaded.append(output)
                continue
            target = _unique_output_path(output_dir, _safe_output_filename(output), reserved)
            with active_client.stream("GET", output.url) as response:
                response.raise_for_status()
                with target.open("wb") as handle:
                    for chunk in response.iter_bytes():
                        handle.write(chunk)
            downloaded.append(output.model_copy(update={"local_path": str(target)}))
    finally:
        if owns_client:
            active_client.close()
    return downloaded


def wait_for_prompt_outputs(
    config: ComfyUIRunConfig,
    prompt_ids: list[str],
    *,
    timeout_seconds: float | None = None,
    poll_interval_seconds: float | None = None,
    client: httpx.Client | None = None,
    sleep_fn: Callable[[float], None] = time.sleep,
    should_cancel: Callable[[], bool] | None = None,
    cancel_check_interval_seconds: float = 1.0,
) -> list[ComfyUIOutput]:
    timeout = config.output_timeout_seconds if timeout_seconds is None else timeout_seconds
    interval = config.output_poll_interval_seconds if poll_interval_seconds is None else poll_interval_seconds
    deadline = time.monotonic() + max(timeout, 0)
    owns_client = client is None
    active_client = client or _comfyui_http_client(timeout=30.0)
    try:
        while True:
            _raise_if_wait_cancelled(should_cancel)
            outputs = collect_prompt_outputs(config, prompt_ids, client=active_client)
            if _all_prompts_have_outputs(outputs, prompt_ids):
                return outputs
            _raise_if_wait_cancelled(should_cancel)
            now = time.monotonic()
            if now >= deadline:
                diagnostics = collect_prompt_diagnostics(
                    config,
                    prompt_ids,
                    client=active_client,
                )
                raise ComfyUIOutputTimeout(
                    f"Timed out waiting for ComfyUI outputs: {', '.join(prompt_ids)}",
                    diagnostics,
                )
            sleep_for = min(max(interval, 0), max(deadline - now, 0))
            if sleep_for <= 0:
                sleep_fn(0)
                continue
            remaining = sleep_for
            check_interval = max(cancel_check_interval_seconds, 0.01)
            while remaining > 0:
                _raise_if_wait_cancelled(should_cancel)
                sleep_slice = min(remaining, check_interval, 1.0)
                sleep_fn(sleep_slice)
                remaining -= sleep_slice
    finally:
        if owns_client:
            active_client.close()


def collect_prompt_diagnostics(
    config: ComfyUIRunConfig,
    prompt_ids: list[str],
    *,
    client: httpx.Client | None = None,
) -> dict[str, Any]:
    base_url = config.endpoint.rstrip("/")
    owns_client = client is None
    active_client = client or _comfyui_http_client(timeout=30.0)
    try:
        return {
            "prompt_ids": list(prompt_ids),
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "queue": _fetch_json_or_error(active_client, f"{base_url}/queue"),
            "history": {
                prompt_id: _fetch_json_or_error(active_client, f"{base_url}/history/{prompt_id}")
                for prompt_id in prompt_ids
            },
        }
    finally:
        if owns_client:
            active_client.close()


def _raise_if_wait_cancelled(should_cancel: Callable[[], bool] | None) -> None:
    if should_cancel and should_cancel():
        raise ComfyUIWaitCancelled("ComfyUI output wait cancelled")


def _parse_history_outputs(
    base_url: str,
    prompt_id: str,
    payload: dict[str, Any],
) -> list[ComfyUIOutput]:
    record = _history_record_for_prompt(payload, prompt_id)
    node_outputs = record.get("outputs") if isinstance(record, dict) else None
    if not isinstance(node_outputs, dict):
        return []

    outputs: list[ComfyUIOutput] = []
    for node_id, node_payload in node_outputs.items():
        if not isinstance(node_payload, dict):
            continue
        for category in ("images", "gifs", "videos", "audio"):
            for item in node_payload.get(category) or []:
                if not isinstance(item, dict):
                    continue
                filename = str(item.get("filename") or "")
                if not filename:
                    continue
                subfolder = str(item.get("subfolder") or "")
                output_type = str(item.get("type") or "output")
                outputs.append(
                    ComfyUIOutput(
                        prompt_id=prompt_id,
                        node_id=str(node_id),
                        filename=filename,
                        subfolder=subfolder,
                        type=output_type,
                        media_type=_infer_media_type(category, filename),
                        url=_build_view_url(base_url, filename, subfolder, output_type),
                    )
                )
    return outputs


def _all_prompts_have_outputs(outputs: list[ComfyUIOutput], prompt_ids: list[str]) -> bool:
    if not prompt_ids:
        return True
    found = {output.prompt_id for output in outputs}
    return set(prompt_ids).issubset(found)


def _fetch_json_or_error(client: httpx.Client, url: str) -> dict[str, Any]:
    try:
        response = client.get(url)
        response.raise_for_status()
        payload = response.json()
        return payload if isinstance(payload, dict) else {"body": payload}
    except Exception as exc:
        return {"error": str(exc)}


def _history_record_for_prompt(payload: dict[str, Any], prompt_id: str) -> dict[str, Any]:
    direct = payload.get(prompt_id)
    if isinstance(direct, dict):
        return direct
    if "outputs" in payload:
        return payload
    return {}


def _infer_media_type(category: str, filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix in {".mp4", ".webm", ".mov", ".gif"}:
        return "video"
    if suffix in {".wav", ".mp3", ".flac", ".ogg"}:
        return "audio"
    if suffix in {".png", ".jpg", ".jpeg", ".webp"}:
        return "image"
    if category in {"gifs", "videos"}:
        return "video"
    if category == "audio":
        return "audio"
    if category == "images":
        return "image"
    return "other"


def _build_view_url(base_url: str, filename: str, subfolder: str, output_type: str) -> str:
    params = {"filename": filename}
    if subfolder:
        params["subfolder"] = subfolder
    params["type"] = output_type
    return f"{base_url}/view?{urlencode(params)}"


def _safe_output_filename(output: ComfyUIOutput) -> str:
    basename = Path(output.filename).name or "output"
    raw = "_".join(part for part in (output.prompt_id, output.node_id, basename) if part)
    safe = "".join(char if char.isalnum() or char in "._-" else "_" for char in raw)
    return safe or "output"


def _unique_output_path(output_dir: Path, filename: str, reserved: set[Path]) -> Path:
    target = output_dir / filename
    if target not in reserved and not target.exists():
        reserved.add(target)
        return target
    stem = target.stem
    suffix = target.suffix
    index = 2
    while True:
        candidate = output_dir / f"{stem}_{index}{suffix}"
        if candidate not in reserved and not candidate.exists():
            reserved.add(candidate)
            return candidate
        index += 1


def _new_submission(
    run_id: str,
    submission_key: str,
    content_fingerprint: str,
) -> ComfyUISubmission:
    identity = f"relief-story-agent:{run_id}:{submission_key}:{content_fingerprint}"
    prompt_id = str(uuid.uuid5(uuid.NAMESPACE_URL, identity))
    client_id = f"{run_id}:{submission_key}:{content_fingerprint[:12]}"
    return ComfyUISubmission(
        submission_key=submission_key,
        content_fingerprint=content_fingerprint,
        prompt_id=prompt_id,
        client_id=client_id,
    )


def _content_fingerprint(workflow: dict[str, Any]) -> str:
    canonical = json.dumps(
        workflow,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _find_existing_submission(
    client: httpx.Client,
    endpoint: str,
    submission: ComfyUISubmission,
) -> str | None:
    base_url = endpoint.rstrip("/")
    job_response = client.get(f"{base_url}/api/jobs/{submission.prompt_id}")
    if job_response.status_code == 200:
        data = job_response.json()
        return str(data.get("id") or data.get("prompt_id") or submission.prompt_id)
    if job_response.status_code != 404:
        job_response.raise_for_status()

    queue_response = client.get(f"{base_url}/queue")
    queue_response.raise_for_status()
    queued_prompt_id = _find_in_queue(queue_response.json(), submission)
    if queued_prompt_id:
        return queued_prompt_id

    history_response = client.get(f"{base_url}/history")
    history_response.raise_for_status()
    return _find_in_history(history_response.json(), submission)


def _find_in_queue(payload: dict[str, Any], submission: ComfyUISubmission) -> str | None:
    for queue_name in ("queue_running", "queue_pending"):
        for item in payload.get(queue_name) or []:
            prompt_id = str(item[1]) if len(item) > 1 else ""
            extra_data = item[3] if len(item) > 3 and isinstance(item[3], dict) else {}
            if prompt_id == submission.prompt_id or extra_data.get("client_id") == submission.client_id:
                return prompt_id or submission.prompt_id
    return None


def _find_in_history(payload: dict[str, Any], submission: ComfyUISubmission) -> str | None:
    for history_prompt_id, record in payload.items():
        if str(history_prompt_id) == submission.prompt_id:
            return submission.prompt_id
        prompt_data = record.get("prompt") if isinstance(record, dict) else None
        extra_data = (
            prompt_data[3]
            if isinstance(prompt_data, list)
            and len(prompt_data) > 3
            and isinstance(prompt_data[3], dict)
            else {}
        )
        if extra_data.get("client_id") == submission.client_id:
            return str(history_prompt_id)
    return None


def _update_submission(
    submission: ComfyUISubmission,
    *,
    status: str,
    prompt_id: str | None = None,
    error: str | None = None,
) -> None:
    submission.status = status  # type: ignore[assignment]
    if prompt_id is not None:
        submission.prompt_id = prompt_id
    if error is not None:
        submission.error = error
    submission.updated_at = datetime.now(timezone.utc).isoformat()


def _notify(
    callback: SubmissionUpdateCallback | None,
    submissions: list[ComfyUISubmission],
) -> None:
    if callback:
        callback([item.model_copy(deep=True) for item in submissions])


def _read_source(shot: dict[str, Any], source: str) -> Any:
    current: Any = shot
    for part in source.split("."):
        if isinstance(current, dict):
            current = current[part]
        else:
            raise KeyError(source)
    return current


def _placeholder_replacement_preview(
    shot: dict[str, Any],
    placeholder_map: dict[str, PlaceholderTarget],
) -> list[dict[str, str]]:
    replacements: list[dict[str, str]] = []
    for key, target in placeholder_map.items():
        replacements.append(
            {
                "key": key,
                "node": target.node,
                "input": target.input,
                "source": target.source,
                "value_preview": _preview_value(_read_source(shot, target.source)),
            }
        )
    return replacements


def _preview_value(value: Any, *, max_chars: int = 160) -> str:
    if isinstance(value, (dict, list)):
        text = json.dumps(value, ensure_ascii=False, sort_keys=True)
    elif value is None:
        text = ""
    else:
        text = str(value)
    if len(text) > max_chars:
        return text[:max_chars].rstrip() + "..."
    return text


def _mime_for_path(path: Path) -> str:
    return {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
    }.get(path.suffix.lower(), "application/octet-stream")


def _normalize_placeholder_target(key: str, target: dict[str, str] | PlaceholderTarget) -> PlaceholderTarget:
    try:
        return target if isinstance(target, PlaceholderTarget) else PlaceholderTarget(**target)
    except Exception as exc:
        raise ValueError(f"placeholder_map {key!r} is invalid: {exc}") from exc


def _read_storyboard_seed(storyboard: list[dict[str, Any]]) -> int | None:
    for shot in storyboard:
        comfyui_inputs = shot.get("comfyui_inputs") or {}
        if "seed" in comfyui_inputs:
            return int(comfyui_inputs["seed"])
    return None
