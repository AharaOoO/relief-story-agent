from __future__ import annotations

import hashlib
import json
from typing import Any

from .ltx_workflow import detect_workflow_format, litegraph_to_api_prompt
from .models import WorkflowModelBinding


MODEL_INPUT_MARKERS = (
    "model",
    "ckpt",
    "checkpoint",
    "unet",
    "vae",
    "clip",
    "lora",
    "controlnet",
    "control_net",
    "text_encoder",
    "diffusion",
)
MODEL_FILE_SUFFIXES = (
    ".safetensors",
    ".ckpt",
    ".pt",
    ".pth",
    ".bin",
    ".gguf",
)


class WorkflowModelUnavailable(ValueError):
    def __init__(self, details: list[dict[str, Any]]):
        self.details = details
        summary = ", ".join(
            f"node {item['node_id']} {item['input_name']}={item['selected']}"
            for item in details
        )
        super().__init__(f"ComfyUI workflow model is unavailable: {summary}")


def workflow_fingerprint(workflow: dict[str, Any]) -> str:
    payload = json.dumps(
        workflow,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def build_workflow_model_manifest(
    workflow: dict[str, Any],
    object_info: dict[str, Any],
) -> list[WorkflowModelBinding]:
    api_prompt = (
        litegraph_to_api_prompt(workflow, object_info=object_info)
        if detect_workflow_format(workflow) == "litegraph"
        else workflow
    )
    bindings: list[WorkflowModelBinding] = []
    for node_id, node in api_prompt.items():
        if not isinstance(node, dict):
            continue
        class_type = str(node.get("class_type") or "")
        inputs = node.get("inputs") or {}
        if not class_type or not isinstance(inputs, dict):
            continue
        title = str((node.get("_meta") or {}).get("title") or "")
        for input_name, selected in inputs.items():
            if not isinstance(selected, str) or not selected.strip():
                continue
            choices = _input_choices(object_info.get(class_type), str(input_name))
            if not choices or not _is_model_input(str(input_name), selected, choices):
                continue
            bindings.append(
                WorkflowModelBinding(
                    node_id=str(node_id),
                    class_type=class_type,
                    title=title,
                    input_name=str(input_name),
                    selected=selected,
                    available=selected in choices,
                    choices=choices,
                )
            )
    return bindings


def validate_workflow_models(
    workflow: dict[str, Any],
    object_info: dict[str, Any],
) -> list[WorkflowModelBinding]:
    manifest = build_workflow_model_manifest(workflow, object_info)
    missing = [item.model_dump() for item in manifest if not item.available]
    if missing:
        raise WorkflowModelUnavailable(missing)
    return manifest


def _input_choices(node_info: Any, input_name: str) -> list[str]:
    if not isinstance(node_info, dict):
        return []
    input_groups = node_info.get("input") or {}
    if not isinstance(input_groups, dict):
        return []
    for group_name in ("required", "optional"):
        group = input_groups.get(group_name) or {}
        if not isinstance(group, dict) or input_name not in group:
            continue
        schema = group[input_name]
        if not isinstance(schema, (list, tuple)) or not schema:
            return []
        raw_choices = schema[0]
        if not isinstance(raw_choices, (list, tuple)):
            return []
        return [str(item) for item in raw_choices if isinstance(item, str)]
    return []


def _is_model_input(input_name: str, selected: str, choices: list[str]) -> bool:
    normalized = input_name.casefold()
    if any(marker in normalized for marker in MODEL_INPUT_MARKERS):
        return True
    values = [selected, *choices]
    return any(value.casefold().endswith(MODEL_FILE_SUFFIXES) for value in values)
