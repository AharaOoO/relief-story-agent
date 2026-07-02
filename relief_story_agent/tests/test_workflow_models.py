from __future__ import annotations

import pytest

from relief_story_agent.artifacts import write_execution_manifest
from relief_story_agent.models import RunRequest, RunState, SegmentRenderState
from relief_story_agent.workflow_models import (
    WorkflowModelUnavailable,
    build_workflow_model_manifest,
    validate_workflow_models,
)


WORKFLOW = {
    "151": {
        "class_type": "CheckpointLoaderSimple",
        "inputs": {"ckpt_name": "ltx-2.3-22b.safetensors"},
        "_meta": {"title": "LTX model loader"},
    },
    "152": {
        "class_type": "KSampler",
        "inputs": {"sampler_name": "euler"},
    },
}

OBJECT_INFO = {
    "CheckpointLoaderSimple": {
        "input": {
            "required": {
                "ckpt_name": [
                    ["ltx-2.3-22b.safetensors", "other.safetensors"],
                    {"tooltip": "checkpoint"},
                ]
            }
        }
    },
    "KSampler": {
        "input": {"required": {"sampler_name": [["euler", "dpmpp_2m"], {}]}}
    },
}


def test_model_manifest_reports_available_loader_values():
    manifest = build_workflow_model_manifest(WORKFLOW, OBJECT_INFO)

    assert len(manifest) == 1
    assert manifest[0].node_id == "151"
    assert manifest[0].title == "LTX model loader"
    assert manifest[0].selected == "ltx-2.3-22b.safetensors"
    assert manifest[0].available is True
    assert manifest[0].choices == [
        "ltx-2.3-22b.safetensors",
        "other.safetensors",
    ]


def test_missing_model_blocks_submission_with_node_details():
    unavailable = {
        **OBJECT_INFO,
        "CheckpointLoaderSimple": {
            "input": {
                "required": {
                    "ckpt_name": [["other.safetensors"], {}],
                }
            }
        },
    }

    with pytest.raises(WorkflowModelUnavailable) as exc:
        validate_workflow_models(WORKFLOW, unavailable)

    assert exc.value.details[0]["node_id"] == "151"
    assert exc.value.details[0]["selected"] == "ltx-2.3-22b.safetensors"


def test_non_model_choice_inputs_are_not_reported_as_models():
    manifest = build_workflow_model_manifest(WORKFLOW, OBJECT_INFO)

    assert all(binding.input_name != "sampler_name" for binding in manifest)


def test_execution_manifest_records_segment_parameters_without_secrets(tmp_path):
    run = RunState(
        run_id="run_manifest",
        request=RunRequest(
            idea="manifest",
            output_root=str(tmp_path),
            creation_spec={"duration_seconds": 0},
        ),
        segment_renders=[
            SegmentRenderState(
                segment_id="segment-001",
                shot_id="1",
                order=1,
                authored_time_range="0-10s",
                render_time_range="0-10s",
                duration_seconds=10,
                frame_count=240,
                local_frame_indices=[0, 80, 159, 239],
                positive_prompt="camera prompt",
                grid_panel_prompts=["a", "b", "c", "d"],
                workflow_name="LTX workflow",
                workflow_path="D:/workflows/ltx.json",
                workflow_sha256="f" * 64,
                workflow_models=build_workflow_model_manifest(WORKFLOW, OBJECT_INFO),
            )
        ],
    )

    path = write_execution_manifest(run)
    text = path.read_text(encoding="utf-8")

    assert path.name == "execution_manifest.json"
    assert '"duration_mode": "auto"' in text
    assert '"frame_count": 240' in text
    assert '"local_frame_indices": [' in text
    assert "ltx-2.3-22b.safetensors" in text
    assert "api_key" not in text.casefold()
    assert "authorization" not in text.casefold()
