from __future__ import annotations

import math
import re
from collections.abc import Mapping, Sequence
from typing import Any

from .models import SegmentRenderState


TIME_RANGE_PATTERN = re.compile(r"\s*(\d+)\s*-\s*(\d+)\s*s?\s*")


def parse_time_range(value: str) -> tuple[int, int]:
    match = TIME_RANGE_PATTERN.fullmatch(str(value or ""))
    if not match:
        raise ValueError(f"Invalid time_range: {value}")
    start, end = (int(item) for item in match.groups())
    if end <= start:
        raise ValueError(f"time_range must increase: {value}")
    return start, end


def local_frame_indices(duration_seconds: int, fps: int) -> list[int]:
    if duration_seconds < 1 or fps < 1:
        raise ValueError("duration_seconds and fps must be positive")
    last = duration_seconds * fps - 1
    return [0, round(last / 3), round(last * 2 / 3), last]


def grid_panel_prompts_for_shot(
    shot: Mapping[str, Any],
) -> tuple[list[str], str]:
    supplied = shot.get("grid_panel_prompts")
    if (
        isinstance(supplied, list)
        and len(supplied) == 4
        and all(str(item).strip() for item in supplied)
    ):
        return [str(item).strip() for item in supplied], "model"
    base = str(shot.get("image_prompt") or shot.get("description") or "").strip()
    if not base:
        raise ValueError("segment shot requires image_prompt or description")
    return [
        f"开场建立：{base}",
        f"动作发展：{base}",
        f"情绪高潮：{base}",
        f"镜头收束：{base}",
    ], "derived"


def build_segment_render_plan(
    storyboard: Sequence[Mapping[str, Any]],
    *,
    target_duration_seconds: int,
    fps: int = 24,
) -> list[SegmentRenderState]:
    if not storyboard:
        raise ValueError("segment render plan requires at least one storyboard shot")
    authored_ranges = [parse_time_range(str(shot.get("time_range") or "")) for shot in storyboard]
    authored_durations = [end - start for start, end in authored_ranges]
    planned_durations = _planned_durations(authored_durations, target_duration_seconds)

    states: list[SegmentRenderState] = []
    render_start = 0
    for order, (shot, authored_range, duration) in enumerate(
        zip(storyboard, authored_ranges, planned_durations, strict=True),
        start=1,
    ):
        render_end = render_start + duration
        panels, panel_source = grid_panel_prompts_for_shot(shot)
        comfyui_inputs = shot.get("comfyui_inputs")
        if not isinstance(comfyui_inputs, Mapping):
            comfyui_inputs = {}
        strength = _normalized_strength(comfyui_inputs.get("strength", 0.7))
        states.append(
            SegmentRenderState(
                segment_id=f"shot-{order:03d}",
                shot_id=str(shot.get("shot_id") or order),
                order=order,
                authored_time_range=f"{authored_range[0]}-{authored_range[1]}s",
                render_time_range=f"{render_start}-{render_end}s",
                duration_seconds=duration,
                fps=fps,
                frame_count=duration * fps + 1,
                local_frame_indices=local_frame_indices(duration, fps),
                positive_prompt=str(
                    comfyui_inputs.get("positive")
                    or shot.get("image_prompt")
                    or shot.get("description")
                    or ""
                ).strip(),
                negative_prompt=str(
                    comfyui_inputs.get("negative")
                    or shot.get("negative_prompt")
                    or ""
                ).strip(),
                seed=int(comfyui_inputs.get("seed") or 0),
                strength=strength,
                grid_panel_prompts=panels,
                grid_prompt_source=panel_source,
            )
        )
        render_start = render_end
    return states


def _planned_durations(authored: list[int], target: int) -> list[int]:
    if target == 0 or target == sum(authored):
        return list(authored)
    if not 15 <= target <= 300:
        raise ValueError("target_duration_seconds must be 0 or between 15 and 300")
    if target < len(authored):
        raise ValueError("target duration is shorter than the segment count")

    remaining = target - len(authored)
    total = sum(authored)
    raw_extras = [duration / total * remaining for duration in authored]
    planned = [1 + math.floor(value) for value in raw_extras]
    remainder = target - sum(planned)
    ranked = sorted(
        range(len(authored)),
        key=lambda index: (-(raw_extras[index] - math.floor(raw_extras[index])), index),
    )
    for index in ranked[:remainder]:
        planned[index] += 1
    return planned


def _normalized_strength(value: Any) -> float:
    try:
        return min(1.0, max(0.0, float(value)))
    except (TypeError, ValueError):
        return 0.7
