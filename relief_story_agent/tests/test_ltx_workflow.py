import json

from relief_story_agent.ltx_workflow import (
    build_ltx_payload_from_storyboard,
    build_segment_ltx_payload,
    detect_workflow_format,
    find_ltx_injection_points,
    litegraph_to_api_prompt,
    patch_ltx_litegraph_workflow,
)
from relief_story_agent.models import SegmentRenderState


def test_build_segment_ltx_payload_uses_local_timeline_and_one_shot():
    segment = SegmentRenderState(
        segment_id="segment-003",
        shot_id="3",
        order=3,
        authored_time_range="25-45s",
        render_time_range="25-45s",
        duration_seconds=20,
        frame_count=480,
        local_frame_indices=[0, 160, 319, 479],
        positive_prompt="slow dolly toward the cashier",
        negative_prompt="text, watermark",
        seed=31415,
        strength=0.76,
        grid_panel_prompts=["wide", "medium", "close", "reaction"],
    )

    payload = build_segment_ltx_payload(segment)

    assert payload["duration_seconds"] == 20
    assert payload["fps"] == 24
    assert payload["frame_indices"] == "0,160,319,479"
    assert payload["strengths"] == "0.76,0.76,0.76,0.76"
    assert len(payload["shots"]) == 1
    assert payload["shots"][0]["shot_id"] == "3"
    assert payload["shots"][0]["time_range"] == "0-20s"


def _mini_litegraph_workflow():
    return {
        "version": 0.4,
        "nodes": [
            {
                "id": 10,
                "type": "JWString",
                "title": "LTX JSON",
                "inputs": [{"name": "text", "type": "STRING", "widget": {"name": "text"}}],
                "outputs": [{"name": "STRING", "type": "STRING", "links": [1, 2]}],
                "widgets_values": [
                    json.dumps(
                        {
                            "prompt": "old prompt",
                            "negative_prompt": "old negative",
                            "frame_indices": "0,24,48,72",
                            "strengths": "0.7,0.7,0.8,0.8",
                            "duration_seconds": 4,
                            "fps": 24,
                            "shots": [],
                        },
                        ensure_ascii=False,
                    )
                ],
            },
            {
                "id": 20,
                "type": "ParseJsonNode",
                "inputs": [
                    {"name": "input", "type": "STRING", "link": 1},
                    {"name": "key", "type": "STRING", "widget": {"name": "key"}},
                ],
                "outputs": [{"name": "any", "type": "*"}, {"name": "string", "type": "STRING", "links": [3]}],
                "widgets_values": ["prompt"],
            },
            {
                "id": 30,
                "type": "CLIPTextEncode",
                "title": "正向提示词",
                "inputs": [
                    {"name": "clip", "type": "CLIP", "link": 4},
                    {"name": "text", "type": "STRING", "widget": {"name": "text"}, "link": 3},
                ],
                "outputs": [{"name": "CONDITIONING", "type": "CONDITIONING", "links": []}],
                "widgets_values": ["unused because linked"],
            },
            {
                "id": 40,
                "type": "RandomNoise",
                "inputs": [{"name": "noise_seed", "type": "INT", "widget": {"name": "noise_seed"}}],
                "outputs": [{"name": "NOISE", "type": "NOISE", "links": []}],
                "widgets_values": [111, "randomize"],
            },
            {
                "id": 50,
                "type": "VHS_VideoCombine",
                "inputs": [
                    {"name": "images", "type": "IMAGE", "link": 5},
                    {"name": "filename_prefix", "type": "STRING", "widget": {"name": "filename_prefix"}},
                    {"name": "frame_rate", "type": "FLOAT", "widget": {"name": "frame_rate"}},
                ],
                "outputs": [{"name": "Filenames", "type": "VHS_FILENAMES"}],
                "widgets_values": {"filename_prefix": "old_prefix", "frame_rate": 24, "videopreview": {"ignored": True}},
            },
        ],
        "links": [
            [1, 10, 0, 20, 0, "STRING"],
            [2, 10, 0, 99, 0, "STRING"],
            [3, 20, 1, 30, 1, "STRING"],
            [4, 88, 0, 30, 0, "CLIP"],
            [5, 77, 0, 50, 0, "IMAGE"],
        ],
    }


def test_detects_litegraph_and_finds_ltx_json_injection_node():
    workflow = _mini_litegraph_workflow()

    points = find_ltx_injection_points(workflow)

    assert detect_workflow_format(workflow) == "litegraph"
    assert points.json_node_id == "10"
    assert points.seed_node_id == "40"
    assert points.filename_prefix_node_id == "50"


def test_prefers_jwstring_ltx_json_over_stale_linked_clip_widget_text():
    workflow = _mini_litegraph_workflow()
    stale_clip_node = workflow["nodes"][2]
    workflow["nodes"] = [stale_clip_node, workflow["nodes"][0], workflow["nodes"][1], *workflow["nodes"][3:]]
    stale_clip_node["widgets_values"] = [
        json.dumps(
            {
                "prompt": "stale clip text",
                "negative_prompt": "stale negative",
                "frame_indices": "0,24,48,72",
                "strengths": "0.7,0.7,0.8,0.8",
                "duration_seconds": 4,
                "fps": 24,
                "shots": [],
            },
            ensure_ascii=False,
        )
    ]

    points = find_ltx_injection_points(workflow)

    assert points.json_node_id == "10"


def test_litegraph_to_api_prompt_preserves_links_and_widget_inputs():
    prompt = litegraph_to_api_prompt(_mini_litegraph_workflow())

    assert prompt["20"]["inputs"]["input"] == ["10", 0]
    assert prompt["20"]["inputs"]["key"] == "prompt"
    assert prompt["30"]["inputs"]["text"] == ["20", 1]
    assert prompt["40"]["inputs"]["noise_seed"] == 111
    assert prompt["50"]["inputs"]["filename_prefix"] == "old_prefix"
    assert "videopreview" not in prompt["50"]["inputs"]


def test_litegraph_to_api_prompt_expands_kjnodes_set_get_pairs_to_direct_links():
    workflow = {
        "version": 0.4,
        "nodes": [
            {"id": 1, "type": "PrimitiveInt", "outputs": [{"name": "INT", "type": "INT", "links": [10]}]},
            {
                "id": 2,
                "type": "SetNode",
                "inputs": [{"name": "INT", "type": "INT", "link": 10}],
                "outputs": [{"name": "*", "type": "*"}],
                "widgets_values": ["width"],
            },
            {
                "id": 3,
                "type": "GetNode",
                "inputs": [],
                "outputs": [{"name": "INT", "type": "INT", "links": [20]}],
                "widgets_values": ["width"],
            },
            {
                "id": 4,
                "type": "NeedsWidth",
                "inputs": [{"name": "width", "type": "INT", "link": 20}],
                "outputs": [],
            },
        ],
        "links": [
            [10, 1, 0, 2, 0, "INT"],
            [20, 3, 0, 4, 0, "INT"],
        ],
    }

    prompt = litegraph_to_api_prompt(workflow)

    assert "2" not in prompt
    assert "3" not in prompt
    assert prompt["4"]["inputs"]["width"] == ["1", 0]


def test_litegraph_to_api_prompt_expands_comfyui_subgraph_nodes():
    workflow = {
        "version": 0.4,
        "nodes": [
            {"id": 1, "type": "PrimitiveString", "outputs": [{"name": "STRING", "type": "STRING", "links": [10]}]},
            {
                "id": 2,
                "type": "subgraph-uuid",
                "inputs": [{"name": "text", "type": "STRING", "link": 10}],
                "outputs": [{"name": "STRING", "type": "STRING", "links": [20]}],
            },
            {"id": 3, "type": "NeedsSubgraphOutput", "inputs": [{"name": "value", "type": "STRING", "link": 20}]},
        ],
        "links": [
            [10, 1, 0, 2, 0, "STRING"],
            [20, 2, 0, 3, 0, "STRING"],
        ],
        "definitions": {
            "subgraphs": [
                {
                    "id": "subgraph-uuid",
                    "name": "Tiny Subgraph",
                    "inputNode": {"id": -10},
                    "outputNode": {"id": -20},
                    "inputs": [{"name": "text", "type": "STRING"}],
                    "outputs": [{"name": "STRING", "type": "STRING"}],
                    "nodes": [
                        {
                            "id": 101,
                            "type": "InnerTransform",
                            "inputs": [{"name": "text", "type": "STRING", "link": 100}],
                            "outputs": [{"name": "STRING", "type": "STRING", "links": [101]}],
                        }
                    ],
                    "links": [
                        {
                            "id": 100,
                            "origin_id": -10,
                            "origin_slot": 0,
                            "target_id": 101,
                            "target_slot": 0,
                            "type": "STRING",
                        },
                        {
                            "id": 101,
                            "origin_id": 101,
                            "origin_slot": 0,
                            "target_id": -20,
                            "target_slot": 0,
                            "type": "STRING",
                        },
                    ],
                }
            ]
        },
    }

    prompt = litegraph_to_api_prompt(workflow)

    assert "2" not in prompt
    assert prompt["2:101"]["class_type"] == "InnerTransform"
    assert prompt["2:101"]["inputs"]["text"] == ["1", 0]
    assert prompt["3"]["inputs"]["value"] == ["2:101", 0]


def test_patches_ltx_json_seed_and_filename_prefix_before_api_conversion():
    workflow = _mini_litegraph_workflow()
    ltx_payload = {
        "prompt": "new ltx prompt",
        "negative_prompt": "new negative",
        "frame_indices": "0,48,96,144",
        "strengths": "0.72,0.74,0.82,0.84",
        "duration_seconds": 6,
        "fps": 24,
        "shots": [],
    }

    patched_prompt = patch_ltx_litegraph_workflow(
        workflow,
        ltx_payload=ltx_payload,
        seed=222,
        filename_prefix="relief_test",
    )

    injected = json.loads(patched_prompt["10"]["inputs"]["text"])
    assert injected["prompt"] == "new ltx prompt"
    assert patched_prompt["40"]["inputs"]["noise_seed"] == 222
    assert patched_prompt["50"]["inputs"]["filename_prefix"] == "relief_test"


def test_build_ltx_payload_from_storyboard_selects_balanced_four_keyframes():
    payload = build_ltx_payload_from_storyboard(
        [
            {
                "shot_id": 1,
                "time_range": "0-10s",
                "description": "雨后便利店外景。",
                "image_prompt": "雨后便利店，疲惫上班族推门进入",
                "negative_prompt": "争吵，恐怖",
                "comfyui_inputs": {"strength": 0.72},
            },
            {
                "shot_id": 2,
                "time_range": "10-30s",
                "description": "店员看见他只买冷便当。",
                "image_prompt": "便利店收银台，温柔灯光",
                "negative_prompt": "争吵，恐怖",
                "comfyui_inputs": {"strength": 0.74},
            },
            {
                "shot_id": 3,
                "time_range": "30-60s",
                "description": "店员多放一双筷子。",
                "image_prompt": "热汤与便当的近景",
                "negative_prompt": "争吵，恐怖",
                "comfyui_inputs": {"strength": 0.82},
            },
            {
                "shot_id": 4,
                "time_range": "60-90s",
                "description": "便当热气升起。",
                "image_prompt": "窗边座位，热气缓慢升起",
                "negative_prompt": "争吵，恐怖",
                "comfyui_inputs": {"strength": 0.84},
            },
            {
                "shot_id": 5,
                "time_range": "90-100s",
                "image_prompt": "aftertaste ending, phone screen off, warm steam remains",
                "negative_prompt": "shouting",
                "comfyui_inputs": {"strength": 0.9},
            },
        ],
        duration_seconds=90,
        fps=24,
    )

    assert payload["duration_seconds"] == 90
    assert payload["fps"] == 24
    assert payload["frame_indices"] == "0,240,720,2159"
    assert payload["strengths"] == "0.72,0.74,0.82,0.9"
    assert len(payload["shots"]) == 4
    assert "雨后便利店" in payload["prompt"]
    assert "aftertaste ending" in payload["prompt"]
    assert [shot["shot_id"] for shot in payload["shots"]] == [1, 2, 3, 5]
    assert payload["shots"][-1]["requested_frame_index"] == 2160
    assert payload["shots"][-1]["frame_index"] == 2159
    assert payload["shots"][-1]["frame_index_clamped"] is True
    assert payload["keyframe_selection"] == {
        "strategy": "balanced_timeline",
        "source_shot_count": 5,
        "selected_shot_ids": [1, 2, 3, 5],
        "max_keyframes": 4,
        "frame_index_clamp": {"min": 0, "max": 2159},
        "frame_index_order": {
            "strategy": "preserve_story_order_strictly_increasing",
            "strictly_increasing": True,
            "adjusted_count": 0,
        },
        "strength_normalization": {
            "range": {"min": 0, "max": 1},
            "adjusted_count": 0,
            "fallback_count": 0,
        },
        "keyframes": [
            {
                "slot": 1,
                "shot_id": 1,
                "time_range": "0-10s",
                "requested_frame_index": 0,
                "frame_index": 0,
                "frame_index_clamped": False,
                "frame_index_adjusted": False,
                "requested_strength": 0.72,
                "strength": 0.72,
                "strength_adjusted": False,
            },
            {
                "slot": 2,
                "shot_id": 2,
                "time_range": "10-30s",
                "requested_frame_index": 240,
                "frame_index": 240,
                "frame_index_clamped": False,
                "frame_index_adjusted": False,
                "requested_strength": 0.74,
                "strength": 0.74,
                "strength_adjusted": False,
            },
            {
                "slot": 3,
                "shot_id": 3,
                "time_range": "30-60s",
                "requested_frame_index": 720,
                "frame_index": 720,
                "frame_index_clamped": False,
                "frame_index_adjusted": False,
                "requested_strength": 0.82,
                "strength": 0.82,
                "strength_adjusted": False,
            },
            {
                "slot": 4,
                "shot_id": 5,
                "time_range": "90-100s",
                "requested_frame_index": 2160,
                "frame_index": 2159,
                "frame_index_clamped": True,
                "frame_index_adjusted": False,
                "requested_strength": 0.9,
                "strength": 0.9,
                "strength_adjusted": False,
            },
        ],
    }


def test_build_ltx_payload_keeps_frame_indices_strictly_increasing_when_times_overlap():
    payload = build_ltx_payload_from_storyboard(
        [
            {"shot_id": 1, "time_range": "10-20s", "image_prompt": "first"},
            {"shot_id": 2, "time_range": "10-30s", "image_prompt": "duplicate time"},
            {"shot_id": 3, "time_range": "5-15s", "image_prompt": "backward time"},
            {"shot_id": 4, "time_range": "60-70s", "image_prompt": "ending"},
        ],
        duration_seconds=90,
        fps=24,
    )

    assert payload["frame_indices"] == "240,241,242,1440"
    assert [shot["requested_frame_index"] for shot in payload["shots"]] == [240, 240, 120, 1440]
    assert [shot["frame_index_adjusted"] for shot in payload["shots"]] == [False, True, True, False]
    assert payload["keyframe_selection"]["frame_index_order"] == {
        "strategy": "preserve_story_order_strictly_increasing",
        "strictly_increasing": True,
        "adjusted_count": 2,
    }


def test_build_ltx_payload_normalizes_strengths_and_records_adjustments():
    payload = build_ltx_payload_from_storyboard(
        [
            {"shot_id": 1, "time_range": "0-10s", "image_prompt": "a", "comfyui_inputs": {"strength": 1.4}},
            {"shot_id": 2, "time_range": "20-30s", "image_prompt": "b", "comfyui_inputs": {"strength": -0.2}},
            {"shot_id": 3, "time_range": "40-50s", "image_prompt": "c", "comfyui_inputs": {"strength": "0.66"}},
            {"shot_id": 4, "time_range": "60-70s", "image_prompt": "d", "comfyui_inputs": {"strength": "bad"}},
        ],
        duration_seconds=90,
        fps=24,
    )

    assert payload["strengths"] == "1,0,0.66,0.84"
    assert [shot["requested_strength"] for shot in payload["shots"]] == [1.4, -0.2, "0.66", "bad"]
    assert [shot["strength"] for shot in payload["shots"]] == [1, 0, 0.66, 0.84]
    assert [shot["strength_adjusted"] for shot in payload["shots"]] == [True, True, False, True]
    assert payload["keyframe_selection"]["strength_normalization"] == {
        "range": {"min": 0, "max": 1},
        "adjusted_count": 3,
        "fallback_count": 1,
    }
