from __future__ import annotations

import argparse
import json
import shutil
from contextlib import nullcontext
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

import httpx
from pydantic import BaseModel, Field, field_validator

from .comfyui_endpoint import normalize_comfyui_endpoint
from .comfyui import (
    analyze_workflow_config,
    fetch_workflow_runtime_object_info,
    preview_storyboard_submission,
    submit_storyboard,
    upload_grid_image,
)
from .grid_image import deterministic_comfyui_filename, validate_grid_image
from .models import ComfyUIRunConfig, GridImageAsset, GridImageConfig
from .resource_limits import ExecutionResourceLimits


class SmokeCheck(BaseModel):
    id: str
    status: Literal["pass", "warn", "fail"]
    severity: Literal["info", "warning", "error"] = "info"
    message: str
    evidence: dict[str, Any] = Field(default_factory=dict)
    suggested_action: str = ""


class ComfyUISmokeRequest(BaseModel):
    workflow_path: str
    comfyui_base_url: str = "http://127.0.0.1:8188"
    final_storyboard: list[dict[str, Any]] | None = None
    final_prompts: dict[str, Any] | list[dict[str, Any]] | None = None
    artifact_root: str | None = None
    run_id: str = "smoke"
    manual_grid_image_path: str | None = None
    output_root: str = "runs"
    seed: int | None = None
    filename_prefix: str | None = None
    dry_run: bool = False
    timeout_seconds: float = Field(default=30.0, gt=0)

    @field_validator("comfyui_base_url")
    @classmethod
    def _normalize_comfyui_base_url(cls, value: str) -> str:
        return normalize_comfyui_endpoint(value)


class ComfyUISmokeResult(BaseModel):
    status: Literal["passed", "failed"]
    ready: bool = False
    preflight: list[SmokeCheck] = Field(default_factory=list)
    workflow_summary: dict[str, Any] = Field(default_factory=dict)
    grid_asset: dict[str, Any] = Field(default_factory=dict)
    upload_result: dict[str, Any] = Field(default_factory=dict)
    patched_replacements: dict[str, dict[str, Any]] = Field(default_factory=dict)
    prompt_id: str = ""
    artifact_dir: str = ""
    logs: list[str] = Field(default_factory=list)
    failure_code: str = ""


def run_comfyui_smoke(
    request: ComfyUISmokeRequest,
    *,
    client: httpx.Client | None = None,
    resource_limits: ExecutionResourceLimits | None = None,
) -> ComfyUISmokeResult:
    artifact_dir = _make_artifact_dir(Path(request.output_root))
    logs: list[str] = []
    checks: list[SmokeCheck] = []
    _write_json(artifact_dir / "smoke_request.json", request.model_dump())
    _write_logs(artifact_dir / "smoke_logs.jsonl", logs)

    config = ComfyUIRunConfig(
        enabled=True,
        endpoint=request.comfyui_base_url,
        workflow_api_path=request.workflow_path,
    )
    try:
        storyboard = _resolve_final_storyboard(request)
    except ValueError as exc:
        _fail(
            checks,
            "final_prompts_missing",
            str(exc),
            "Provide final_storyboard, final_prompts, or artifact_root with 05_final_prompts.json.",
        )
        storyboard = []
    _apply_request_overrides(storyboard, request)
    workflow_summary = _check_workflow(config, checks)
    grid_asset = _prepare_grid_asset(request, artifact_dir, checks)
    preview = (
        {}
        if _has_failure(checks)
        else _check_patch_preview(config, storyboard, request, grid_asset, checks)
    )
    replacements = _index_replacements(preview)

    _write_json(
        artifact_dir / "smoke_preflight.json",
        {"checks": [item.model_dump() for item in checks]},
    )
    if preview.get("items") and preview["items"][0].get("workflow"):
        _write_json(
            artifact_dir / "smoke_workflow_patched.json",
            preview["items"][0]["workflow"],
        )

    failed = next((item for item in checks if item.status == "fail"), None)
    if failed:
        result = ComfyUISmokeResult(
            status="failed",
            ready=False,
            preflight=checks,
            workflow_summary=workflow_summary,
            grid_asset=grid_asset.model_dump() if grid_asset else {},
            patched_replacements=replacements,
            artifact_dir=str(artifact_dir),
            logs=logs,
            failure_code=failed.id,
        )
        _write_json(artifact_dir / "smoke_result.json", result.model_dump())
        return result

    upload_result: dict[str, Any] = {}
    prompt_id = ""
    if not request.dry_run:
        assert grid_asset is not None
        owns_client = client is None
        active_client = client or httpx.Client(timeout=request.timeout_seconds, trust_env=False)
        try:
            try:
                upload_filename = upload_grid_image(
                    request.comfyui_base_url,
                    grid_asset.local_path,
                    destination_name=grid_asset.comfyui_filename,
                    client=active_client,
                )
            except (httpx.TransportError, httpx.HTTPStatusError) as exc:
                _fail(
                    checks,
                    "comfyui_upload_failed",
                    str(exc),
                    "Check ComfyUI /upload/image and whether the server is running.",
                    **_http_error_evidence(exc),
                )
                result = ComfyUISmokeResult(
                    status="failed",
                    ready=False,
                    preflight=checks,
                    workflow_summary=workflow_summary,
                    grid_asset=grid_asset.model_dump(),
                    patched_replacements=replacements,
                    artifact_dir=str(artifact_dir),
                    logs=logs,
                    failure_code="comfyui_upload_failed",
                )
                _write_json(artifact_dir / "smoke_result.json", result.model_dump())
                return result
            grid_asset.comfyui_filename = upload_filename
            grid_asset.upload_status = "accepted"
            upload_result = {"filename": upload_filename, "status": "accepted"}
            _write_json(artifact_dir / "smoke_upload.json", upload_result)
            try:
                runtime_object_info = fetch_workflow_runtime_object_info(
                    active_client,
                    request.comfyui_base_url,
                    config,
                )
                real_preview = preview_storyboard_submission(
                    config,
                    storyboard,
                    request.filename_prefix or request.run_id,
                    include_workflow=True,
                    grid_image_asset=grid_asset,
                    object_info=runtime_object_info,
                )
            except (httpx.TransportError, httpx.HTTPStatusError, ValueError) as exc:
                _fail(
                    checks,
                    "comfyui_object_info_failed",
                    str(exc),
                    "Check ComfyUI /object_info and the selected workflow.",
                    **_http_error_evidence(exc),
                )
                result = ComfyUISmokeResult(
                    status="failed",
                    ready=False,
                    preflight=checks,
                    workflow_summary=workflow_summary,
                    grid_asset=grid_asset.model_dump(),
                    upload_result=upload_result,
                    patched_replacements=replacements,
                    artifact_dir=str(artifact_dir),
                    logs=logs,
                    failure_code="comfyui_object_info_failed",
                )
                _write_json(artifact_dir / "smoke_result.json", result.model_dump())
                return result
            if real_preview.get("items") and real_preview["items"][0].get("workflow"):
                _write_json(
                    artifact_dir / "smoke_workflow_patched.json",
                    real_preview["items"][0]["workflow"],
                )
            try:
                with _comfyui_limit(resource_limits):
                    submissions = submit_storyboard(
                        config,
                        storyboard,
                        request.filename_prefix or request.run_id,
                        client=active_client,
                        grid_image_asset=grid_asset,
                        object_info=runtime_object_info,
                    )
            except Exception as exc:
                _fail(
                    checks,
                    "comfyui_prompt_failed",
                    str(exc),
                    "Check ComfyUI /prompt and the patched workflow.",
                    **_http_error_evidence(exc),
                )
                result = ComfyUISmokeResult(
                    status="failed",
                    ready=False,
                    preflight=checks,
                    workflow_summary=workflow_summary,
                    grid_asset=grid_asset.model_dump(),
                    upload_result=upload_result,
                    patched_replacements=replacements,
                    artifact_dir=str(artifact_dir),
                    logs=logs,
                    failure_code="comfyui_prompt_failed",
                )
                _write_json(artifact_dir / "smoke_result.json", result.model_dump())
                return result
            prompt_id = submissions[0].prompt_id if submissions else ""
        finally:
            if owns_client:
                active_client.close()
        preview = real_preview
        replacements = _index_replacements(preview)

    result = ComfyUISmokeResult(
        status="passed",
        ready=True,
        preflight=checks,
        workflow_summary=workflow_summary,
        grid_asset=grid_asset.model_dump() if grid_asset else {},
        upload_result=upload_result,
        patched_replacements=replacements,
        prompt_id=prompt_id,
        artifact_dir=str(artifact_dir),
        logs=logs,
    )
    _write_json(artifact_dir / "smoke_result.json", result.model_dump())
    return result


def _make_artifact_dir(output_root: Path) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    path = output_root / f"comfyui_smoke_{stamp}"
    path.mkdir(parents=True, exist_ok=False)
    return path


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _write_logs(path: Path, logs: list[str]) -> None:
    path.write_text(
        "".join(json.dumps({"message": item}, ensure_ascii=False) + "\n" for item in logs),
        encoding="utf-8",
    )


def _has_failure(checks: list[SmokeCheck]) -> bool:
    return any(check.status == "fail" for check in checks)


def _resolve_final_storyboard(request: ComfyUISmokeRequest) -> list[dict[str, Any]]:
    if request.final_storyboard:
        return [dict(item) for item in request.final_storyboard]
    if isinstance(request.final_prompts, list):
        return [dict(item) for item in request.final_prompts]
    if isinstance(request.final_prompts, dict) and isinstance(
        request.final_prompts.get("shots"),
        list,
    ):
        return [dict(item) for item in request.final_prompts["shots"]]
    if request.artifact_root:
        path = Path(request.artifact_root) / "05_final_prompts.json"
        if path.exists():
            payload = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(payload, list):
                return [dict(item) for item in payload]
            if isinstance(payload, dict) and isinstance(payload.get("shots"), list):
                return [dict(item) for item in payload["shots"]]
    raise ValueError("final_storyboard or final_prompts is required for ComfyUI smoke")


def _apply_request_overrides(
    storyboard: list[dict[str, Any]],
    request: ComfyUISmokeRequest,
) -> None:
    if request.seed is None:
        return
    for shot in storyboard:
        inputs = dict(shot.get("comfyui_inputs") or {})
        inputs["seed"] = request.seed
        shot["comfyui_inputs"] = inputs


def _pass(
    checks: list[SmokeCheck],
    check_id: str,
    message: str,
    **evidence: Any,
) -> None:
    checks.append(
        SmokeCheck(id=check_id, status="pass", message=message, evidence=evidence)
    )


def _fail(
    checks: list[SmokeCheck],
    check_id: str,
    message: str,
    suggested_action: str,
    **evidence: Any,
) -> None:
    checks.append(
        SmokeCheck(
            id=check_id,
            status="fail",
            severity="error",
            message=message,
            evidence=evidence,
            suggested_action=suggested_action,
        )
    )


def _check_workflow(
    config: ComfyUIRunConfig,
    checks: list[SmokeCheck],
) -> dict[str, Any]:
    try:
        summary = analyze_workflow_config(config)
    except FileNotFoundError as exc:
        _fail(checks, "workflow_file_readable", str(exc), "Check workflow_path.")
        return {}
    except json.JSONDecodeError as exc:
        _fail(
            checks,
            "workflow_invalid_json",
            str(exc),
            "Export a valid ComfyUI workflow JSON.",
        )
        return {}
    except ValueError as exc:
        _fail(
            checks,
            "workflow_unsupported",
            str(exc),
            "Use the supported LTX LiteGraph/API workflow format.",
        )
        return {}

    _pass(
        checks,
        "workflow_file_readable",
        "Workflow JSON loaded.",
        path=config.workflow_api_path,
    )
    _pass(
        checks,
        "workflow_format_supported",
        "Workflow format is supported.",
        format=summary.get("workflow_format"),
    )
    adapter_mode = str(summary.get("adapter_mode") or "")
    if adapter_mode == "litegraph_ltx_widget_patch":
        widget_points = summary.get("ltx_widget_patch_points") or {}
        required = ["positive_prompt_node_ids", "image_node_ids"]
        missing = [key for key in required if not widget_points.get(key)]
        if missing:
            _fail(
                checks,
                "ltx_widget_patch_points",
                f"Missing widget patch points: {missing}",
                "Use a supported integrated-package LTX LiteGraph workflow.",
            )
        else:
            _pass(
                checks,
                "ltx_widget_patch_points",
                "Detected LTX widget patch points.",
                **widget_points,
            )
        return summary

    points = summary.get("ltx_injection_points") or {}
    required = ["json_node_id", "seed_node_id", "filename_prefix_node_id", "grid_image_node_id"]
    missing = [key for key in required if not points.get(key)]
    if missing:
        _fail(
            checks,
            "ltx_injection_points",
            f"Missing injection points: {missing}",
            "Use the supported LTX 2.3 workflow.",
        )
        return summary

    _pass(checks, "ltx_injection_points", "Detected LTX injection points.", **points)
    shape = summary.get("grid_shape") or {}
    if shape.get("columns") == 2 and shape.get("rows") == 2:
        _pass(checks, "grid_shape", "Detected 2x2 grid shape.", **shape)
    else:
        _fail(checks, "grid_shape", "Expected 2x2 grid shape.", "Use the LTX 2.3 four-grid workflow.", **shape)
    return summary


def _prepare_grid_asset(
    request: ComfyUISmokeRequest,
    artifact_dir: Path,
    checks: list[SmokeCheck],
) -> GridImageAsset | None:
    if not request.manual_grid_image_path:
        _fail(
            checks,
            "grid_image_missing",
            "manual_grid_image_path is required for first-version smoke.",
            "Provide a local four-grid image path.",
        )
        return None

    image_config = GridImageConfig()
    try:
        validated = validate_grid_image(
            request.manual_grid_image_path,
            min_dimension=image_config.min_dimension,
            max_bytes=image_config.max_bytes,
        )
    except ValueError as exc:
        _fail(
            checks,
            "grid_image_invalid",
            str(exc),
            "Provide a valid square 2x2 four-grid image.",
        )
        return None

    destination = artifact_dir / f"smoke_grid_image{validated.path.suffix.lower()}"
    shutil.copyfile(validated.path, destination)
    filename = deterministic_comfyui_filename(
        request.run_id,
        validated.sha256,
        validated.mime_type,
    )
    _pass(
        checks,
        "grid_image_valid",
        "Four-grid image validated.",
        width=validated.width,
        height=validated.height,
        sha256=validated.sha256,
    )
    return GridImageAsset(
        source="manual",
        local_path=str(destination),
        sha256=validated.sha256,
        mime_type=validated.mime_type,
        width=validated.width,
        height=validated.height,
        byte_size=validated.byte_size,
        comfyui_filename=filename,
        upload_status="pending",
    )


def _check_patch_preview(
    config: ComfyUIRunConfig,
    storyboard: list[dict[str, Any]],
    request: ComfyUISmokeRequest,
    grid_asset: GridImageAsset | None,
    checks: list[SmokeCheck],
) -> dict[str, Any]:
    if not storyboard:
        _fail(
            checks,
            "final_prompts_missing",
            "Final storyboard is empty.",
            "Provide final_storyboard or 05_final_prompts.json.",
        )
        return {}
    _pass(
        checks,
        "final_prompts_available",
        "Final storyboard is available.",
        shot_count=len(storyboard),
    )
    if grid_asset is None:
        return {}
    try:
        preview = preview_storyboard_submission(
            config,
            storyboard,
            request.filename_prefix or request.run_id,
            include_workflow=True,
            grid_image_asset=grid_asset,
            allow_unuploaded_grid_image=True,
        )
    except ValueError as exc:
        _fail(
            checks,
            "workflow_patch_failed",
            str(exc),
            "Inspect the workflow injection points and final prompts.",
        )
        return {}
    _pass(
        checks,
        "patch_preview_safe",
        "Workflow patch preview succeeded.",
        planned_count=preview.get("planned_count"),
    )
    return preview


def _index_replacements(preview: dict[str, Any]) -> dict[str, dict[str, Any]]:
    if not preview.get("items"):
        return {}
    replacements = preview["items"][0].get("replacements", [])
    return {str(item.get("key")): dict(item) for item in replacements}


def _comfyui_limit(resource_limits: ExecutionResourceLimits | None):
    if resource_limits is None:
        return nullcontext()
    return resource_limits.comfyui_submission()


def _load_request(path: Path) -> ComfyUISmokeRequest:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    return ComfyUISmokeRequest.model_validate(payload)


def _http_error_evidence(exc: Exception) -> dict[str, Any]:
    if not isinstance(exc, httpx.HTTPStatusError):
        return {}
    return {
        "status_code": exc.response.status_code,
        "response_text": exc.response.text[:4000],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run a local ComfyUI LTX smoke test.")
    parser.add_argument("--request", required=True, help="Path to smoke request JSON.")
    parser.add_argument("--dry-run", action="store_true", help="Force dry-run mode.")
    parser.add_argument("--comfyui-base-url", default="", help="Override ComfyUI base URL.")
    parser.add_argument("--output-root", default="", help="Override artifact output root.")
    parser.add_argument("--timeout-seconds", type=float, default=0, help="Override network timeout.")
    args = parser.parse_args(argv)

    request = _load_request(Path(args.request))
    if args.dry_run:
        request.dry_run = True
    if args.comfyui_base_url:
        request.comfyui_base_url = normalize_comfyui_endpoint(args.comfyui_base_url)
    if args.output_root:
        request.output_root = args.output_root
    if args.timeout_seconds > 0:
        request.timeout_seconds = args.timeout_seconds

    result = run_comfyui_smoke(request)
    print(f"status={result.status}")
    print(f"ready={str(result.ready).lower()}")
    if result.prompt_id:
        print(f"prompt_id={result.prompt_id}")
    if result.failure_code:
        print(f"failure_code={result.failure_code}")
    print(f"artifact_dir={result.artifact_dir}")
    return 0 if result.status == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
