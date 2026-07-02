import pytest
from pydantic import ValidationError

from relief_story_agent.config_validation import (
    _validate_creation_spec,
    _validate_input_spec,
    validate_run_configuration,
)
from relief_story_agent.model_config import ModelConfigRegistry
from relief_story_agent.models import CreationSpec, RunRequest


@pytest.mark.parametrize("value", [0, 15, 90, 300])
def test_creation_spec_accepts_supported_duration_values(value):
    assert CreationSpec(duration_seconds=value).duration_seconds == value


@pytest.mark.parametrize("value", [-1, 1, 14, 301])
def test_creation_spec_rejects_unsupported_duration_values(value):
    with pytest.raises(ValidationError):
        CreationSpec(duration_seconds=value)


def test_legacy_run_duration_migrates_into_creation_spec():
    request = RunRequest.model_validate({"duration_seconds": 180})

    assert request.creation_spec.duration_seconds == 180

def test_run_request_v2_migration():
    # Test that V1 idea is migrated to input_spec
    payload = {
        "idea": "A short story",
        "duration_seconds": 120,
        "preferred_series": "Test Series",
        "preferred_style": "cinematic_suspense",
        "audience_pressure": "high"
    }
    req = RunRequest.model_validate(payload)
    
    assert req.idea == "A short story"
    assert req.input_spec.mode == "idea"
    assert req.input_spec.content == "A short story"
    
    assert req.creation_spec.duration_seconds == 120
    assert req.creation_spec.series_name == "Test Series"
    assert req.creation_spec.style_preset_id == "cinematic_suspense"
    assert req.creation_spec.audience == "high"

def test_validate_input_spec_script_mode():
    # Empty script should fail
    req1 = RunRequest.model_validate({
        "input_spec": {"mode": "script", "content": "  "}
    })
    res1 = _validate_input_spec(req1)
    assert res1["status"] == "failed"
    assert "cannot be empty" in res1["message"]

    # Valid script
    req2 = RunRequest.model_validate({
        "input_spec": {"mode": "script", "content": "Valid content"}
    })
    res2 = _validate_input_spec(req2)
    assert res2["status"] == "passed"

def test_validate_creation_spec_aspect_ratio():
    # Valid aspect ratio
    req1 = RunRequest.model_validate({
        "idea": "test",
        "creation_spec": {"video_aspect_ratio": "16:9"}
    })
    assert _validate_creation_spec(req1)["status"] == "passed"

    # Invalid aspect ratio (simulate bypass pydantic or strict parsing if enum, but literal will fail early in pydantic)
    with pytest.raises(ValidationError):
        RunRequest.model_validate({
            "idea": "test",
            "creation_spec": {"video_aspect_ratio": "4:3"}
        })


def test_blank_auto_input_is_valid_and_preflight_has_one_boolean_semantic():
    request = RunRequest.model_validate(
        {"input_spec": {"mode": "auto", "content": ""}}
    )

    result = validate_run_configuration(request, ModelConfigRegistry())

    assert result["ready"] is True
    assert result["passed"] is True
    assert result["blockers"] == []
    assert isinstance(result["warnings"], list)
    assert result["suggested_actions"] == []


def test_run_request_rejects_unknown_six_stage_bindings():
    with pytest.raises(ValidationError, match="Unknown model stage"):
        RunRequest.model_validate(
            {
                "model_configs": {
                    "artifacts": {"model": "must-not-run-a-model"}
                }
            }
        )

    with pytest.raises(ValidationError, match="Unknown prompt stage"):
        RunRequest.model_validate(
            {
                "prompt_profile": {
                    "stage_overrides": {"comfyui": "not a prompt stage"}
                }
            }
        )


def test_creation_spec_drives_grid_image_ratio_and_resolution():
    landscape = RunRequest.model_validate(
        {
            "creation_spec": {
                "video_aspect_ratio": "16:9",
                "image_resolution": "2k",
            },
            "comfyui": {"enabled": False},
        }
    )
    portrait = RunRequest.model_validate(
        {
            "creation_spec": {
                "video_aspect_ratio": "9:16",
                "image_resolution": "1k",
            },
            "comfyui": {"enabled": False},
        }
    )

    assert landscape.comfyui.grid_image.aspect_ratio == "16:9"
    assert landscape.comfyui.grid_image.resolution == "2k"
    assert portrait.comfyui.grid_image.aspect_ratio == "9:16"
    assert portrait.comfyui.grid_image.resolution == "1k"


def test_legacy_1080p_image_resolution_migrates_to_1k():
    request = RunRequest.model_validate(
        {"creation_spec": {"image_resolution": "1080p"}}
    )

    assert request.creation_spec.image_resolution == "1k"
