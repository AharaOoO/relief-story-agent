from __future__ import annotations

from typing import Any


def require_mapping(payload: dict[str, Any], stage: str, field: str) -> dict[str, Any]:
    if field not in payload:
        raise ValueError(f"{stage} missing required field: {field}")
    value = payload[field]
    if not isinstance(value, dict):
        raise ValueError(f"{stage} field {field} must be an object")
    return value


def require_list(payload: dict[str, Any], stage: str, field: str) -> list[Any]:
    if field not in payload:
        raise ValueError(f"{stage} missing required field: {field}")
    value = payload[field]
    if not isinstance(value, list):
        raise ValueError(f"{stage} field {field} must be a list")
    return value


def require_bool(payload: dict[str, Any], stage: str, field: str) -> bool:
    if field not in payload:
        raise ValueError(f"{stage} missing required field: {field}")
    value = payload[field]
    if not isinstance(value, bool):
        raise ValueError(f"{stage} field {field} must be a boolean")
    return value


def require_shot_contract(shots: list[Any], stage: str) -> list[dict[str, Any]]:
    required_text_fields = ("time_range", "description", "image_prompt", "negative_prompt")
    normalized: list[dict[str, Any]] = []
    for index, shot in enumerate(shots):
        if not isinstance(shot, dict):
            raise ValueError(f"{stage} shots[{index}] must be an object")
        current = dict(shot)
        for field in required_text_fields:
            if field not in current:
                raise ValueError(f"{stage} shots[{index}] missing required field: {field}")
            value = current[field]
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{stage} shots[{index}] field {field} must be a non-empty string")
        if "comfyui_inputs" not in current:
            raise ValueError(f"{stage} shots[{index}] missing required field: comfyui_inputs")
        if not isinstance(current["comfyui_inputs"], dict):
            raise ValueError(f"{stage} shots[{index}] field comfyui_inputs must be an object")
        panels = current.get("grid_panel_prompts")
        if panels is not None:
            if (
                not isinstance(panels, list)
                or len(panels) != 4
                or not all(isinstance(item, str) and item.strip() for item in panels)
            ):
                raise ValueError(
                    f"{stage} shots[{index}] field grid_panel_prompts must contain exactly four non-empty strings"
                )
            current["grid_panel_prompts"] = [item.strip() for item in panels]
        normalized.append(current)
    return normalized
