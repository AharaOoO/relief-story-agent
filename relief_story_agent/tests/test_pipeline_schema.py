from __future__ import annotations

import json
import subprocess
import sys

from fastapi.testclient import TestClient

from relief_story_agent.api import create_app
from relief_story_agent.orchestrator import StoryRunOrchestrator
from relief_story_agent.pipeline import (
    CANONICAL_STAGE_ORDER,
    MODEL_STAGE_IDS,
    build_pipeline_schema,
)
from relief_story_agent.providers import FakeModelProvider


def test_pipeline_schema_exposes_fixed_order_and_stage_metadata():
    schema = build_pipeline_schema()

    assert schema["schema_version"] == "1"
    assert schema["canonical_stage_order"] == list(CANONICAL_STAGE_ORDER)
    assert schema["runtime_variants"]["base"] == [
        "chief_screenwriter",
        "deepseek_polish",
        "quality_gate",
        "gpt_prompt_writer",
        "gpt_prompt_audit",
        "final_prompts",
    ]
    assert schema["invariants"]["fixed_order"] is True
    assert schema["invariants"]["prompt_reviser_max_auto_attempts"] == 1
    assert schema["invariants"]["comfyui_workflow_generation"] == "never"

    stages = {stage["stage_id"]: stage for stage in schema["stages"]}
    assert stages["chief_screenwriter"]["category"] == "model"
    assert stages["chief_screenwriter"]["side_effects"] == ["model_call"]
    assert stages["quality_gate"]["category"] == "model"
    assert stages["quality_gate"]["side_effects"] == ["model_call"]
    assert "quality_gate" in MODEL_STAGE_IDS
    assert stages["gpt_prompt_reviser"]["automatic"] == "conditional_once"
    assert stages["four_grid_asset"]["category"] == "asset"
    assert stages["comfyui"]["side_effects"] == ["comfyui_prompt"]


def test_api_pipeline_schema_returns_core_contract():
    client = TestClient(create_app(StoryRunOrchestrator(provider=FakeModelProvider.minimal_success())))

    response = client.get("/api/pipeline/schema")

    assert response.status_code == 200
    body = response.json()
    assert body["canonical_stage_order"] == list(CANONICAL_STAGE_ORDER)
    assert body["stages"][0]["stage_id"] == "chief_screenwriter"
    assert body["stages"][-1]["stage_id"] == "comfyui"


def test_cli_pipeline_schema_prints_machine_readable_contract():
    completed = subprocess.run(
        [sys.executable, "-m", "relief_story_agent.cli", "pipeline-schema"],
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert completed.returncode == 0
    body = json.loads(completed.stdout)
    assert body["canonical_stage_order"] == list(CANONICAL_STAGE_ORDER)
    assert body["invariants"]["fixed_order"] is True
