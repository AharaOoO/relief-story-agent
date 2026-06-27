from __future__ import annotations

import copy
import json
import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any
from urllib.parse import unquote


LTX_REQUIRED_JSON_KEYS = {"prompt", "frame_indices", "strengths", "duration_seconds"}

LITEGRAPH_NON_RUNTIME_NODE_TYPES = {
    "Bookmark (rgthree)",
    "Fast Actions Button (rgthree)",
    "Fast Groups Bypasser (rgthree)",
    "GetNode",
    "Label (rgthree)",
    "MarkdownNote",
    "Note",
    "SetNode",
}


@dataclass(frozen=True)
class LTXInjectionPoints:
    json_node_id: str
    seed_node_id: str | None = None
    filename_prefix_node_id: str | None = None
    grid_image_node_id: str | None = None
    grid_image_input: str = "image"
    grid_columns: int | None = None
    grid_rows: int | None = None


@dataclass(frozen=True)
class LTXWidgetPatchPoints:
    positive_prompt_node_ids: tuple[str, ...]
    negative_prompt_node_ids: tuple[str, ...] = ()
    seed_node_ids: tuple[str, ...] = ()
    filename_prefix_node_ids: tuple[str, ...] = ()
    image_node_ids: tuple[str, ...] = ()


def detect_workflow_format(workflow: dict[str, Any]) -> str:
    if isinstance(workflow.get("nodes"), list) and isinstance(workflow.get("links"), list):
        return "litegraph"
    if workflow and all(isinstance(node, dict) and "class_type" in node for node in workflow.values()):
        return "api"
    return "unknown"


def find_ltx_injection_points(workflow: dict[str, Any]) -> LTXInjectionPoints:
    if detect_workflow_format(workflow) != "litegraph":
        raise ValueError("LTX injection point detection requires a LiteGraph workflow")

    json_candidates: list[tuple[int, str]] = []
    seed_node_id: str | None = None
    filename_prefix_node_id: str | None = None
    node_types = {str(node.get("id")): str(node.get("type") or "") for node in workflow.get("nodes", [])}

    for node in workflow.get("nodes", []):
        node_id = str(node.get("id"))
        node_type = str(node.get("type") or "")

        if _node_has_ltx_json(node):
            json_candidates.append((_ltx_json_node_score(workflow, node, node_types), node_id))

        if seed_node_id is None and _has_widget_input(node, "noise_seed"):
            seed_node_id = node_id

        if filename_prefix_node_id is None and (
            node_type == "VHS_VideoCombine" or _has_widget_input(node, "filename_prefix")
        ):
            filename_prefix_node_id = node_id

    if not json_candidates:
        raise ValueError("Could not find a LiteGraph node containing the LTX prompt JSON")
    json_candidates.sort(reverse=True)
    grid_image_node_id, grid_columns, grid_rows = _find_grid_injection(workflow)

    return LTXInjectionPoints(
        json_node_id=json_candidates[0][1],
        seed_node_id=seed_node_id,
        filename_prefix_node_id=filename_prefix_node_id,
        grid_image_node_id=grid_image_node_id,
        grid_image_input="image",
        grid_columns=grid_columns,
        grid_rows=grid_rows,
    )


def find_ltx_widget_patch_points(workflow: dict[str, Any]) -> LTXWidgetPatchPoints:
    if detect_workflow_format(workflow) != "litegraph":
        raise ValueError("LTX widget patch detection requires a LiteGraph workflow")

    positive: list[str] = []
    negative: list[str] = []
    seeds: list[str] = []
    filename_prefixes: list[str] = []
    images: list[str] = []

    for node in workflow.get("nodes", []):
        node_id = str(node.get("id"))
        node_type = str(node.get("type") or "")
        label = _node_label(node)

        if _is_negative_prompt_node(node_type, label):
            negative.append(node_id)
        elif _is_positive_prompt_node(node_type, label):
            positive.append(node_id)

        if node_type == "RandomNoise":
            seeds.append(node_id)

        if node_type in {"SaveVideo", "VHS_VideoCombine"}:
            filename_prefixes.append(node_id)

        if node_type == "LoadImage":
            images.append(node_id)

    if not positive:
        raise ValueError("Could not find a LiteGraph positive prompt widget node")

    return LTXWidgetPatchPoints(
        positive_prompt_node_ids=tuple(positive),
        negative_prompt_node_ids=tuple(negative),
        seed_node_ids=tuple(seeds),
        filename_prefix_node_ids=tuple(filename_prefixes),
        image_node_ids=tuple(images),
    )


def litegraph_to_api_prompt(
    workflow: dict[str, Any],
    *,
    object_info: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if detect_workflow_format(workflow) != "litegraph":
        raise ValueError("Expected a LiteGraph workflow")

    expanded_links = _expand_kjnodes_set_get_links(workflow)
    links_by_id = {link[0]: link for link in expanded_links if isinstance(link, list) and len(link) >= 5}
    subgraph_definitions = _subgraph_definitions_by_id(workflow)
    subgraph_output_sources: dict[tuple[str, int], list[Any]] = {}
    prompt: dict[str, Any] = {}

    def resolve_link_source(link: Any) -> list[Any]:
        origin_id, origin_slot = _link_origin(link)
        return subgraph_output_sources.get((origin_id, origin_slot), [origin_id, origin_slot])

    for node in workflow.get("nodes", []):
        node_type = str(node.get("type") or "")
        if node_type in subgraph_definitions:
            _append_subgraph_prompt(
                prompt,
                outer_node=node,
                subgraph=subgraph_definitions[node_type],
                outer_links_by_id=links_by_id,
                resolve_outer_link_source=resolve_link_source,
                subgraph_output_sources=subgraph_output_sources,
                object_info=object_info,
            )

    for node in workflow.get("nodes", []):
        if _is_litegraph_non_runtime_node(node):
            continue
        if str(node.get("type") or "") in subgraph_definitions:
            continue
        node_id = str(node.get("id"))
        inputs = _litegraph_node_inputs(node, links_by_id, resolve_link_source, object_info)
        prompt[node_id] = {"class_type": node.get("type"), "inputs": inputs}
        title = node.get("title")
        if title:
            prompt[node_id]["_meta"] = {"title": title}

    return prompt


def _is_litegraph_non_runtime_node(node: dict[str, Any]) -> bool:
    return str(node.get("type") or "") in LITEGRAPH_NON_RUNTIME_NODE_TYPES


def _litegraph_node_inputs(
    node: dict[str, Any],
    links_by_id: dict[Any, Any],
    resolve_link_source,
    object_info: dict[str, Any] | None,
) -> dict[str, Any]:
    inputs: dict[str, Any] = {}
    for input_index, input_spec in enumerate(node.get("inputs") or []):
        name = input_spec.get("name")
        if not name:
            continue

        link_id = input_spec.get("link")
        if link_id is not None and link_id in links_by_id:
            inputs[name] = resolve_link_source(links_by_id[link_id])
            continue

        if "widget" in input_spec:
            value_found, value = _read_widget_value(node, name, input_index)
            if value_found and name != "videopreview":
                inputs[name] = value

    _apply_known_widget_values(node, inputs)
    _apply_object_info_widget_values(node, inputs, object_info)
    return inputs


def _subgraph_definitions_by_id(workflow: dict[str, Any]) -> dict[str, dict[str, Any]]:
    raw_subgraphs = (workflow.get("definitions") or {}).get("subgraphs") or []
    if isinstance(raw_subgraphs, dict):
        subgraphs = raw_subgraphs.values()
    else:
        subgraphs = raw_subgraphs
    return {
        str(subgraph.get("id")): subgraph
        for subgraph in subgraphs
        if isinstance(subgraph, dict) and subgraph.get("id")
    }


def _append_subgraph_prompt(
    prompt: dict[str, Any],
    *,
    outer_node: dict[str, Any],
    subgraph: dict[str, Any],
    outer_links_by_id: dict[Any, Any],
    resolve_outer_link_source,
    subgraph_output_sources: dict[tuple[str, int], list[Any]],
    object_info: dict[str, Any] | None,
) -> None:
    outer_id = str(outer_node.get("id"))
    input_node_id = str((subgraph.get("inputNode") or {}).get("id"))
    output_node_id = str((subgraph.get("outputNode") or {}).get("id"))
    subgraph_links_by_id = {
        _link_id(link): link
        for link in subgraph.get("links", [])
        if _link_id(link) is not None
    }
    outer_input_sources: dict[int, list[Any]] = {}
    for input_index, input_spec in enumerate(outer_node.get("inputs") or []):
        link_id = input_spec.get("link")
        if link_id is not None and link_id in outer_links_by_id:
            outer_input_sources[input_index] = resolve_outer_link_source(outer_links_by_id[link_id])

    def resolve_subgraph_link_source(link: Any) -> list[Any] | None:
        origin_id, origin_slot = _link_origin(link)
        if origin_id == input_node_id:
            return outer_input_sources.get(origin_slot)
        return [_subgraph_prompt_node_id(outer_id, origin_id), origin_slot]

    for link in subgraph.get("links", []):
        target_id, target_slot = _link_target(link)
        if target_id == output_node_id:
            source = resolve_subgraph_link_source(link)
            if source is not None:
                subgraph_output_sources[(outer_id, target_slot)] = source

    for inner_node in subgraph.get("nodes", []):
        if _is_litegraph_non_runtime_node(inner_node):
            continue
        inner_id = _subgraph_prompt_node_id(outer_id, str(inner_node.get("id")))
        inputs = _litegraph_node_inputs(
            inner_node,
            subgraph_links_by_id,
            resolve_subgraph_link_source,
            object_info,
        )
        prompt[inner_id] = {"class_type": inner_node.get("type"), "inputs": inputs}
        title = inner_node.get("title")
        if title:
            prompt[inner_id]["_meta"] = {"title": title}


def _subgraph_prompt_node_id(outer_id: str, inner_id: str) -> str:
    return f"{outer_id}:{inner_id}"


def _link_id(link: Any) -> Any:
    if isinstance(link, dict):
        return link.get("id")
    if isinstance(link, list) and link:
        return link[0]
    return None


def _link_origin(link: Any) -> tuple[str, int]:
    if isinstance(link, dict):
        return str(link.get("origin_id")), int(link.get("origin_slot") or 0)
    return str(link[1]), int(link[2])


def _link_target(link: Any) -> tuple[str, int]:
    if isinstance(link, dict):
        return str(link.get("target_id")), int(link.get("target_slot") or 0)
    return str(link[3]), int(link[4])


def _expand_kjnodes_set_get_links(workflow: dict[str, Any]) -> list[list[Any]]:
    nodes_by_id = {str(node.get("id")): node for node in workflow.get("nodes", [])}
    links_by_id = {
        link[0]: link for link in workflow.get("links", []) if isinstance(link, list) and len(link) >= 5
    }
    set_sources: dict[str, tuple[Any, Any]] = {}

    for node in workflow.get("nodes", []):
        if node.get("type") != "SetNode":
            continue
        name = _first_widget_value(node)
        inputs = node.get("inputs") or []
        input_link_id = inputs[0].get("link") if inputs else None
        if name is None or input_link_id not in links_by_id:
            continue
        source_link = links_by_id[input_link_id]
        set_sources[str(name)] = (source_link[1], source_link[2])

    expanded: list[list[Any]] = []
    for link in workflow.get("links", []):
        if not isinstance(link, list) or len(link) < 5:
            continue
        copied = list(link)
        origin_node = nodes_by_id.get(str(copied[1]))
        if origin_node and origin_node.get("type") == "GetNode":
            name = _first_widget_value(origin_node)
            if name is not None and str(name) in set_sources:
                copied[1], copied[2] = set_sources[str(name)]
        expanded.append(copied)
    return expanded


def patch_ltx_litegraph_workflow(
    workflow: dict[str, Any],
    *,
    ltx_payload: dict[str, Any],
    seed: int | None = None,
    filename_prefix: str | None = None,
    grid_image_filename: str | None = None,
    object_info: dict[str, Any] | None = None,
) -> dict[str, Any]:
    patched = copy.deepcopy(workflow)
    points = find_ltx_injection_points(patched)

    if points.grid_image_node_id:
        if not grid_image_filename:
            raise ValueError("LTX grid workflow requires an uploaded grid image filename")
        image_node = _find_node(patched, points.grid_image_node_id)
        _write_widget_value(image_node, points.grid_image_input, grid_image_filename)

    json_node = _find_node(patched, points.json_node_id)
    _write_widget_value(json_node, "text", json.dumps(ltx_payload, ensure_ascii=False))

    if seed is not None and points.seed_node_id is not None:
        seed_node = _find_node(patched, points.seed_node_id)
        _write_widget_value(seed_node, "noise_seed", int(seed))

    if filename_prefix is not None and points.filename_prefix_node_id is not None:
        prefix_node = _find_node(patched, points.filename_prefix_node_id)
        _write_widget_value(prefix_node, "filename_prefix", filename_prefix)

    return litegraph_to_api_prompt(patched, object_info=object_info)


def patch_ltx_widget_workflow(
    workflow: dict[str, Any],
    *,
    ltx_payload: dict[str, Any],
    seed: int | None = None,
    filename_prefix: str | None = None,
    image_filename: str | None = None,
    object_info: dict[str, Any] | None = None,
) -> dict[str, Any]:
    patched = copy.deepcopy(workflow)
    points = find_ltx_widget_patch_points(patched)

    if points.image_node_ids:
        if not image_filename:
            raise ValueError("LTX widget workflow requires an uploaded image filename")
        for node_id in points.image_node_ids:
            _write_widget_value(_find_node(patched, node_id), "image", image_filename)

    prompt = str(ltx_payload.get("prompt") or "")
    negative_prompt = str(ltx_payload.get("negative_prompt") or "")
    for node_id in points.positive_prompt_node_ids:
        _write_prompt_widget(_find_node(patched, node_id), prompt)
    for node_id in points.negative_prompt_node_ids:
        _write_prompt_widget(_find_node(patched, node_id), negative_prompt)

    if seed is not None:
        for node_id in points.seed_node_ids:
            _write_widget_value(_find_node(patched, node_id), "noise_seed", int(seed))

    if filename_prefix is not None:
        for node_id in points.filename_prefix_node_ids:
            _write_widget_value(_find_node(patched, node_id), "filename_prefix", filename_prefix)

    return litegraph_to_api_prompt(patched, object_info=object_info)


def build_ltx_payload_from_storyboard(
    storyboard: list[dict[str, Any]],
    *,
    duration_seconds: int,
    fps: int = 24,
    max_keyframes: int = 4,
) -> dict[str, Any]:
    selected_shots = _select_balanced_keyframes(storyboard, max_keyframes=max_keyframes)
    frame_min = 0
    frame_max = max(0, int(duration_seconds) * int(fps) - 1)
    frame_indices: list[int] = []
    strengths: list[float] = []
    ltx_shots: list[dict[str, Any]] = []
    keyframe_summaries: list[dict[str, Any]] = []
    prompt_parts: list[str] = []
    negative_parts: list[str] = []
    adjusted_frame_count = 0
    adjusted_strength_count = 0
    fallback_strength_count = 0

    for index, shot in enumerate(selected_shots):
        start_second = _parse_start_second(str(shot.get("time_range") or ""), fallback=index * duration_seconds / max(1, max_keyframes))
        requested_frame_index = round(start_second * fps)
        clamped_frame_index = _clamp_int(requested_frame_index, frame_min, frame_max)
        frame_index = _make_strictly_increasing_frame_index(
            clamped_frame_index,
            previous_frame_index=frame_indices[-1] if frame_indices else None,
            frame_max=frame_max,
        )
        frame_index_adjusted = frame_index != clamped_frame_index
        if frame_index_adjusted:
            adjusted_frame_count += 1
        requested_strength = (shot.get("comfyui_inputs") or {}).get("strength", _default_strength(index))
        strength, strength_adjusted, strength_fallback = _normalize_strength(
            requested_strength,
            fallback=_default_strength(index),
        )
        if strength_adjusted:
            adjusted_strength_count += 1
        if strength_fallback:
            fallback_strength_count += 1
        description = str(shot.get("image_prompt") or shot.get("description") or "").strip()
        negative_prompt = str(shot.get("negative_prompt") or "").strip()

        frame_indices.append(frame_index)
        strengths.append(strength)
        if description:
            prompt_parts.append(description)
        if negative_prompt:
            negative_parts.append(negative_prompt)
        ltx_shots.append(
            {
                "shot_id": shot.get("shot_id", index + 1),
                "time_range": shot.get("time_range", ""),
                "requested_frame_index": requested_frame_index,
                "frame_index": frame_index,
                "frame_index_clamped": clamped_frame_index != requested_frame_index,
                "frame_index_adjusted": frame_index_adjusted,
                "requested_strength": requested_strength,
                "strength": strength,
                "strength_adjusted": strength_adjusted,
                "description": shot.get("description", ""),
                "image_prompt": description,
            }
        )
        keyframe_summaries.append(
            {
                "slot": index + 1,
                "shot_id": shot.get("shot_id", index + 1),
                "time_range": shot.get("time_range", ""),
                "requested_frame_index": requested_frame_index,
                "frame_index": frame_index,
                "frame_index_clamped": clamped_frame_index != requested_frame_index,
                "frame_index_adjusted": frame_index_adjusted,
                "requested_strength": requested_strength,
                "strength": strength,
                "strength_adjusted": strength_adjusted,
            }
        )

    return {
        "prompt": _join_unique(prompt_parts),
        "negative_prompt": _join_unique(negative_parts)
        or "high stimulation, intense conflict, horror, violence, shouting, distorted faces, low quality",
        "frame_indices": ",".join(str(value) for value in frame_indices),
        "strengths": ",".join(_format_float(value) for value in strengths),
        "duration_seconds": int(duration_seconds),
        "fps": int(fps),
        "keyframe_selection": {
            "strategy": "balanced_timeline",
            "source_shot_count": len(storyboard),
            "selected_shot_ids": [shot.get("shot_id", index + 1) for index, shot in enumerate(selected_shots)],
            "max_keyframes": int(max_keyframes),
            "frame_index_clamp": {"min": frame_min, "max": frame_max},
            "frame_index_order": {
                "strategy": "preserve_story_order_strictly_increasing",
                "strictly_increasing": _is_strictly_increasing(frame_indices),
                "adjusted_count": adjusted_frame_count,
            },
            "strength_normalization": {
                "range": {"min": 0, "max": 1},
                "adjusted_count": adjusted_strength_count,
                "fallback_count": fallback_strength_count,
            },
            "keyframes": keyframe_summaries,
        },
        "shots": ltx_shots,
    }


def _clamp_int(value: int, lower: int, upper: int) -> int:
    return max(lower, min(upper, value))


def _make_strictly_increasing_frame_index(
    value: int,
    *,
    previous_frame_index: int | None,
    frame_max: int,
) -> int:
    if previous_frame_index is None or value > previous_frame_index:
        return value
    return _clamp_int(previous_frame_index + 1, 0, frame_max)


def _is_strictly_increasing(values: list[int]) -> bool:
    return all(current > previous for previous, current in zip(values, values[1:]))


def _normalize_strength(value: Any, *, fallback: float) -> tuple[float, bool, bool]:
    fallback_used = False
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        parsed = float(fallback)
        fallback_used = True
    normalized = _clamp_float(parsed, 0.0, 1.0)
    return normalized, fallback_used or normalized != parsed, fallback_used


def _clamp_float(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def _select_balanced_keyframes(
    storyboard: list[dict[str, Any]],
    *,
    max_keyframes: int,
) -> list[dict[str, Any]]:
    if max_keyframes <= 0:
        return []
    if len(storyboard) <= max_keyframes:
        return list(storyboard)
    if max_keyframes == 1:
        return [storyboard[0]]

    last_index = len(storyboard) - 1
    selected_indices: list[int] = []
    for index in range(max_keyframes):
        selected = int(index * last_index / (max_keyframes - 1))
        if selected not in selected_indices:
            selected_indices.append(selected)
    while len(selected_indices) < max_keyframes:
        for candidate in range(len(storyboard)):
            if candidate not in selected_indices:
                selected_indices.append(candidate)
                break
    return [storyboard[index] for index in selected_indices[:max_keyframes]]


def _node_has_ltx_json(node: dict[str, Any]) -> bool:
    for value in _iter_widget_values(node):
        if not isinstance(value, str):
            continue
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict) and LTX_REQUIRED_JSON_KEYS.issubset(parsed.keys()):
            return True
    return False


def _ltx_json_node_score(workflow: dict[str, Any], node: dict[str, Any], node_types: dict[str, str]) -> int:
    node_id = str(node.get("id"))
    node_type = str(node.get("type") or "")
    score = 0
    if node_type == "JWString":
        score += 100
    if _feeds_parse_json_node(workflow, node_id, node_types):
        score += 50
    if node_type == "CLIPTextEncode":
        score -= 25
    return score


def _feeds_parse_json_node(workflow: dict[str, Any], source_node_id: str, node_types: dict[str, str]) -> bool:
    for link in workflow.get("links", []):
        if not isinstance(link, list) or len(link) < 4:
            continue
        if str(link[1]) == source_node_id and node_types.get(str(link[3])) == "ParseJsonNode":
            return True
    return False


def _find_grid_injection(workflow: dict[str, Any]) -> tuple[str | None, int | None, int | None]:
    nodes = {str(node.get("id")): node for node in workflow.get("nodes", [])}
    links = [link for link in workflow.get("links", []) if isinstance(link, list) and len(link) >= 5]
    guides = [node for node in nodes.values() if node.get("type") == "TD_LTXVAddGuideFromGrid"]
    if not guides:
        return None, None, None
    if len(guides) != 1:
        raise ValueError("LTX workflow must contain exactly one TD_LTXVAddGuideFromGrid node")
    guide = guides[0]
    guide_id = str(guide.get("id"))
    guide_inputs = guide.get("inputs") or []
    grid_input = next(
        (item for item in guide_inputs if item.get("name") == "grid_image"),
        None,
    )
    if not grid_input:
        raise ValueError("grid guide is missing grid_image input")
    grid_input_index = guide_inputs.index(grid_input)
    incoming = [
        link
        for link in links
        if str(link[3]) == guide_id and int(link[4]) == grid_input_index
    ]
    load_ids = {
        str(link[1])
        for link in incoming
        if nodes.get(str(link[1]), {}).get("type") == "LoadImage"
    }
    if len(load_ids) != 1:
        raise ValueError("grid_image must resolve to exactly one LoadImage node")
    columns = _read_required_int_widget(guide, "columns")
    rows = _read_required_int_widget(guide, "rows")
    return next(iter(load_ids)), columns, rows


def _read_required_int_widget(node: dict[str, Any], name: str) -> int:
    inputs = node.get("inputs") or []
    index = next((i for i, item in enumerate(inputs) if item.get("name") == name), None)
    if index is None:
        raise ValueError(f"grid guide is missing {name} widget")
    found, value = _read_widget_value(node, name, index)
    if not found:
        raise ValueError(f"grid guide is missing {name} value")
    return int(value)


def _has_widget_input(node: dict[str, Any], name: str) -> bool:
    return any(
        input_spec.get("name") == name and "widget" in input_spec for input_spec in node.get("inputs") or []
    )


def _iter_widget_values(node: dict[str, Any]) -> list[Any]:
    values = node.get("widgets_values")
    if isinstance(values, dict):
        return list(values.values())
    if isinstance(values, list):
        return values
    return []


def _first_widget_value(node: dict[str, Any]) -> Any:
    values = _iter_widget_values(node)
    if not values:
        return None
    return values[0]


def _read_widget_value(node: dict[str, Any], widget_name: str, widget_input_index: int) -> tuple[bool, Any]:
    values = node.get("widgets_values")
    if isinstance(values, dict):
        if widget_name in values:
            return True, values[widget_name]
        return False, None

    if not isinstance(values, list):
        return False, None

    widget_names = [
        input_spec.get("name")
        for input_spec in node.get("inputs") or []
        if "widget" in input_spec and input_spec.get("name")
    ]
    if widget_name in widget_names:
        index = widget_names.index(widget_name)
        if index < len(values):
            return True, values[index]
    if widget_input_index < len(values):
        return True, values[widget_input_index]
    return False, None


def _write_widget_value(node: dict[str, Any], widget_name: str, value: Any) -> None:
    values = node.setdefault("widgets_values", [])
    if isinstance(values, dict):
        values[widget_name] = value
        return

    if not isinstance(values, list):
        node["widgets_values"] = [value]
        return

    widget_names = [
        input_spec.get("name")
        for input_spec in node.get("inputs") or []
        if "widget" in input_spec and input_spec.get("name")
    ]
    if widget_name in widget_names:
        index = widget_names.index(widget_name)
    elif widget_name in _KNOWN_WIDGET_INPUT_NAMES.get(str(node.get("type") or ""), ()):
        index = _KNOWN_WIDGET_INPUT_NAMES[str(node.get("type") or "")].index(widget_name)
    else:
        index = 0
    while len(values) <= index:
        values.append(None)
    values[index] = value


def _find_node(workflow: dict[str, Any], node_id: str) -> dict[str, Any]:
    for node in workflow.get("nodes", []):
        if str(node.get("id")) == str(node_id):
            return node
    raise KeyError(node_id)


def _parse_start_second(time_range: str, *, fallback: float) -> float:
    match = re.search(r"(\d+(?:\.\d+)?)", time_range)
    if not match:
        return fallback
    return float(match.group(1))


def _default_strength(index: int) -> float:
    defaults = [0.72, 0.74, 0.82, 0.84]
    if index < len(defaults):
        return defaults[index]
    return defaults[-1]


def _format_float(value: float) -> str:
    return f"{value:.2f}".rstrip("0").rstrip(".")


def _join_unique(parts: list[str]) -> str:
    seen: set[str] = set()
    unique: list[str] = []
    for part in parts:
        if not part or part in seen:
            continue
        seen.add(part)
        unique.append(part)
    return "；".join(unique)


def _node_label(node: dict[str, Any]) -> str:
    parts = [
        str(node.get("type") or ""),
        str(node.get("title") or ""),
    ]
    properties = node.get("properties") or {}
    if isinstance(properties, dict):
        parts.append(str(properties.get("Node name for S&R") or ""))
    return " ".join(parts).lower()


def _is_positive_prompt_node(node_type: str, label: str) -> bool:
    if "negative" in label:
        return False
    if node_type in {"CLIPTextEncode", "GemmaAPITextEncode"}:
        return "positive" in label or "prompt" in label
    if node_type in {"PrimitiveStringMultiline", "PrimitiveString"}:
        return "prompt" in label
    return False


def _is_negative_prompt_node(node_type: str, label: str) -> bool:
    return node_type in {"CLIPTextEncode", "GemmaAPITextEncode"} and "negative" in label


def _write_prompt_widget(node: dict[str, Any], value: str) -> None:
    widget_name = "prompt" if node.get("type") == "GemmaAPITextEncode" else "text"
    _write_widget_value(node, widget_name, value)


_KNOWN_WIDGET_INPUT_NAMES: dict[str, tuple[str, ...]] = {
    "CLIPTextEncode": ("text",),
    "GemmaAPITextEncode": ("api_key", "prompt", "_legacy_model_slot", "ckpt_name"),
    "JWString": ("text",),
    "PrimitiveString": ("value",),
    "PrimitiveStringMultiline": ("value",),
    "RandomNoise": ("noise_seed", "control_after_generate"),
    "LoadImage": ("image", "upload"),
    "SaveVideo": ("filename_prefix", "format", "codec"),
    "VHS_VideoCombine": ("filename_prefix",),
}


def _apply_known_widget_values(node: dict[str, Any], inputs: dict[str, Any]) -> None:
    values = _iter_widget_values(node)
    if not values:
        return
    widget_names = _KNOWN_WIDGET_INPUT_NAMES.get(str(node.get("type") or ""))
    if not widget_names:
        return
    linked_inputs = {
        str(input_spec.get("name"))
        for input_spec in node.get("inputs") or []
        if input_spec.get("link") is not None
    }
    for index, name in enumerate(widget_names):
        if index >= len(values) or name in inputs or name in linked_inputs:
            continue
        if name == "upload" or name.startswith("_"):
            continue
        inputs[name] = values[index]


def _apply_object_info_widget_values(
    node: dict[str, Any],
    inputs: dict[str, Any],
    object_info: dict[str, Any] | None,
) -> None:
    node_type = str(node.get("type") or "")
    if not object_info or node_type in _KNOWN_WIDGET_INPUT_NAMES:
        return
    values = _iter_widget_values(node)
    if not values:
        return
    class_info = object_info.get(node_type)
    if not isinstance(class_info, dict):
        return
    input_info = class_info.get("input") or {}
    if not isinstance(input_info, dict):
        return
    fields = _object_info_fields(input_info)
    frontend_widget_names = _frontend_widget_names(node)
    value_index = 0

    for name, spec in fields:
        if _is_dynamic_combo_spec(spec):
            if value_index >= len(values):
                continue
            selected = _coerce_object_info_value(spec, values[value_index])
            value_index += 1
            if name not in inputs:
                inputs[name] = selected
            for nested_name, nested_spec in _dynamic_option_fields(spec, selected):
                dotted_name = f"{name}.{nested_name}"
                if dotted_name in inputs:
                    if not _is_link_value(inputs[dotted_name]):
                        inputs[dotted_name] = _coerce_object_info_value(nested_spec, inputs[dotted_name])
                    if value_index < len(values):
                        value_index += 1
                    continue
                if nested_name in inputs:
                    linked_value = inputs.pop(nested_name)
                    inputs[dotted_name] = (
                        linked_value
                        if _is_link_value(linked_value)
                        else _coerce_object_info_value(nested_spec, linked_value)
                    )
                    if value_index < len(values):
                        value_index += 1
                    continue
                if value_index < len(values):
                    inputs[dotted_name] = _coerce_object_info_value(nested_spec, values[value_index])
                    value_index += 1
            continue

        if name in inputs:
            if not _is_link_value(inputs[name]):
                inputs[name] = _coerce_object_info_value(spec, inputs[name])
            if name in frontend_widget_names and value_index < len(values):
                value_index += 1
            continue
        if value_index < len(values) and _object_info_field_looks_widget(spec):
            inputs[name] = _coerce_object_info_value(spec, values[value_index])
            value_index += 1


def _object_info_fields(input_info: dict[str, Any]) -> list[tuple[str, Any]]:
    fields: list[tuple[str, Any]] = []
    for section_name in ("required", "optional"):
        section = input_info.get(section_name) or {}
        if isinstance(section, dict):
            fields.extend((str(name), spec) for name, spec in section.items())
    return fields


def _frontend_widget_names(node: dict[str, Any]) -> set[str]:
    return {
        str(input_spec.get("name"))
        for input_spec in node.get("inputs") or []
        if "widget" in input_spec and input_spec.get("name")
    }


def _object_info_field_looks_widget(spec: Any) -> bool:
    if not isinstance(spec, list) or not spec:
        return False
    value_type = spec[0]
    if isinstance(value_type, list):
        return True
    return str(value_type) not in {
        "AUDIO",
        "CLIP",
        "CONDITIONING",
        "IMAGE",
        "LATENT",
        "MASK",
        "MODEL",
        "NOISE",
        "VAE",
        "VIDEO",
    }


def _is_dynamic_combo_spec(spec: Any) -> bool:
    return isinstance(spec, list) and len(spec) > 1 and str(spec[0]).startswith("COMFY_DYNAMICCOMBO")


def _dynamic_option_fields(spec: Any, selected: Any) -> list[tuple[str, Any]]:
    if not isinstance(spec, list) or len(spec) < 2 or not isinstance(spec[1], dict):
        return []
    options = spec[1].get("options") or []
    for option in options:
        if not isinstance(option, dict) or option.get("key") != selected:
            continue
        inputs = option.get("inputs") or {}
        required = inputs.get("required") or {}
        if isinstance(required, dict):
            return [(str(name), field_spec) for name, field_spec in required.items()]
    return []


def _is_link_value(value: Any) -> bool:
    return isinstance(value, list) and len(value) == 2 and isinstance(value[0], str) and isinstance(value[1], int)


def _coerce_object_info_value(spec: Any, value: Any) -> Any:
    options = _object_info_options(spec)
    if not options or value in options:
        return value
    if not isinstance(value, str):
        return value
    best = _best_combo_option(value, options)
    return best if best is not None else value


def _object_info_options(spec: Any) -> list[Any]:
    if not isinstance(spec, list) or not spec:
        return []
    if isinstance(spec[0], list):
        return list(spec[0])
    if len(spec) > 1 and isinstance(spec[1], dict):
        options = spec[1].get("options") or []
        if isinstance(options, list):
            return [option.get("key") if isinstance(option, dict) else option for option in options]
    return []


def _best_combo_option(value: str, options: list[Any]) -> str | None:
    best_option: str | None = None
    best_score = 0.0
    for option in options:
        if not isinstance(option, str):
            continue
        score = _combo_match_score(value, option)
        if score > best_score:
            best_score = score
            best_option = option
    return best_option if best_score >= 0.9 else None


def _combo_match_score(source: str, candidate: str) -> float:
    source_key = _combo_key(source)
    candidate_key = _combo_key(candidate)
    if not source_key or not candidate_key:
        return 0.0
    if source_key == candidate_key:
        return 10.0
    score = SequenceMatcher(None, source_key, candidate_key).ratio()
    if source_key in candidate_key or candidate_key in source_key:
        score += 2.0

    source_tokens = _combo_tokens(source)
    candidate_tokens = _combo_tokens(candidate)
    if source_tokens:
        overlap = source_tokens & candidate_tokens
        score += len(overlap) / len(source_tokens)
        score += 0.35 * len(overlap & _ASSET_ANCHOR_TOKENS)
    return score


def _combo_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", unquote(value).lower())


def _combo_tokens(value: str) -> set[str]:
    decoded = unquote(value).lower()
    compact = _combo_key(decoded)
    tokens = set(re.findall(r"[a-z]+|\d+[a-z]*", decoded))
    for anchor in _ASSET_ANCHOR_TOKENS:
        if anchor in compact:
            tokens.add(anchor)
    if "ltx23" in compact or re.search(r"ltx[^a-z0-9]*2[^a-z0-9]*3", decoded):
        tokens.add("ltx23")
    tokens.update(re.findall(r"\d+b", decoded))
    return {token for token in tokens if token not in _GENERIC_ASSET_TOKENS}


_ASSET_ANCHOR_TOKENS = {
    "clip",
    "gemma",
    "ltx",
    "ltx23",
    "qwen",
    "t5",
    "umt5",
    "wan",
}

_GENERIC_ASSET_TOKENS = {
    "auto",
    "bf16",
    "ckpt",
    "comfy",
    "default",
    "dev",
    "dynamic",
    "fp16",
    "fp8",
    "lora",
    "model",
    "rank",
    "safetensors",
}
