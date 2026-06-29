from relief_story_agent.models import RunRequest, StoryInputSpec, CreationSpec
from relief_story_agent.config_validation import _validate_input_spec, _validate_creation_spec

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
    from pydantic import ValidationError
    import pytest
    
    with pytest.raises(ValidationError):
        RunRequest.model_validate({
            "idea": "test",
            "creation_spec": {"video_aspect_ratio": "4:3"}
        })
