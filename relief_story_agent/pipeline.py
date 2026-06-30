from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


StageCategory = Literal["model", "validation", "asset", "artifact", "external"]


@dataclass(frozen=True)
class StageSpec:
    stage_id: str
    category: StageCategory
    retryable: bool
    side_effects: tuple[str, ...] = ()
    outputs: tuple[str, ...] = ()


CANONICAL_STAGE_ORDER = (
    "chief_screenwriter",
    "deepseek_polish",
    "quality_gate",
    "gpt_prompt_writer",
    "gpt_prompt_audit",
    "gpt_prompt_reviser",
    "final_prompts",
    "four_grid_asset",
    "artifacts",
    "comfyui",
)

BASE_RUNTIME_STAGE_ORDER = (
    "chief_screenwriter",
    "deepseek_polish",
    "quality_gate",
    "gpt_prompt_writer",
    "gpt_prompt_audit",
    "final_prompts",
)

MODEL_STAGE_IDS = (
    "chief_screenwriter",
    "deepseek_polish",
    "quality_gate",
    "gpt_prompt_writer",
    "gpt_prompt_audit",
    "gpt_prompt_reviser",
)

STAGE_SPECS = {
    "chief_screenwriter": StageSpec(
        stage_id="chief_screenwriter",
        category="model",
        retryable=True,
        side_effects=("model_call",),
        outputs=("core_candidates", "selected_core", "draft_script"),
    ),
    "deepseek_polish": StageSpec(
        stage_id="deepseek_polish",
        category="model",
        retryable=True,
        side_effects=("model_call",),
        outputs=("script",),
    ),
    "quality_gate": StageSpec(
        stage_id="quality_gate",
        category="model",
        retryable=True,
        side_effects=("model_call",),
        outputs=("quality_gate",),
    ),
    "gpt_prompt_writer": StageSpec(
        stage_id="gpt_prompt_writer",
        category="model",
        retryable=True,
        side_effects=("model_call",),
        outputs=("storyboard",),
    ),
    "gpt_prompt_audit": StageSpec(
        stage_id="gpt_prompt_audit",
        category="model",
        retryable=True,
        side_effects=("model_call",),
        outputs=("prompt_audit", "final_storyboard"),
    ),
    "gpt_prompt_reviser": StageSpec(
        stage_id="gpt_prompt_reviser",
        category="model",
        retryable=True,
        side_effects=("model_call",),
        outputs=("final_storyboard",),
    ),
    "final_prompts": StageSpec(
        stage_id="final_prompts",
        category="validation",
        retryable=False,
        outputs=("final_storyboard",),
    ),
    "four_grid_asset": StageSpec(
        stage_id="four_grid_asset",
        category="asset",
        retryable=True,
        side_effects=("image_generation", "comfyui_upload"),
        outputs=("grid_image_asset", "grid_image_replacements"),
    ),
    "artifacts": StageSpec(
        stage_id="artifacts",
        category="artifact",
        retryable=True,
        side_effects=("filesystem_write",),
        outputs=("artifact_manifest",),
    ),
    "comfyui": StageSpec(
        stage_id="comfyui",
        category="external",
        retryable=True,
        side_effects=("comfyui_prompt",),
        outputs=("comfyui_prompt_ids", "comfyui_outputs"),
    ),
}

RECOVERABLE_STAGE_ORDER = tuple(
    stage_id for stage_id in CANONICAL_STAGE_ORDER if stage_id != "gpt_prompt_reviser"
)


def get_stage_spec(stage_id: str) -> StageSpec:
    return STAGE_SPECS[stage_id]


def build_pipeline_schema() -> dict:
    return {
        "schema_version": "1",
        "canonical_stage_order": list(CANONICAL_STAGE_ORDER),
        "runtime_variants": {
            "base": list(BASE_RUNTIME_STAGE_ORDER),
            "recoverable": list(RECOVERABLE_STAGE_ORDER),
            "model": list(MODEL_STAGE_IDS),
            "maximal": list(CANONICAL_STAGE_ORDER),
        },
        "invariants": {
            "fixed_order": True,
            "prompt_reviser_max_auto_attempts": 1,
            "quality_gate_after": "deepseek_polish",
            "comfyui_workflow_generation": "never",
            "comfyui_enqueue_boundary": "/prompt",
        },
        "stages": [
            _stage_schema(stage_id, index)
            for index, stage_id in enumerate(CANONICAL_STAGE_ORDER)
        ],
    }


def _stage_schema(stage_id: str, index: int) -> dict:
    spec = STAGE_SPECS[stage_id]
    return {
        "stage_id": spec.stage_id,
        "index": index,
        "category": spec.category,
        "retryable": spec.retryable,
        "automatic": _automatic_policy(stage_id),
        "runtime_presence": _runtime_presence(stage_id),
        "side_effects": list(spec.side_effects),
        "outputs": list(spec.outputs),
        "previous_stage": CANONICAL_STAGE_ORDER[index - 1] if index else "",
        "next_stage": (
            CANONICAL_STAGE_ORDER[index + 1]
            if index < len(CANONICAL_STAGE_ORDER) - 1
            else ""
        ),
    }


def _automatic_policy(stage_id: str) -> str:
    if stage_id == "gpt_prompt_reviser":
        return "conditional_once"
    return "always_when_present"


def _runtime_presence(stage_id: str) -> str:
    if stage_id == "gpt_prompt_reviser":
        return "when_prompt_audit_fails_first_pass"
    if stage_id == "four_grid_asset":
        return "when_ltx_grid_asset_required"
    if stage_id == "artifacts":
        return "when_output_root_or_grid_asset_present"
    if stage_id == "comfyui":
        return "when_comfyui_enabled"
    return "base"


def stage_ids_for_run(
    *,
    requires_grid_asset: bool,
    writes_artifacts: bool,
    comfyui_enabled: bool,
) -> list[str]:
    stages = list(BASE_RUNTIME_STAGE_ORDER)
    if requires_grid_asset:
        stages.append("four_grid_asset")
    if writes_artifacts:
        stages.append("artifacts")
    if comfyui_enabled:
        stages.append("comfyui")
    return stages


def retry_tail_for_stage(
    start_stage: str,
    *,
    requires_grid_asset: bool,
    writes_artifacts: bool,
    comfyui_enabled: bool,
) -> list[str]:
    stages = stage_ids_for_run(
        requires_grid_asset=requires_grid_asset,
        writes_artifacts=writes_artifacts,
        comfyui_enabled=comfyui_enabled,
    )
    if start_stage == "gpt_prompt_reviser":
        tail = ["gpt_prompt_reviser", "final_prompts"]
        if requires_grid_asset:
            tail.append("four_grid_asset")
        if writes_artifacts:
            tail.append("artifacts")
        if comfyui_enabled:
            tail.append("comfyui")
        return tail
    if start_stage not in stages:
        raise ValueError(f"Cannot retry from unavailable stage: {start_stage}")
    return stages[stages.index(start_stage) :]
