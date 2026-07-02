from __future__ import annotations

import hashlib
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Protocol

from PIL import Image, ImageStat

from .models import GridImageAsset, GridImageConfig
from .segment_render import grid_panel_prompts_for_shot


@dataclass(frozen=True)
class GeneratedImage:
    content: bytes
    mime_type: str
    provider: str
    model: str
    task_id: str = ""
    aspect_ratio: str = ""
    resolution: str = ""


class GridImageProvider(Protocol):
    def generate(self, *, prompt: str, config: GridImageConfig) -> GeneratedImage:
        raise NotImplementedError


@dataclass(frozen=True)
class ValidatedImage:
    path: Path
    sha256: str
    mime_type: str
    width: int
    height: int
    byte_size: int


def compile_four_grid_prompt(storyboard: list[dict], *, max_chars: int) -> str:
    if not storyboard:
        raise ValueError("four-grid prompt requires at least one storyboard shot")
    indices = _balanced_indices(len(storyboard), 4)
    selected = [storyboard[index] for index in indices]
    labels = ["Top-left", "Top-right", "Bottom-left", "Bottom-right"]
    frames = []
    for label, shot in zip(labels, selected):
        text = str(shot.get("image_prompt") or shot.get("description") or "").strip()
        if not text:
            raise ValueError("four-grid prompt shot is missing image_prompt and description")
        frames.append(f"{label}: {text}")
    prefix = (
        "Create one clean 2x2 cinematic contact sheet with four equal cells in chronological order. "
        "Keep character identity, wardrobe, screen direction, camera side, and scene geography consistent. "
    )
    suffix = (
        " No captions, labels, readable text, watermarks, extra panels, duplicated cells, or decorative borders."
    )
    prompt = prefix + " ".join(frames) + suffix
    return prompt[:max_chars].rstrip()


def compile_segment_four_grid_prompt(
    shot: dict,
    *,
    aspect_ratio: Literal["16:9", "9:16"],
    max_chars: int,
) -> str:
    panels, _ = grid_panel_prompts_for_shot(shot)
    labels = ["Top-left", "Top-right", "Bottom-left", "Bottom-right"]
    panel_text = " ".join(
        f"{label}: {text}" for label, text in zip(labels, panels, strict=True)
    )
    prompt = (
        "Create one clean 2x2 cinematic contact sheet for one story segment only, "
        f"composed for a {aspect_ratio} output. Read the cells in chronological order. "
        "Keep character identity, wardrobe, location, lighting, camera axis, and screen direction consistent. "
        f"{panel_text} "
        "Do not include events, characters, or locations from other segments. "
        "No captions, panel labels, readable text, watermarks, extra panels, duplicated cells, or decorative borders."
    )
    return prompt[:max_chars].rstrip()


def validate_grid_image(
    path: str | Path,
    *,
    min_dimension: int,
    max_bytes: int,
    expected_aspect_ratio: Literal["16:9", "9:16"] | None = None,
) -> ValidatedImage:
    image_path = Path(path)
    if not image_path.is_file():
        raise ValueError(f"grid image file not found: {image_path}")
    byte_size = image_path.stat().st_size
    if byte_size <= 0 or byte_size > max_bytes:
        raise ValueError(f"grid image byte size is invalid: {byte_size}")
    try:
        with Image.open(image_path) as image:
            image.load()
            width, height = image.size
            detected = Image.MIME.get(image.format or "")
            if detected not in {"image/png", "image/jpeg", "image/webp"}:
                raise ValueError(f"unsupported grid image format: {image.format}")
            if width < min_dimension or height < min_dimension:
                raise ValueError(f"grid image is smaller than {min_dimension}px")
            if expected_aspect_ratio:
                expected = 16 / 9 if expected_aspect_ratio == "16:9" else 9 / 16
                if abs(width / height - expected) > 0.08:
                    raise ValueError(
                        f"grid image must match the selected {expected_aspect_ratio} aspect ratio"
                    )
            rgb = image.convert("RGB")
            for index, crop in enumerate(_quadrants(rgb), start=1):
                extrema = ImageStat.Stat(crop).extrema
                if all(low == high for low, high in extrema):
                    raise ValueError(f"grid image quadrant {index} has no pixel variation")
    except OSError as exc:
        raise ValueError(f"grid image cannot be decoded: {exc}") from exc
    return ValidatedImage(
        path=image_path,
        sha256=hashlib.sha256(image_path.read_bytes()).hexdigest(),
        mime_type=detected,
        width=width,
        height=height,
        byte_size=byte_size,
    )


def acquire_manual_grid_image(
    source: str | Path,
    *,
    artifact_dir: Path,
    prompt: str,
    config: GridImageConfig,
) -> GridImageAsset:
    validated = validate_grid_image(
        source,
        min_dimension=config.min_dimension,
        max_bytes=config.max_bytes,
        expected_aspect_ratio=config.aspect_ratio,
    )
    artifact_dir.mkdir(parents=True, exist_ok=True)
    extension = _extension_for_mime(validated.mime_type)
    target = artifact_dir / f"10_four_grid_image.{extension}"
    shutil.copyfile(validated.path, target)
    copied = validate_grid_image(
        target,
        min_dimension=config.min_dimension,
        max_bytes=config.max_bytes,
        expected_aspect_ratio=config.aspect_ratio,
    )
    return _asset_from_validated(copied, source="manual", prompt=prompt)


def acquire_generated_grid_image(
    provider: GridImageProvider,
    *,
    artifact_dir: Path,
    prompt: str,
    config: GridImageConfig,
) -> GridImageAsset:
    generated = provider.generate(prompt=prompt, config=config)
    extension = _extension_for_mime(generated.mime_type)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    target = artifact_dir / f"10_four_grid_image.{extension}"
    target.write_bytes(generated.content)
    validated = validate_grid_image(
        target,
        min_dimension=config.min_dimension,
        max_bytes=config.max_bytes,
        expected_aspect_ratio=config.aspect_ratio,
    )
    if validated.mime_type != generated.mime_type:
        raise ValueError(
            f"image provider declared {generated.mime_type} but returned {validated.mime_type}"
        )
    return _asset_from_validated(
        validated,
        source="generated",
        prompt=prompt,
        provider=generated.provider,
        model=generated.model,
        task_id=generated.task_id,
        aspect_ratio=generated.aspect_ratio or config.aspect_ratio,
        resolution=generated.resolution or config.resolution,
    )


def deterministic_comfyui_filename(run_id: str, sha256: str, mime_type: str) -> str:
    safe_run_id = "".join(char for char in run_id if char.isalnum() or char in {"-", "_"}) or "run"
    return f"{safe_run_id}_{sha256[:12]}.{_extension_for_mime(mime_type)}"


def _asset_from_validated(
    validated: ValidatedImage,
    *,
    source: Literal["generated", "manual"],
    prompt: str,
    provider: str = "",
    model: str = "",
    task_id: str = "",
    aspect_ratio: str = "",
    resolution: str = "",
) -> GridImageAsset:
    return GridImageAsset(
        source=source,
        local_path=str(validated.path),
        sha256=validated.sha256,
        mime_type=validated.mime_type,
        width=validated.width,
        height=validated.height,
        byte_size=validated.byte_size,
        prompt=prompt,
        provider=provider,
        model=model,
        task_id=task_id,
        aspect_ratio=aspect_ratio,
        resolution=resolution,
    )


def _balanced_indices(count: int, slots: int) -> list[int]:
    if count <= 0:
        return []
    if count == 1:
        return [0] * slots
    return [int(index * (count - 1) / (slots - 1)) for index in range(slots)]


def _quadrants(image: Image.Image) -> list[Image.Image]:
    width, height = image.size
    half_w, half_h = width // 2, height // 2
    return [
        image.crop((0, 0, half_w, half_h)),
        image.crop((half_w, 0, width, half_h)),
        image.crop((0, half_h, half_w, height)),
        image.crop((half_w, half_h, width, height)),
    ]


def _extension_for_mime(mime_type: str) -> str:
    return {
        "image/png": "png",
        "image/jpeg": "jpeg",
        "image/webp": "webp",
    }[mime_type]
