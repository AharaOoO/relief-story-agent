from __future__ import annotations

import pytest

from relief_story_agent.output_contracts import require_shot_contract
from relief_story_agent.segment_render import (
    build_segment_render_plan,
    local_frame_indices,
    parse_time_range,
)


SIX_SHOTS = [
    {
        "shot_id": index,
        "time_range": time_range,
        "description": f"shot {index}",
        "image_prompt": f"image prompt {index}",
        "negative_prompt": "text, watermark",
        "comfyui_inputs": {"seed": 1000 + index, "strength": 0.7},
    }
    for index, time_range in enumerate(
        ["0-10s", "10-25s", "25-45s", "45-60s", "60-75s", "75-90s"],
        start=1,
    )
]


def test_auto_duration_preserves_six_authored_ranges():
    states = build_segment_render_plan(
        SIX_SHOTS,
        target_duration_seconds=0,
        fps=24,
    )

    assert [item.duration_seconds for item in states] == [10, 15, 20, 15, 15, 15]
    assert [item.frame_count for item in states] == [241, 361, 481, 361, 361, 361]
    assert states[0].local_frame_indices == [0, 80, 159, 239]
    assert states[2].local_frame_indices == [0, 160, 319, 479]


def test_explicit_duration_retimes_and_preserves_exact_total():
    states = build_segment_render_plan(
        SIX_SHOTS,
        target_duration_seconds=60,
        fps=24,
    )

    assert [item.duration_seconds for item in states] == [7, 10, 13, 10, 10, 10]
    assert sum(item.duration_seconds for item in states) == 60
    assert all(item.duration_seconds >= 1 for item in states)
    assert states[0].authored_time_range == "0-10s"
    assert states[-1].render_time_range == "50-60s"


def test_every_shot_gets_one_stable_segment_id():
    states = build_segment_render_plan(
        SIX_SHOTS,
        target_duration_seconds=90,
        fps=24,
    )

    assert [item.segment_id for item in states] == [
        f"shot-{index:03d}" for index in range(1, 7)
    ]
    assert [item.shot_id for item in states] == [str(index) for index in range(1, 7)]


def test_model_authored_panels_are_preserved():
    shot = dict(SIX_SHOTS[0])
    shot["grid_panel_prompts"] = ["opening", "development", "climax", "exit"]

    state = build_segment_render_plan([shot], target_duration_seconds=0, fps=24)[0]

    assert state.grid_panel_prompts == shot["grid_panel_prompts"]
    assert state.grid_prompt_source == "model"


def test_shot_contract_accepts_exactly_four_optional_grid_panels():
    shot = dict(SIX_SHOTS[0])
    shot["grid_panel_prompts"] = ["opening", "development", "climax", "exit"]

    normalized = require_shot_contract([shot], "gpt_prompt_writer")

    assert normalized[0]["grid_panel_prompts"] == shot["grid_panel_prompts"]


def test_shot_contract_rejects_incomplete_grid_panels():
    shot = dict(SIX_SHOTS[0])
    shot["grid_panel_prompts"] = ["opening", "exit"]

    with pytest.raises(ValueError, match="exactly four"):
        require_shot_contract([shot], "gpt_prompt_writer")


def test_legacy_shot_derives_four_panels():
    state = build_segment_render_plan(
        [SIX_SHOTS[0]],
        target_duration_seconds=0,
        fps=24,
    )[0]

    assert len(state.grid_panel_prompts) == 4
    assert state.grid_prompt_source == "derived"
    assert all("image prompt 1" in item for item in state.grid_panel_prompts)


@pytest.mark.parametrize("value", ["", "10", "10-5s", "one-two"])
def test_invalid_time_ranges_are_rejected(value):
    with pytest.raises(ValueError):
        parse_time_range(value)


def test_local_frame_indices_are_strict_and_bounded():
    assert local_frame_indices(15, 24) == [0, 120, 239, 359]
