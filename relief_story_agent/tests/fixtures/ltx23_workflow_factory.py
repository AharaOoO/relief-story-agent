def build_sanitized_ltx23_workflow():
    nodes = [
        {
            "id": 196,
            "type": "LoadImage",
            "inputs": [
                {"name": "image", "type": "COMBO", "widget": {"name": "image"}},
                {"name": "upload", "type": "IMAGEUPLOAD", "widget": {"name": "upload"}},
            ],
            "outputs": [{"name": "IMAGE", "type": "IMAGE", "links": [451]}],
            "widgets_values": ["fixture.png", "image"],
        },
        {
            "id": 202,
            "type": "JWString",
            "inputs": [{"name": "text", "type": "STRING", "widget": {"name": "text"}}],
            "outputs": [{"name": "STRING", "type": "STRING", "links": [435]}],
            "widgets_values": [
                '{"prompt":"fixture","frame_indices":"0,24,48,72","strengths":"0.7,0.7,0.7,0.7","duration_seconds":4}'
            ],
        },
        {
            "id": 37,
            "type": "RandomNoise",
            "inputs": [{"name": "noise_seed", "type": "INT", "widget": {"name": "noise_seed"}}],
            "outputs": [{"name": "NOISE", "type": "NOISE"}],
            "widgets_values": [123, "randomize"],
        },
        {
            "id": 79,
            "type": "VHS_VideoCombine",
            "inputs": [
                {"name": "filename_prefix", "type": "STRING", "widget": {"name": "filename_prefix"}}
            ],
            "outputs": [],
            "widgets_values": {"filename_prefix": "fixture"},
        },
        {
            "id": 218,
            "type": "ParseJsonNode",
            "inputs": [{"name": "input", "type": "STRING", "link": 435}],
            "outputs": [],
            "widgets_values": ["prompt"],
        },
        {
            "id": 221,
            "type": "TD_LTXVAddGuideFromGrid",
            "inputs": [
                {"name": "grid_image", "type": "IMAGE", "link": 451},
                {"name": "columns", "type": "INT", "widget": {"name": "columns"}},
                {"name": "rows", "type": "INT", "widget": {"name": "rows"}},
            ],
            "outputs": [],
            "widgets_values": [2, 2],
        },
    ]
    next_id = 300
    while len(nodes) < 60:
        nodes.append(
            {
                "id": next_id,
                "type": "FixturePassthrough",
                "inputs": [],
                "outputs": [],
                "widgets_values": [],
            }
        )
        next_id += 1
    return {
        "version": 0.4,
        "nodes": nodes,
        "links": [
            [435, 202, 0, 218, 0, "STRING"],
            [451, 196, 0, 221, 0, "IMAGE"],
        ],
    }
