from __future__ import annotations

import json
from typing import Any

import httpx
import openai

from .models import FailureRecord
from .pipeline import MODEL_STAGE_IDS


def classify_failure(stage: str, exc: Exception) -> FailureRecord:
    status = _status_code(exc)
    message = str(exc)
    exception_type = type(exc).__name__
    details = getattr(exc, "details", {})
    if not isinstance(details, dict):
        details = {}
    category = "unknown"
    code = "unknown_error"
    retryable = False

    if "CancellationRequested" in exception_type or "cancel" in message.lower():
        category = "cancelled"
        code = "cancelled"
    elif exception_type == "ExecutionPolicyExceeded":
        category = "validation"
        code = str(getattr(exc, "code", "") or "execution_policy_exhausted")
    elif isinstance(exc, json.JSONDecodeError):
        category = "contract"
        code = "malformed_json"
    elif isinstance(exc, openai.APITimeoutError):
        category = "timeout"
        code = "api_timeout"
        retryable = True
    elif isinstance(exc, openai.APIConnectionError):
        category = "transient"
        code = "api_connection_error"
        retryable = True
    elif isinstance(exc, (httpx.TimeoutException, TimeoutError)):
        category = "timeout"
        code = "timeout"
        retryable = True
    elif status is not None:
        category, code, retryable = _classify_http_status(status)
    elif isinstance(exc, httpx.TransportError):
        category = "transient"
        code = "transport_error"
        retryable = True
    else:
        category, code, retryable = _classify_message(stage, message)

    return FailureRecord(
        stage=stage,
        category=category,
        code=code,
        retryable=retryable,
        source=_source_for_stage(stage),
        message=message,
        exception_type=exception_type,
        http_status=status,
        details=details,
    )


def _classify_http_status(status: int) -> tuple[str, str, bool]:
    if status == 429:
        return "throttled", "http_429", True
    if status in {408, 409} or status >= 500:
        return "transient", f"http_{status}", True
    if status in {401, 403}:
        return "configuration", f"http_{status}", False
    return "unknown", f"http_{status}", False


def _classify_message(stage: str, message: str) -> tuple[str, str, bool]:
    lower = message.lower()
    if stage == "four_grid_asset" and (
        "grid image" in lower
        or "quadrant" in lower
        or "loadimage" in lower
        or "grid_image" in lower
    ):
        return "validation", "grid_image_invalid", False
    if "quality gate failed" in lower or stage == "quality_gate":
        return "validation", "quality_gate_failed", False
    if "execution policy" in lower or "execution budget" in lower:
        return "validation", "execution_policy_exhausted", False
    if "missing required field" in lower or "must return between" in lower:
        return "contract", "output_contract_failed", False
    if "template" in lower or "placeholder(s)" in lower:
        return "configuration", "template_invalid", False
    if "missing model config" in lower or "missing environment variable" in lower:
        return "configuration", "model_config_invalid", False
    if "placeholder_map" in lower or "workflow" in lower or "comfyui" in lower:
        return "external", "external_workflow_invalid", False
    return "unknown", "unknown_error", False


def _source_for_stage(stage: str) -> str:
    if stage == "comfyui":
        return "comfyui"
    if stage in MODEL_STAGE_IDS:
        return "model"
    if stage == "artifacts":
        return "artifact"
    return "agent"


def _status_code(exc: Exception) -> int | None:
    status = getattr(exc, "status_code", None)
    if isinstance(status, int):
        return status
    response: Any = getattr(exc, "response", None)
    response_status = getattr(response, "status_code", None)
    return response_status if isinstance(response_status, int) else None
