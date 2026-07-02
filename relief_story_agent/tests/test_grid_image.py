from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from relief_story_agent.grid_image import (
    acquire_manual_grid_image,
    acquire_generated_grid_image,
    compile_four_grid_prompt,
    compile_segment_four_grid_prompt,
    deterministic_comfyui_filename,
    GeneratedImage,
    validate_grid_image,
)
from relief_story_agent.models import (
    ComfyUIRunConfig,
    GridImageAsset,
    GridImageConfig,
    RunRequest,
)


def test_grid_image_config_defaults_to_gpt_image_2_auto_mode():
    config = GridImageConfig()

    assert config.mode == "auto"
    assert config.provider == "openai_compatible"
    assert config.model == "gpt-image-2"
    assert config.aspect_ratio == "16:9"
    assert config.resolution == "2k"
    assert config.quality == "medium"
    assert config.output_format == "png"
    assert config.prompt_max_chars == 4000
    assert config.min_dimension == 512


def test_manual_path_has_explicit_precedence():
    config = GridImageConfig(
        mode="auto",
        manual_image_path="D:/images/override.png",
    )

    assert config.effective_mode() == "manual_override"


def test_grid_image_secret_is_not_serialized():
    request = RunRequest(
        idea="secret-safe",
        comfyui=ComfyUIRunConfig(
            enabled=True,
            grid_image=GridImageConfig(api_key="secret-value"),
        ),
    )

    serialized = request.model_dump()
    assert "secret-value" not in str(serialized)
    assert "api_key" not in serialized["comfyui"]["grid_image"]


def test_grid_image_asset_round_trips_through_run_state(tmp_path):
    image_path = tmp_path / "grid.png"
    asset = GridImageAsset(
        source="generated",
        local_path=str(image_path),
        sha256="a" * 64,
        mime_type="image/png",
        width=1024,
        height=1024,
        byte_size=123,
        prompt="2x2 grid",
        provider="openai_compatible",
        model="gpt-image-2",
    )

    assert asset.upload_status == "pending"
    assert Path(asset.local_path).name == "grid.png"


def _make_grid(path, *, size=(1024, 1024), colors=None, add_detail=True):
    image = Image.new("RGB", size, "white")
    colors = colors or ["red", "green", "blue", "yellow"]
    half_w = size[0] // 2
    half_h = size[1] // 2
    draw = ImageDraw.Draw(image)
    for index, color in enumerate(colors):
        left = (index % 2) * half_w
        top = (index // 2) * half_h
        image.paste(color, (left, top, left + half_w, top + half_h))
        if add_detail:
            draw.line(
                (left + 20, top + 20, left + half_w - 20, top + half_h - 20),
                fill="black",
                width=8,
            )
    image.save(path)


def test_compile_prompt_selects_four_balanced_chronological_frames():
    storyboard = [
        {
            "shot_id": index + 1,
            "time_range": f"{index * 10}-{index * 10 + 8}s",
            "image_prompt": f"frame {index + 1}",
        }
        for index in range(8)
    ]

    prompt = compile_four_grid_prompt(storyboard, max_chars=600)

    assert "Top-left: frame 1" in prompt
    assert "Top-right: frame 3" in prompt
    assert "Bottom-left: frame 5" in prompt
    assert "Bottom-right: frame 8" in prompt
    assert len(prompt) <= 600


def test_compile_segment_prompt_uses_only_one_shot_and_four_ordered_panels():
    prompt = compile_segment_four_grid_prompt(
        {
            "shot_id": 3,
            "image_prompt": "父亲把热咖啡推向夜班护士",
            "grid_panel_prompts": ["看见", "靠近", "推杯", "释然"],
        },
        aspect_ratio="16:9",
        max_chars=1200,
    )

    assert "one story segment" in prompt
    assert "Top-left: 看见" in prompt
    assert "Top-right: 靠近" in prompt
    assert "Bottom-left: 推杯" in prompt
    assert "Bottom-right: 释然" in prompt
    assert "16:9" in prompt
    assert "other segments" in prompt


def test_validate_grid_image_reports_dimensions_hash_and_quadrants(tmp_path):
    path = tmp_path / "grid.png"
    _make_grid(path)

    validated = validate_grid_image(path, min_dimension=512, max_bytes=10_000_000)

    assert validated.mime_type == "image/png"
    assert validated.width == 1024
    assert validated.height == 1024
    assert len(validated.sha256) == 64


def test_validate_grid_image_uses_the_selected_landscape_or_portrait_ratio(tmp_path):
    landscape = tmp_path / "landscape.png"
    portrait = tmp_path / "portrait.png"
    _make_grid(landscape, size=(1600, 900))
    _make_grid(portrait, size=(900, 1600))

    assert validate_grid_image(
        landscape,
        min_dimension=512,
        max_bytes=10_000_000,
        expected_aspect_ratio="16:9",
    ).width == 1600
    assert validate_grid_image(
        portrait,
        min_dimension=512,
        max_bytes=10_000_000,
        expected_aspect_ratio="9:16",
    ).height == 1600

    with pytest.raises(ValueError, match="16:9"):
        validate_grid_image(
            portrait,
            min_dimension=512,
            max_bytes=10_000_000,
            expected_aspect_ratio="16:9",
        )


def test_validate_grid_image_rejects_empty_quadrant(tmp_path):
    path = tmp_path / "blank.png"
    _make_grid(
        path,
        colors=["white", "white", "white", "white"],
        add_detail=False,
    )

    with pytest.raises(ValueError, match="quadrant"):
        validate_grid_image(path, min_dimension=512, max_bytes=10_000_000)


def test_manual_asset_is_copied_without_modifying_source(tmp_path):
    source = tmp_path / "source.png"
    artifact_dir = tmp_path / "run"
    _make_grid(source, size=(1600, 900))
    before = source.read_bytes()

    asset = acquire_manual_grid_image(
        source,
        artifact_dir=artifact_dir,
        prompt="compiled prompt",
        config=GridImageConfig(manual_image_path=str(source)),
    )

    assert source.read_bytes() == before
    assert Path(asset.local_path).parent == artifact_dir
    assert Path(asset.local_path).read_bytes() == before
    assert asset.source == "manual"


def test_deterministic_filename_uses_run_and_hash():
    assert (
        deterministic_comfyui_filename(
            "run_demo",
            "abcdef0123456789",
            "image/png",
        )
        == "run_demo_abcdef012345.png"
    )


class FakeGridProvider:
    def __init__(self, content):
        self.content = content
        self.calls = 0

    def generate(self, *, prompt, config):
        self.calls += 1
        return GeneratedImage(
            content=self.content,
            mime_type="image/png",
            provider="fake",
            model=config.model,
        )


def test_generated_asset_is_saved_and_validated(tmp_path):
    source = tmp_path / "source.png"
    _make_grid(source, size=(1600, 900))
    provider = FakeGridProvider(source.read_bytes())

    asset = acquire_generated_grid_image(
        provider,
        artifact_dir=tmp_path / "run",
        prompt="compiled",
        config=GridImageConfig(),
    )

    assert provider.calls == 1
    assert asset.source == "generated"
    assert Path(asset.local_path).name == "10_four_grid_image.png"
    assert asset.provider == "fake"
