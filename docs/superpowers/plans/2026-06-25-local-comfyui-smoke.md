# Local ComfyUI Smoke Runner Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a real local ComfyUI smoke runner that validates finalized LTX prompts, validates/copies a four-grid image, uploads it to ComfyUI, patches the detected LTX workflow, enqueues `/prompt`, and writes replayable smoke artifacts.

**Architecture:** Add one focused smoke orchestration module that reuses existing ComfyUI and grid-image primitives instead of duplicating workflow logic. Add a small API route and CLI entrypoint over the same function, with dry-run and real-run paths sharing preflight, artifact, and workflow-patch behavior.

**Tech Stack:** Python 3.11+, Pydantic, FastAPI, httpx, Pillow via existing `grid_image.py`, pytest

---

## File Structure

- Create `relief_story_agent/smoke_comfyui.py`: owns smoke request/result models, preflight checks, artifact writing, CLI parsing, and the `run_comfyui_smoke` orchestration function.
- Modify `relief_story_agent/api.py`: import smoke models/function and add `POST /api/smoke/comfyui`.
- Modify `relief_story_agent/server.py`: no behavior change expected unless import ordering requires it.
- Create `relief_story_agent/tests/test_smoke_comfyui.py`: unit and mock integration coverage for dry-run, failures, artifact writing, upload, and `/prompt`.
- Modify `relief_story_agent/README.md`: document CLI/API smoke usage and what it does not do.

The first implementation keeps smoke models in `smoke_comfyui.py` because they are not core run-state models. If a later UI needs them broadly, they can be moved to `models.py` with no behavior change.

## Task 1: Smoke Request, Result, and Dry-Run Preflight

**Files:**
- Create: `relief_story_agent/smoke_comfyui.py`
- Test: `relief_story_agent/tests/test_smoke_comfyui.py`

- [ ] **Step 1: Write failing dry-run tests**

Create `relief_story_agent/tests/test_smoke_comfyui.py` with these helpers and tests:

```python
from __future__ import annotations

import json
from pathlib import Path

import pytest
from PIL import Image

from relief_story_agent.smoke_comfyui import ComfyUISmokeRequest, run_comfyui_smoke
from relief_story_agent.tests.fixtures.ltx23_workflow_factory import make_ltx23_litegraph_workflow


def _write_workflow(path: Path) -> Path:
    path.write_text(json.dumps(make_ltx23_litegraph_workflow()), encoding="utf-8")
    return path


def _write_grid(path: Path) -> Path:
    image = Image.new("RGB", (1024, 1024), "white")
    colors = ["red", "green", "blue", "yellow"]
    boxes = [(0, 0, 512, 512), (512, 0, 1024, 512), (0, 512, 512, 1024), (512, 512, 1024, 1024)]
    for color, box in zip(colors, boxes):
        for x in range(box[0], box[2]):
            for y in range(box[1], box[3]):
                image.putpixel((x, y), color)
    image.save(path)
    return path


def _final_storyboard() -> list[dict]:
    return [
        {
            "shot_id": 1,
            "time_range": "0-15s",
            "description": "quiet convenience store",
            "image_prompt": "soft convenience store keyframe",
            "negative_prompt": "shouting, horror, text, watermark",
            "comfyui_inputs": {"seed": 1234},
        }
    ]


def test_smoke_dry_run_writes_preflight_and_patched_workflow_without_upload(tmp_path):
    request = ComfyUISmokeRequest(
        workflow_path=str(_write_workflow(tmp_path / "workflow.json")),
        comfyui_base_url="http://127.0.0.1:8188",
        final_storyboard=_final_storyboard(),
        manual_grid_image_path=str(_write_grid(tmp_path / "grid.png")),
        output_root=str(tmp_path / "out"),
        dry_run=True,
    )

    result = run_comfyui_smoke(request)

    assert result.status == "passed"
    assert result.ready is True
    assert result.prompt_id == ""
    assert result.upload_result == {}
    assert result.artifact_dir
    artifact_dir = Path(result.artifact_dir)
    assert (artifact_dir / "smoke_request.json").exists()
    assert (artifact_dir / "smoke_preflight.json").exists()
    assert (artifact_dir / "smoke_grid_image.png").exists()
    assert (artifact_dir / "smoke_workflow_patched.json").exists()
    assert (artifact_dir / "smoke_result.json").exists()
    assert not (artifact_dir / "smoke_upload.json").exists()
    assert any(check.id == "ltx_injection_points" and check.status == "pass" for check in result.preflight)
    assert result.patched_replacements["grid_image"]["node"] == "196"
```

- [ ] **Step 2: Verify RED**

Run:

```powershell
python -m pytest relief_story_agent/tests/test_smoke_comfyui.py::test_smoke_dry_run_writes_preflight_and_patched_workflow_without_upload -q
```

Expected: FAIL because `relief_story_agent.smoke_comfyui` does not exist.

- [ ] **Step 3: Implement smoke models and preflight shell**

Create `relief_story_agent/smoke_comfyui.py` with this foundation:

```python
from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

import httpx
from pydantic import BaseModel, Field

from .comfyui import (
    analyze_workflow_config,
    preview_storyboard_submission,
)
from .grid_image import deterministic_comfyui_filename, validate_grid_image
from .models import ComfyUIRunConfig, GridImageAsset
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
    config = ComfyUIRunConfig(
        enabled=True,
        endpoint=request.comfyui_base_url,
        workflow_api_path=request.workflow_path,
    )
    storyboard = _resolve_final_storyboard(request)
    _apply_request_overrides(storyboard, request)
    workflow_summary = _check_workflow(config, checks)
    grid_asset = _prepare_grid_asset(request, artifact_dir, checks)
    preview = _check_patch_preview(config, storyboard, request, grid_asset, checks)
    replacements = _index_replacements(preview)
    _write_json(artifact_dir / "smoke_preflight.json", {"checks": [item.model_dump() for item in checks]})
    if preview.get("items"):
        _write_json(artifact_dir / "smoke_workflow_patched.json", preview["items"][0].get("workflow", {}))
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
    result = ComfyUISmokeResult(
        status="passed",
        ready=True,
        preflight=checks,
        workflow_summary=workflow_summary,
        grid_asset=grid_asset.model_dump(),
        patched_replacements=replacements,
        artifact_dir=str(artifact_dir),
        logs=logs,
    )
    _write_json(artifact_dir / "smoke_result.json", result.model_dump())
    return result
```

- [ ] **Step 4: Add dry-run helpers**

Add these helpers in the same file:

```python
def _make_artifact_dir(output_root: Path) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    path = output_root / f"comfyui_smoke_{stamp}"
    path.mkdir(parents=True, exist_ok=False)
    return path


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _resolve_final_storyboard(request: ComfyUISmokeRequest) -> list[dict[str, Any]]:
    if request.final_storyboard:
        return [dict(item) for item in request.final_storyboard]
    if isinstance(request.final_prompts, list):
        return [dict(item) for item in request.final_prompts]
    if isinstance(request.final_prompts, dict) and isinstance(request.final_prompts.get("shots"), list):
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


def _apply_request_overrides(storyboard: list[dict[str, Any]], request: ComfyUISmokeRequest) -> None:
    if request.seed is not None:
        for shot in storyboard:
            inputs = dict(shot.get("comfyui_inputs") or {})
            inputs["seed"] = request.seed
            shot["comfyui_inputs"] = inputs


def _pass(checks: list[SmokeCheck], check_id: str, message: str, **evidence: Any) -> None:
    checks.append(SmokeCheck(id=check_id, status="pass", message=message, evidence=evidence))


def _fail(checks: list[SmokeCheck], check_id: str, message: str, suggested_action: str, **evidence: Any) -> None:
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


def _check_workflow(config: ComfyUIRunConfig, checks: list[SmokeCheck]) -> dict[str, Any]:
    try:
        summary = analyze_workflow_config(config)
    except FileNotFoundError as exc:
        _fail(checks, "workflow_file_readable", str(exc), "Check workflow_path.")
        return {}
    except json.JSONDecodeError as exc:
        _fail(checks, "workflow_invalid_json", str(exc), "Export a valid ComfyUI workflow JSON.")
        return {}
    except ValueError as exc:
        _fail(checks, "workflow_unsupported", str(exc), "Use the supported LTX LiteGraph/API workflow format.")
        return {}
    _pass(checks, "workflow_file_readable", "Workflow JSON loaded.", path=config.workflow_api_path)
    _pass(checks, "workflow_format_supported", "Workflow format is supported.", format=summary.get("workflow_format"))
    points = summary.get("ltx_injection_points") or {}
    required = ["json_node_id", "seed_node_id", "filename_prefix_node_id", "grid_image_node_id"]
    missing = [key for key in required if not points.get(key)]
    if missing:
        _fail(checks, "ltx_injection_points", f"Missing injection points: {missing}", "Use the supported LTX 2.3 workflow.")
    else:
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
        _fail(checks, "grid_image_missing", "manual_grid_image_path is required for first-version smoke.", "Provide a local four-grid image path.")
        return None
    try:
        validated = validate_grid_image(request.manual_grid_image_path)
    except ValueError as exc:
        _fail(checks, "grid_image_invalid", str(exc), "Provide a valid square 2x2 four-grid image.")
        return None
    destination = artifact_dir / f"smoke_grid_image{validated.path.suffix.lower()}"
    shutil.copyfile(validated.path, destination)
    filename = deterministic_comfyui_filename(request.run_id, validated.sha256, validated.mime_type)
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
        _fail(checks, "final_prompts_missing", "Final storyboard is empty.", "Provide final_storyboard or 05_final_prompts.json.")
        return {}
    _pass(checks, "final_prompts_available", "Final storyboard is available.", shot_count=len(storyboard))
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
        _fail(checks, "workflow_patch_failed", str(exc), "Inspect the workflow injection points and final prompts.")
        return {}
    _pass(checks, "patch_preview_safe", "Workflow patch preview succeeded.", planned_count=preview.get("planned_count"))
    return preview


def _index_replacements(preview: dict[str, Any]) -> dict[str, dict[str, Any]]:
    if not preview.get("items"):
        return {}
    replacements = preview["items"][0].get("replacements", [])
    return {str(item.get("key")): dict(item) for item in replacements}
```

- [ ] **Step 5: Verify GREEN**

Run:

```powershell
python -m pytest relief_story_agent/tests/test_smoke_comfyui.py::test_smoke_dry_run_writes_preflight_and_patched_workflow_without_upload -q
```

Expected: PASS.

## Task 2: Failure Semantics and Artifact Completeness

**Files:**
- Modify: `relief_story_agent/smoke_comfyui.py`
- Test: `relief_story_agent/tests/test_smoke_comfyui.py`

- [ ] **Step 1: Write failing failure tests**

Append:

```python
def test_smoke_fails_before_network_when_final_prompts_missing(tmp_path):
    request = ComfyUISmokeRequest(
        workflow_path=str(_write_workflow(tmp_path / "workflow.json")),
        comfyui_base_url="http://127.0.0.1:8188",
        manual_grid_image_path=str(_write_grid(tmp_path / "grid.png")),
        output_root=str(tmp_path / "out"),
        dry_run=True,
    )

    result = run_comfyui_smoke(request)

    assert result.status == "failed"
    assert result.ready is False
    assert result.failure_code == "final_prompts_missing"
    assert Path(result.artifact_dir, "smoke_result.json").exists()


def test_smoke_fails_before_patch_when_grid_image_missing(tmp_path):
    request = ComfyUISmokeRequest(
        workflow_path=str(_write_workflow(tmp_path / "workflow.json")),
        comfyui_base_url="http://127.0.0.1:8188",
        final_storyboard=_final_storyboard(),
        output_root=str(tmp_path / "out"),
        dry_run=True,
    )

    result = run_comfyui_smoke(request)

    assert result.status == "failed"
    assert result.failure_code == "grid_image_missing"
    assert not Path(result.artifact_dir, "smoke_workflow_patched.json").exists()
```

- [ ] **Step 2: Verify RED**

Run:

```powershell
python -m pytest relief_story_agent/tests/test_smoke_comfyui.py -k "missing" -q
```

Expected: one test fails because `_resolve_final_storyboard` currently raises instead of returning a structured failure.

- [ ] **Step 3: Convert final prompt errors into checks**

Change `run_comfyui_smoke` so final storyboard resolution is checked before patching:

```python
try:
    storyboard = _resolve_final_storyboard(request)
except ValueError as exc:
    _fail(checks, "final_prompts_missing", str(exc), "Provide final_storyboard, final_prompts, or artifact_root with 05_final_prompts.json.")
    storyboard = []
```

Keep the rest of the pipeline running only far enough to write preflight and result artifacts.

- [ ] **Step 4: Make artifact writing conditional and stable**

In `run_comfyui_smoke`, only write `smoke_workflow_patched.json` when `preview.get("items")` and a workflow object exists:

```python
if preview.get("items") and preview["items"][0].get("workflow"):
    _write_json(artifact_dir / "smoke_workflow_patched.json", preview["items"][0]["workflow"])
```

- [ ] **Step 5: Verify GREEN**

Run:

```powershell
python -m pytest relief_story_agent/tests/test_smoke_comfyui.py -k "missing" -q
```

Expected: PASS.

## Task 3: Real ComfyUI Upload and `/prompt` Enqueue

**Files:**
- Modify: `relief_story_agent/smoke_comfyui.py`
- Test: `relief_story_agent/tests/test_smoke_comfyui.py`

- [ ] **Step 1: Write failing mock ComfyUI real-run test**

Append:

```python
import httpx


def test_smoke_real_run_uploads_grid_and_enqueues_prompt(tmp_path):
    requests: list[tuple[str, str]] = []
    uploaded_name = ""
    prompted_payload = {}

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal uploaded_name, prompted_payload
        requests.append((request.method, request.url.path))
        if request.url.path == "/upload/image":
            body = request.read()
            assert b"smoke" in body or b"grid" in body
            uploaded_name = "smoke_uploaded_grid.png"
            return httpx.Response(200, json={"name": uploaded_name, "subfolder": "", "type": "input"})
        if request.url.path == "/prompt":
            prompted_payload = json.loads(request.content.decode("utf-8"))
            return httpx.Response(200, json={"prompt_id": prompted_payload["prompt_id"]})
        return httpx.Response(404)

    request = ComfyUISmokeRequest(
        workflow_path=str(_write_workflow(tmp_path / "workflow.json")),
        comfyui_base_url="http://comfy.test",
        final_storyboard=_final_storyboard(),
        manual_grid_image_path=str(_write_grid(tmp_path / "grid.png")),
        output_root=str(tmp_path / "out"),
        run_id="smoke_real",
        dry_run=False,
    )

    result = run_comfyui_smoke(
        request,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    assert result.status == "passed"
    assert result.prompt_id.startswith("smoke_real")
    assert result.upload_result["filename"] == uploaded_name
    assert ("POST", "/upload/image") in requests
    assert ("POST", "/prompt") in requests
    assert prompted_payload["prompt"]["196"]["inputs"]["image"] == uploaded_name
    assert Path(result.artifact_dir, "smoke_upload.json").exists()
```

- [ ] **Step 2: Verify RED**

Run:

```powershell
python -m pytest relief_story_agent/tests/test_smoke_comfyui.py::test_smoke_real_run_uploads_grid_and_enqueues_prompt -q
```

Expected: FAIL because real-run currently returns after dry-run-style preview and never uploads/enqueues.

- [ ] **Step 3: Add real-run imports**

Update imports in `smoke_comfyui.py`:

```python
from .comfyui import (
    analyze_workflow_config,
    preview_storyboard_submission,
    submit_storyboard,
    upload_grid_image,
)
```

- [ ] **Step 4: Add real-run branch**

In `run_comfyui_smoke`, after preflight passes and before constructing the passed result, add:

```python
upload_result: dict[str, Any] = {}
prompt_id = ""
if not request.dry_run:
    upload_filename = upload_grid_image(
        request.comfyui_base_url,
        grid_asset.local_path,
        destination_name=grid_asset.comfyui_filename,
        client=client,
    )
    grid_asset.comfyui_filename = upload_filename
    grid_asset.upload_status = "accepted"
    upload_result = {"filename": upload_filename, "status": "accepted"}
    _write_json(artifact_dir / "smoke_upload.json", upload_result)
    real_preview = preview_storyboard_submission(
        config,
        storyboard,
        request.filename_prefix or request.run_id,
        include_workflow=True,
        grid_image_asset=grid_asset,
    )
    if real_preview.get("items") and real_preview["items"][0].get("workflow"):
        _write_json(artifact_dir / "smoke_workflow_patched.json", real_preview["items"][0]["workflow"])
    with _comfyui_limit(resource_limits):
        submissions = submit_storyboard(
            config,
            storyboard,
            request.filename_prefix or request.run_id,
            client=client,
            grid_image_asset=grid_asset,
        )
    prompt_id = submissions[0].prompt_id if submissions else ""
    preview = real_preview
    replacements = _index_replacements(real_preview)
```

Add a tiny context manager:

```python
from contextlib import nullcontext


def _comfyui_limit(resource_limits: ExecutionResourceLimits | None):
    return resource_limits.comfyui_submission() if resource_limits else nullcontext()
```

- [ ] **Step 5: Include upload and prompt in result**

Set `upload_result=upload_result` and `prompt_id=prompt_id` in the passed `ComfyUISmokeResult`.

- [ ] **Step 6: Verify GREEN**

Run:

```powershell
python -m pytest relief_story_agent/tests/test_smoke_comfyui.py::test_smoke_real_run_uploads_grid_and_enqueues_prompt -q
```

Expected: PASS.

## Task 4: Real-Run Failure Classification

**Files:**
- Modify: `relief_story_agent/smoke_comfyui.py`
- Test: `relief_story_agent/tests/test_smoke_comfyui.py`

- [ ] **Step 1: Write failing network failure tests**

Append:

```python
def test_smoke_real_run_reports_upload_failure(tmp_path):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/upload/image":
            return httpx.Response(500, text="upload failed")
        return httpx.Response(404)

    result = run_comfyui_smoke(
        ComfyUISmokeRequest(
            workflow_path=str(_write_workflow(tmp_path / "workflow.json")),
            comfyui_base_url="http://comfy.test",
            final_storyboard=_final_storyboard(),
            manual_grid_image_path=str(_write_grid(tmp_path / "grid.png")),
            output_root=str(tmp_path / "out"),
        ),
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    assert result.status == "failed"
    assert result.failure_code == "comfyui_upload_failed"


def test_smoke_real_run_reports_prompt_failure(tmp_path):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/upload/image":
            return httpx.Response(200, json={"name": "grid.png"})
        if request.url.path == "/prompt":
            return httpx.Response(500, text="prompt failed")
        return httpx.Response(404)

    result = run_comfyui_smoke(
        ComfyUISmokeRequest(
            workflow_path=str(_write_workflow(tmp_path / "workflow.json")),
            comfyui_base_url="http://comfy.test",
            final_storyboard=_final_storyboard(),
            manual_grid_image_path=str(_write_grid(tmp_path / "grid.png")),
            output_root=str(tmp_path / "out"),
        ),
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    assert result.status == "failed"
    assert result.failure_code == "comfyui_prompt_failed"
    assert Path(result.artifact_dir, "smoke_upload.json").exists()
```

- [ ] **Step 2: Verify RED**

Run:

```powershell
python -m pytest relief_story_agent/tests/test_smoke_comfyui.py -k "upload_failure or prompt_failure" -q
```

Expected: FAIL because HTTP exceptions escape instead of becoming structured smoke results.

- [ ] **Step 3: Wrap upload errors**

Around `upload_grid_image`, catch `httpx.TransportError` and `httpx.HTTPStatusError`:

```python
try:
    upload_filename = upload_grid_image(...)
except (httpx.TransportError, httpx.HTTPStatusError) as exc:
    _fail(checks, "comfyui_upload_failed", str(exc), "Check ComfyUI /upload/image and whether the server is running.")
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
```

- [ ] **Step 4: Wrap prompt errors**

Around `submit_storyboard`, catch `Exception` after upload succeeds:

```python
try:
    with _comfyui_limit(resource_limits):
        submissions = submit_storyboard(...)
except Exception as exc:
    _fail(checks, "comfyui_prompt_failed", str(exc), "Check ComfyUI /prompt and the patched workflow.")
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
```

- [ ] **Step 5: Verify GREEN**

Run:

```powershell
python -m pytest relief_story_agent/tests/test_smoke_comfyui.py -k "upload_failure or prompt_failure" -q
```

Expected: PASS.

## Task 5: API Route

**Files:**
- Modify: `relief_story_agent/api.py`
- Test: `relief_story_agent/tests/test_smoke_comfyui.py`

- [ ] **Step 1: Write failing API test**

Append:

```python
from fastapi.testclient import TestClient

from relief_story_agent.api import create_app
from relief_story_agent.orchestrator import StoryRunOrchestrator
from relief_story_agent.providers import ScriptedModelProvider
from relief_story_agent.storage import InMemoryRunStore


def test_api_smoke_comfyui_dry_run_returns_result(tmp_path):
    app = create_app(
        StoryRunOrchestrator(
            provider=ScriptedModelProvider({}),
            store=InMemoryRunStore(),
        )
    )
    client = TestClient(app)

    response = client.post(
        "/api/smoke/comfyui",
        json={
            "workflow_path": str(_write_workflow(tmp_path / "workflow.json")),
            "comfyui_base_url": "http://127.0.0.1:8188",
            "final_storyboard": _final_storyboard(),
            "manual_grid_image_path": str(_write_grid(tmp_path / "grid.png")),
            "output_root": str(tmp_path / "out"),
            "dry_run": True,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "passed"
    assert body["ready"] is True
    assert body["prompt_id"] == ""
```

- [ ] **Step 2: Verify RED**

Run:

```powershell
python -m pytest relief_story_agent/tests/test_smoke_comfyui.py::test_api_smoke_comfyui_dry_run_returns_result -q
```

Expected: FAIL with 404 for `/api/smoke/comfyui`.

- [ ] **Step 3: Wire route**

In `relief_story_agent/api.py`, add imports:

```python
from .smoke_comfyui import ComfyUISmokeRequest, run_comfyui_smoke
```

Add route near the existing ComfyUI endpoints:

```python
    @app.post("/api/smoke/comfyui")
    def smoke_comfyui(request: ComfyUISmokeRequest):
        result = run_comfyui_smoke(
            request,
            resource_limits=orchestrator.resource_limits,
        )
        return result.model_dump()
```

- [ ] **Step 4: Verify GREEN**

Run:

```powershell
python -m pytest relief_story_agent/tests/test_smoke_comfyui.py::test_api_smoke_comfyui_dry_run_returns_result -q
```

Expected: PASS.

## Task 6: CLI Entry Point

**Files:**
- Modify: `relief_story_agent/smoke_comfyui.py`
- Test: `relief_story_agent/tests/test_smoke_comfyui.py`

- [ ] **Step 1: Write failing CLI test**

Append:

```python
import subprocess
import sys


def test_smoke_cli_dry_run_exits_zero_and_writes_result(tmp_path):
    request_path = tmp_path / "smoke_request.json"
    request_path.write_text(
        json.dumps(
            {
                "workflow_path": str(_write_workflow(tmp_path / "workflow.json")),
                "comfyui_base_url": "http://127.0.0.1:8188",
                "final_storyboard": _final_storyboard(),
                "manual_grid_image_path": str(_write_grid(tmp_path / "grid.png")),
                "output_root": str(tmp_path / "out"),
                "dry_run": True,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    completed = subprocess.run(
        [sys.executable, "-m", "relief_story_agent.smoke_comfyui", "--request", str(request_path)],
        cwd=str(Path(__file__).resolve().parents[2]),
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert completed.returncode == 0
    assert "status=passed" in completed.stdout
    assert "artifact_dir=" in completed.stdout
```

- [ ] **Step 2: Verify RED**

Run:

```powershell
python -m pytest relief_story_agent/tests/test_smoke_comfyui.py::test_smoke_cli_dry_run_exits_zero_and_writes_result -q
```

Expected: FAIL because the module has no CLI behavior.

- [ ] **Step 3: Add CLI parser and main**

Add to `smoke_comfyui.py`:

```python
def _load_request(path: Path) -> ComfyUISmokeRequest:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return ComfyUISmokeRequest.model_validate(payload)


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
        request.comfyui_base_url = args.comfyui_base_url
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
```

- [ ] **Step 4: Verify GREEN**

Run:

```powershell
python -m pytest relief_story_agent/tests/test_smoke_comfyui.py::test_smoke_cli_dry_run_exits_zero_and_writes_result -q
```

Expected: PASS.

## Task 7: README Documentation

**Files:**
- Modify: `relief_story_agent/README.md`
- Test: manual readback command

- [ ] **Step 1: Add smoke section**

Add a section near the ComfyUI documentation:

```markdown
## Local ComfyUI Smoke Test

Use the smoke runner before batch generation to verify that a finalized LTX storyboard and four-grid image can be accepted by your local ComfyUI workflow.

Dry-run:

```powershell
python -m relief_story_agent.smoke_comfyui --request .\smoke_request.json --dry-run
```

Real enqueue:

```powershell
python -m relief_story_agent.smoke_comfyui --request .\smoke_request.json
```

The request JSON accepts `workflow_path`, `comfyui_base_url`, `final_storyboard` or `final_prompts`, `manual_grid_image_path`, `output_root`, and optional `run_id`, `seed`, and `filename_prefix`.

Dry-run writes preflight and patched-workflow artifacts without uploading or enqueueing. Real mode uploads the four-grid image to `/upload/image`, injects the returned filename into the detected `LoadImage` node, submits `/prompt`, and records the returned `prompt_id`.

This tool does not call text models, does not generate the four-grid image, does not wait for render completion, and does not download final videos.
```

- [ ] **Step 2: Verify README text exists**

Run:

```powershell
Select-String -Path relief_story_agent/README.md -Pattern "Local ComfyUI Smoke Test","smoke_comfyui","/api/smoke/comfyui"
```

Expected: finds the new section and commands.

## Task 8: Full Verification

**Files:**
- No additional production files.

- [ ] **Step 1: Run smoke tests**

Run:

```powershell
python -m pytest relief_story_agent/tests/test_smoke_comfyui.py -q
```

Expected: all smoke tests pass.

- [ ] **Step 2: Run related ComfyUI tests**

Run:

```powershell
python -m pytest relief_story_agent/tests/test_comfyui_mapping.py relief_story_agent/tests/test_grid_image.py relief_story_agent/tests/test_api.py -q
```

Expected: all related tests pass.

- [ ] **Step 3: Run full project tests**

Run:

```powershell
python -m pytest relief_story_agent/tests -q
```

Expected: all project tests pass.

- [ ] **Step 4: Run compile check**

Run:

```powershell
python -m compileall -q relief_story_agent
```

Expected: exit code 0.

- [ ] **Step 5: Check Git availability**

Run:

```powershell
git rev-parse --git-dir
```

Expected in this workspace: may fail with `fatal: not a git repository`. If it fails, report changed files and verification results instead of fabricating a commit.

## Self-Review Notes

- Spec coverage: API, CLI, dry-run, real upload, `/prompt`, artifacts, failure codes, resource limit hook, Windows paths, and no UI/no model calls are covered.
- Placeholder scan: the plan avoids unfinished-marker words and open-ended repair instructions.
- Type consistency: the plan consistently uses `ComfyUISmokeRequest`, `ComfyUISmokeResult`, `SmokeCheck`, and `run_comfyui_smoke`.
- Scope control: render monitoring, output download, image generation, and UI are explicitly left out of this implementation slice.
