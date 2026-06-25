# LTX 2.3 Four-Grid Image Adapter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a restart-safe dual-source four-grid image stage that generates or accepts a manual 2x2 reference image, uploads it to ComfyUI, and injects it into the supplied LTX 2.3 workflow without changing the approved writing-stage order.

**Architecture:** Introduce a focused grid-image domain module and provider boundary. Both automatic and manual acquisition produce one persisted `GridImageAsset`; the existing LTX workflow adapter traces the grid guide to its exact `LoadImage` node, and the orchestrator checkpoints acquisition, validation, upload, and workflow preparation before the existing ComfyUI submission stage.

**Tech Stack:** Python 3.11+, Pydantic 2, Pillow, OpenAI Python SDK, HTTPX, FastAPI, pytest

**Design:** `docs/superpowers/specs/2026-06-25-ltx23-grid-image-adapter-design.md`

**Official API references:**

- `https://developers.openai.com/api/docs/guides/image-generation`
- `https://developers.openai.com/api/reference/resources/images/methods/generate/`

**Repository note:** The current workspace does not expose usable Git metadata to command-line Git. Execute all test and implementation steps, but do not fabricate commit hashes or commit results.

---

## File Structure

- Create `relief_story_agent/grid_image.py`: prompt compilation, image acquisition, validation, hashing, manual-copy behavior, deterministic filenames, and provider protocol.
- Create `relief_story_agent/image_providers.py`: OpenAI-compatible GPT Image provider and generated-byte response normalization.
- Create `relief_story_agent/resource_limits.py`: independent semaphores for image generation and ComfyUI submission.
- Modify `relief_story_agent/models.py`: grid image configuration, asset state, attempts, upload status, checkpoints, preview fields, and retry stage.
- Modify `relief_story_agent/ltx_workflow.py`: trace the grid guide to the exact `LoadImage` node and patch its image widget.
- Modify `relief_story_agent/comfyui.py`: image upload, upload reconciliation metadata, four-replacement planning, and preview reporting.
- Modify `relief_story_agent/orchestrator.py`: add `four_grid_asset` execution stage and checkpoint-aware recovery.
- Modify `relief_story_agent/artifacts.py`: write and index artifacts `09`, `10`, and `11`.
- Modify `relief_story_agent/config_validation.py`: validate image config, manual file, image-provider environment, and workflow topology.
- Modify `relief_story_agent/failure_policy.py`: classify grid generation, validation, upload, and topology failures.
- Modify `relief_story_agent/server.py`: inject image provider and independent resource limits; add CLI options.
- Modify `relief_story_agent/README.md`: document configuration, dual modes, artifacts, and recovery behavior.
- Modify `pyproject.toml`: add Pillow as a declared runtime dependency.
- Create `relief_story_agent/tests/fixtures/ltx23_workflow_factory.py`: sanitized 60-node structural workflow fixture.
- Create `relief_story_agent/tests/test_grid_image.py`: domain and validation tests.
- Create `relief_story_agent/tests/test_image_provider.py`: OpenAI-compatible provider tests.
- Extend `relief_story_agent/tests/test_comfyui_mapping.py`: workflow tracing, upload, patching, and preview tests.
- Extend `relief_story_agent/tests/test_orchestrator.py`: stage order, dual-source acquisition, checkpoint recovery, and artifact tests.
- Extend `relief_story_agent/tests/test_config_validation.py`: preflight tests.
- Extend `relief_story_agent/tests/test_scheduler.py`: independent concurrency-limit tests.

### Task 1: Add Grid Image Models and Dependency

**Files:**
- Modify: `pyproject.toml`
- Modify: `relief_story_agent/models.py`
- Test: `relief_story_agent/tests/test_grid_image.py`

- [ ] **Step 1: Write failing model tests**

Create `relief_story_agent/tests/test_grid_image.py`:

```python
from pathlib import Path

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
    assert config.size == "1024x1024"
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
```

- [ ] **Step 2: Verify RED**

Run:

```powershell
python -m pytest relief_story_agent/tests/test_grid_image.py -q
```

Expected: collection fails because `GridImageConfig` and `GridImageAsset` do not exist.

- [ ] **Step 3: Declare Pillow and add models**

Add `"Pillow>=10.0"` to `pyproject.toml`.

In `relief_story_agent/models.py`, add:

```python
class GridImageConfig(BaseModel):
    mode: Literal["auto", "manual_override"] = "auto"
    manual_image_path: str | None = None
    provider: Literal["openai_compatible"] = "openai_compatible"
    base_url: str = "https://api.openai.com/v1"
    api_key: str = Field(default="", exclude=True, repr=False)
    api_key_env: str = "OPENAI_API_KEY"
    model: str = "gpt-image-2"
    size: str = "1024x1024"
    quality: Literal["low", "medium", "high", "auto"] = "medium"
    output_format: Literal["png", "jpeg", "webp"] = "png"
    timeout_seconds: float = Field(default=180.0, gt=0)
    max_attempts: int = Field(default=3, ge=1, le=10)
    prompt_max_chars: int = Field(default=4000, ge=500, le=16000)
    min_dimension: int = Field(default=512, ge=64)
    max_bytes: int = Field(default=50 * 1024 * 1024, ge=1024)

    def effective_mode(self) -> Literal["auto", "manual_override"]:
        return "manual_override" if self.manual_image_path else self.mode


class GridImageAttempt(BaseModel):
    attempt_number: int
    status: Literal["running", "succeeded", "failed"] = "running"
    error_type: str = ""
    error_message: str = ""
    started_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    finished_at: str = ""


class GridImageAsset(BaseModel):
    source: Literal["generated", "manual"]
    local_path: str
    sha256: str
    mime_type: Literal["image/png", "image/jpeg", "image/webp"]
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    byte_size: int = Field(gt=0)
    prompt: str = ""
    provider: str = ""
    model: str = ""
    generated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    comfyui_filename: str = ""
    upload_status: Literal["pending", "accepted", "unknown", "rejected"] = "pending"
    upload_error: str = ""
```

Add to `ComfyUIRunConfig`:

```python
grid_image: GridImageConfig = Field(default_factory=GridImageConfig)
```

Add to `RunState`:

```python
grid_image_prompt: str = ""
grid_image_asset: GridImageAsset | None = None
grid_image_attempts: list[GridImageAttempt] = Field(default_factory=list)
grid_image_checkpoint: Literal[
    "",
    "prompt_compiled",
    "image_acquired",
    "image_validated",
    "image_uploaded",
    "workflow_patched",
] = ""
grid_image_replacements: list[dict[str, Any]] = Field(default_factory=list)
```

Add `"four_grid_asset"` to `RunRetryRequest.from_stage`.

- [ ] **Step 4: Verify GREEN**

Run:

```powershell
python -m pytest relief_story_agent/tests/test_grid_image.py -q
```

Expected: 4 tests pass.

### Task 2: Compile and Validate Four-Grid Assets

**Files:**
- Create: `relief_story_agent/grid_image.py`
- Extend: `relief_story_agent/tests/test_grid_image.py`

- [ ] **Step 1: Add failing prompt and validation tests**

Append:

```python
import io

import pytest
from PIL import Image, ImageDraw

from relief_story_agent.grid_image import (
    acquire_manual_grid_image,
    compile_four_grid_prompt,
    deterministic_comfyui_filename,
    validate_grid_image,
)


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
        {"shot_id": index + 1, "time_range": f"{index * 10}-{index * 10 + 8}s", "image_prompt": f"frame {index + 1}"}
        for index in range(8)
    ]

    prompt = compile_four_grid_prompt(storyboard, max_chars=600)

    assert "Top-left: frame 1" in prompt
    assert "Top-right: frame 3" in prompt
    assert "Bottom-left: frame 5" in prompt
    assert "Bottom-right: frame 8" in prompt
    assert len(prompt) <= 600


def test_validate_grid_image_reports_dimensions_hash_and_quadrants(tmp_path):
    path = tmp_path / "grid.png"
    _make_grid(path)

    validated = validate_grid_image(path, min_dimension=512, max_bytes=10_000_000)

    assert validated.mime_type == "image/png"
    assert validated.width == 1024
    assert validated.height == 1024
    assert len(validated.sha256) == 64


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
    _make_grid(source)
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
    assert deterministic_comfyui_filename(
        "run_demo",
        "abcdef0123456789",
        "image/png",
    ) == "run_demo_abcdef012345.png"
```

- [ ] **Step 2: Verify RED**

Run:

```powershell
python -m pytest relief_story_agent/tests/test_grid_image.py -q
```

Expected: imports fail because `grid_image.py` does not exist.

- [ ] **Step 3: Implement the domain module**

Create `relief_story_agent/grid_image.py` with:

```python
from __future__ import annotations

import hashlib
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from PIL import Image, ImageStat

from .models import GridImageAsset, GridImageConfig


@dataclass(frozen=True)
class GeneratedImage:
    content: bytes
    mime_type: str
    provider: str
    model: str


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


def validate_grid_image(path: str | Path, *, min_dimension: int, max_bytes: int) -> ValidatedImage:
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
            if abs(width / height - 1.0) > 0.08:
                raise ValueError("grid image must be approximately square for a 2x2 layout")
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
    )
    artifact_dir.mkdir(parents=True, exist_ok=True)
    extension = _extension_for_mime(validated.mime_type)
    target = artifact_dir / f"10_four_grid_image.{extension}"
    shutil.copyfile(validated.path, target)
    copied = validate_grid_image(
        target,
        min_dimension=config.min_dimension,
        max_bytes=config.max_bytes,
    )
    return _asset_from_validated(copied, source="manual", prompt=prompt)


def deterministic_comfyui_filename(run_id: str, sha256: str, mime_type: str) -> str:
    safe_run_id = "".join(char for char in run_id if char.isalnum() or char in {"-", "_"}) or "run"
    return f"{safe_run_id}_{sha256[:12]}.{_extension_for_mime(mime_type)}"


def _asset_from_validated(
    validated: ValidatedImage,
    *,
    source: str,
    prompt: str,
    provider: str = "",
    model: str = "",
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
```

Task 3 reuses `_asset_from_validated` directly; do not duplicate asset
construction logic.

- [ ] **Step 4: Verify GREEN**

Run:

```powershell
python -m pytest relief_story_agent/tests/test_grid_image.py -q
```

Expected: all domain tests pass.

### Task 3: Add the GPT Image 2 Provider

**Files:**
- Create: `relief_story_agent/image_providers.py`
- Modify: `relief_story_agent/grid_image.py`
- Create: `relief_story_agent/tests/test_image_provider.py`
- Extend: `relief_story_agent/tests/test_grid_image.py`

- [ ] **Step 1: Write failing provider tests**

Create `relief_story_agent/tests/test_image_provider.py`:

```python
import base64

from relief_story_agent.image_providers import OpenAICompatibleGridImageProvider
from relief_story_agent.models import GridImageConfig


class FakeImages:
    def __init__(self, payload):
        self.payload = payload
        self.kwargs = None

    def generate(self, **kwargs):
        self.kwargs = kwargs
        return self.payload


class FakeClient:
    def __init__(self, payload):
        self.images = FakeImages(payload)


class ImageItem:
    def __init__(self, content):
        self.b64_json = base64.b64encode(content).decode("ascii")


class ImageResponse:
    def __init__(self, content):
        self.data = [ImageItem(content)]
        self.output_format = "png"


def test_provider_uses_current_gpt_image_parameters():
    client = FakeClient(ImageResponse(b"png-bytes"))
    provider = OpenAICompatibleGridImageProvider(client_factory=lambda config: client)
    config = GridImageConfig(
        model="gpt-image-2",
        size="1024x1024",
        quality="medium",
        output_format="png",
    )

    generated = provider.generate(prompt="four frames", config=config)

    assert generated.content == b"png-bytes"
    assert generated.mime_type == "image/png"
    assert client.images.kwargs == {
        "model": "gpt-image-2",
        "prompt": "four frames",
        "size": "1024x1024",
        "quality": "medium",
        "output_format": "png",
        "n": 1,
    }


def test_provider_rejects_empty_image_response():
    client = FakeClient(type("Response", (), {"data": []})())
    provider = OpenAICompatibleGridImageProvider(client_factory=lambda config: client)

    try:
        provider.generate(prompt="four frames", config=GridImageConfig())
    except ValueError as exc:
        assert "no image data" in str(exc)
    else:
        raise AssertionError("expected ValueError")
```

Append to `test_grid_image.py`:

```python
from relief_story_agent.grid_image import GeneratedImage, acquire_generated_grid_image


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
    _make_grid(source)
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
```

- [ ] **Step 2: Verify RED**

Run:

```powershell
python -m pytest relief_story_agent/tests/test_image_provider.py relief_story_agent/tests/test_grid_image.py -q
```

Expected: imports fail because provider and generated acquisition do not exist.

- [ ] **Step 3: Implement provider and generated acquisition**

Create `relief_story_agent/image_providers.py`:

```python
from __future__ import annotations

import base64
import os
from typing import Callable

from openai import OpenAI

from .grid_image import GeneratedImage
from .models import GridImageConfig


class OpenAICompatibleGridImageProvider:
    def __init__(self, client_factory: Callable[[GridImageConfig], object] | None = None):
        self.client_factory = client_factory or self._build_client

    def generate(self, *, prompt: str, config: GridImageConfig) -> GeneratedImage:
        client = self.client_factory(config)
        response = client.images.generate(
            model=config.model,
            prompt=prompt,
            size=config.size,
            quality=config.quality,
            output_format=config.output_format,
            n=1,
        )
        data = list(getattr(response, "data", None) or [])
        if not data or not getattr(data[0], "b64_json", None):
            raise ValueError("image provider returned no image data")
        content = base64.b64decode(data[0].b64_json, validate=True)
        return GeneratedImage(
            content=content,
            mime_type={
                "png": "image/png",
                "jpeg": "image/jpeg",
                "webp": "image/webp",
            }[config.output_format],
            provider=config.provider,
            model=config.model,
        )

    @staticmethod
    def _build_client(config: GridImageConfig) -> OpenAI:
        api_key = config.api_key or os.environ.get(config.api_key_env, "")
        if not api_key:
            raise ValueError(
                f"Missing environment variable for image API key: {config.api_key_env}"
            )
        return OpenAI(
            base_url=config.base_url,
            api_key=api_key,
            max_retries=0,
            timeout=config.timeout_seconds,
        )
```

Add to `grid_image.py`:

```python
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
    )
```

- [ ] **Step 4: Verify GREEN**

Run:

```powershell
python -m pytest relief_story_agent/tests/test_image_provider.py relief_story_agent/tests/test_grid_image.py -q
```

Expected: all tests pass.

### Task 4: Detect and Patch the Real LTX Grid Topology

**Files:**
- Create: `relief_story_agent/tests/fixtures/__init__.py`
- Create: `relief_story_agent/tests/fixtures/ltx23_workflow_factory.py`
- Modify: `relief_story_agent/ltx_workflow.py`
- Extend: `relief_story_agent/tests/test_comfyui_mapping.py`

- [ ] **Step 1: Create a sanitized 60-node fixture factory**

Create `relief_story_agent/tests/fixtures/ltx23_workflow_factory.py`:

```python
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
```

- [ ] **Step 2: Add failing topology and immutability tests**

Append to `test_comfyui_mapping.py`:

```python
import copy

from relief_story_agent.ltx_workflow import (
    find_ltx_injection_points,
    patch_ltx_litegraph_workflow,
)
from relief_story_agent.tests.fixtures.ltx23_workflow_factory import (
    build_sanitized_ltx23_workflow,
)


def test_real_shape_fixture_detects_all_four_injection_points():
    workflow = build_sanitized_ltx23_workflow()

    points = find_ltx_injection_points(workflow)

    assert len(workflow["nodes"]) == 60
    assert points.json_node_id == "202"
    assert points.seed_node_id == "37"
    assert points.filename_prefix_node_id == "79"
    assert points.grid_image_node_id == "196"
    assert points.grid_image_input == "image"
    assert points.grid_columns == 2
    assert points.grid_rows == 2


def test_patch_changes_only_declared_four_inputs():
    workflow = build_sanitized_ltx23_workflow()
    original = copy.deepcopy(workflow)

    patched = patch_ltx_litegraph_workflow(
        workflow,
        ltx_payload={
            "prompt": "new",
            "frame_indices": "0,24,48,72",
            "strengths": "0.7,0.7,0.7,0.7",
            "duration_seconds": 4,
        },
        seed=99,
        filename_prefix="run_demo",
        grid_image_filename="run_demo_hash.png",
    )

    assert workflow == original
    assert patched["196"]["inputs"]["image"] == "run_demo_hash.png"
    assert patched["37"]["inputs"]["noise_seed"] == 99
    assert patched["79"]["inputs"]["filename_prefix"] == "run_demo"
    assert '"prompt": "new"' in patched["202"]["inputs"]["text"]


def test_grid_topology_rejects_ambiguous_upstream_load_images():
    workflow = build_sanitized_ltx23_workflow()
    workflow["nodes"].append(
        {
            "id": 197,
            "type": "LoadImage",
            "inputs": [{"name": "image", "widget": {"name": "image"}}],
            "outputs": [{"name": "IMAGE"}],
            "widgets_values": ["other.png"],
        }
    )
    workflow["links"].append([452, 197, 0, 221, 0, "IMAGE"])

    with pytest.raises(ValueError, match="exactly one"):
        find_ltx_injection_points(workflow)
```

- [ ] **Step 3: Verify RED**

Run:

```powershell
python -m pytest relief_story_agent/tests/test_comfyui_mapping.py -q -k "injection_points or declared_four or ambiguous"
```

Expected: failures because grid fields and `grid_image_filename` do not exist.

- [ ] **Step 4: Extend injection-point tracing and patching**

Modify the dataclass in `ltx_workflow.py`:

```python
@dataclass(frozen=True)
class LTXInjectionPoints:
    json_node_id: str
    seed_node_id: str | None = None
    filename_prefix_node_id: str | None = None
    grid_image_node_id: str | None = None
    grid_image_input: str = "image"
    grid_columns: int | None = None
    grid_rows: int | None = None
```

Add graph helpers:

```python
def _find_grid_injection(workflow: dict[str, Any]) -> tuple[str | None, int | None, int | None]:
    nodes = {str(node.get("id")): node for node in workflow.get("nodes", [])}
    links = [link for link in workflow.get("links", []) if isinstance(link, list) and len(link) >= 5]
    guides = [node for node in nodes.values() if node.get("type") == "TD_LTXVAddGuideFromGrid"]
    if not guides:
        return None, None, None
    if len(guides) != 1:
        raise ValueError("LTX workflow must contain exactly one TD_LTXVAddGuideFromGrid node")
    guide = guides[0]
    guide_id = str(guide.get("id"))
    grid_input = next(
        (item for item in guide.get("inputs") or [] if item.get("name") == "grid_image"),
        None,
    )
    if not grid_input:
        raise ValueError("grid guide is missing grid_image input")
    incoming = [
        link for link in links
        if str(link[3]) == guide_id and int(link[4]) == (guide.get("inputs") or []).index(grid_input)
    ]
    load_ids = {
        str(link[1])
        for link in incoming
        if nodes.get(str(link[1]), {}).get("type") == "LoadImage"
    }
    if len(load_ids) != 1:
        raise ValueError("grid_image must resolve to exactly one LoadImage node")
    columns = _read_required_int_widget(guide, "columns")
    rows = _read_required_int_widget(guide, "rows")
    return next(iter(load_ids)), columns, rows


def _read_required_int_widget(node: dict[str, Any], name: str) -> int:
    inputs = node.get("inputs") or []
    index = next((i for i, item in enumerate(inputs) if item.get("name") == name), None)
    if index is None:
        raise ValueError(f"grid guide is missing {name} widget")
    found, value = _read_widget_value(node, name, index)
    if not found:
        raise ValueError(f"grid guide is missing {name} value")
    return int(value)
```

Call `_find_grid_injection` from `find_ltx_injection_points` and populate the new fields.

Change `patch_ltx_litegraph_workflow` signature:

```python
def patch_ltx_litegraph_workflow(
    workflow: dict[str, Any],
    *,
    ltx_payload: dict[str, Any],
    seed: int | None = None,
    filename_prefix: str | None = None,
    grid_image_filename: str | None = None,
) -> dict[str, Any]:
```

Before conversion, patch:

```python
if points.grid_image_node_id:
    if not grid_image_filename:
        raise ValueError("LTX grid workflow requires an uploaded grid image filename")
    image_node = _find_node(patched, points.grid_image_node_id)
    _write_widget_value(image_node, points.grid_image_input, grid_image_filename)
```

- [ ] **Step 5: Verify GREEN**

Run:

```powershell
python -m pytest relief_story_agent/tests/test_comfyui_mapping.py -q -k "injection_points or declared_four or ambiguous"
```

Expected: selected tests pass.

### Task 5: Upload Images and Plan Four Replacements

**Files:**
- Modify: `relief_story_agent/comfyui.py`
- Extend: `relief_story_agent/tests/test_comfyui_mapping.py`

- [ ] **Step 1: Write failing upload and preview tests**

Append:

```python
from relief_story_agent.comfyui import (
    upload_grid_image,
    preview_storyboard_submission,
)
from relief_story_agent.models import GridImageAsset


def test_upload_grid_image_posts_multipart_and_normalizes_filename(tmp_path):
    image_path = tmp_path / "grid.png"
    image_path.write_bytes(b"image-bytes")
    requests = []

    def handler(request: httpx.Request):
        requests.append(request)
        assert request.url.path == "/upload/image"
        assert "multipart/form-data" in request.headers["content-type"]
        return httpx.Response(
            200,
            json={"name": "run_demo_hash.png", "subfolder": "", "type": "input"},
        )

    result = upload_grid_image(
        "http://comfy.local",
        image_path,
        destination_name="run_demo_hash.png",
        client=HTTPX_CLIENT(transport=httpx.MockTransport(handler)),
    )

    assert result == "run_demo_hash.png"
    assert len(requests) == 1


def test_preview_reports_four_replacements_without_side_effects(tmp_path):
    workflow_path = tmp_path / "workflow.json"
    workflow_path.write_text(
        json.dumps(build_sanitized_ltx23_workflow(), ensure_ascii=False),
        encoding="utf-8",
    )
    asset = GridImageAsset(
        source="manual",
        local_path=str(tmp_path / "grid.png"),
        sha256="a" * 64,
        mime_type="image/png",
        width=1024,
        height=1024,
        byte_size=100,
        comfyui_filename="run_demo_aaaaaaaaaaaa.png",
        upload_status="accepted",
    )

    preview = preview_storyboard_submission(
        ComfyUIRunConfig(enabled=True, workflow_api_path=str(workflow_path)),
        [{"shot_id": 1, "time_range": "0-4s", "image_prompt": "frame", "comfyui_inputs": {"seed": 7}}],
        "run_demo",
        duration_seconds=4,
        grid_image_asset=asset,
    )

    replacements = preview["items"][0]["replacements"]
    assert [item["key"] for item in replacements] == [
        "grid_image",
        "ltx_payload",
        "seed",
        "filename_prefix",
    ]
    assert preview["will_enqueue"] is False
```

- [ ] **Step 2: Verify RED**

Run:

```powershell
python -m pytest relief_story_agent/tests/test_comfyui_mapping.py -q -k "upload_grid_image or four_replacements"
```

Expected: failures because upload and asset-aware preview are missing.

- [ ] **Step 3: Implement upload and asset-aware planning**

Add:

```python
def upload_grid_image(
    endpoint: str,
    image_path: str | Path,
    *,
    destination_name: str,
    client: httpx.Client | None = None,
) -> str:
    path = Path(image_path)
    owns_client = client is None
    active_client = client or httpx.Client(timeout=120.0)
    try:
        with path.open("rb") as handle:
            response = active_client.post(
                endpoint.rstrip("/") + "/upload/image",
                data={"type": "input", "overwrite": "true"},
                files={"image": (destination_name, handle, _mime_for_path(path))},
            )
        response.raise_for_status()
        payload = response.json()
        name = str(payload.get("name") or destination_name)
        subfolder = str(payload.get("subfolder") or "").strip("/\\")
        return f"{subfolder}/{name}" if subfolder else name
    finally:
        if owns_client:
            active_client.close()
```

Add `grid_image_asset: GridImageAsset | None = None` and
`allow_unuploaded_grid_image: bool = False` to:

- `plan_storyboard_workflows`
- `preview_storyboard_submission`
- `submit_storyboard`
- `enqueue_storyboard`

For LiteGraph mode, require an accepted asset when
`points.grid_image_node_id` is present unless the caller explicitly set
`allow_unuploaded_grid_image=True`. Pass `asset.comfyui_filename` into
`patch_ltx_litegraph_workflow`, and put the `grid_image` replacement first:

```python
if points.grid_image_node_id:
    if not grid_image_asset:
        raise ValueError("LTX grid workflow requires a grid image asset")
    if grid_image_asset.upload_status != "accepted" and not allow_unuploaded_grid_image:
        raise ValueError("LTX grid workflow requires an accepted uploaded grid image asset")
    replacements.append(
        {
            "key": "grid_image",
            "node": points.grid_image_node_id,
            "input": points.grid_image_input,
            "source": "grid_image_asset.comfyui_filename",
            "value_preview": grid_image_asset.comfyui_filename,
        }
    )
```

Keep the remaining replacement order `ltx_payload`, `seed`, `filename_prefix`.
`preview_storyboard_submission` passes the flag it receives through to
planning. `submit_storyboard` always calls planning with
`allow_unuploaded_grid_image=False`.

- [ ] **Step 4: Verify GREEN**

Run:

```powershell
python -m pytest relief_story_agent/tests/test_comfyui_mapping.py -q -k "upload_grid_image or four_replacements"
```

Expected: selected tests pass.

### Task 6: Add the Checkpointed Orchestrator Stage

**Files:**
- Create: `relief_story_agent/resource_limits.py`
- Modify: `relief_story_agent/orchestrator.py`
- Modify: `relief_story_agent/failure_policy.py`
- Extend: `relief_story_agent/tests/test_orchestrator.py`
- Extend: `relief_story_agent/tests/test_failure_policy.py`

- [ ] **Step 1: Write failing stage-order and recovery tests**

Add a fake image provider to `test_orchestrator.py`:

```python
import json

import httpx
from PIL import Image, ImageDraw

from relief_story_agent.models import ComfyUIRunConfig, RunRequest, RunRetryRequest
from relief_story_agent.tests.fixtures.ltx23_workflow_factory import (
    build_sanitized_ltx23_workflow,
)


class FakeGeneratedGridProvider:
    def __init__(self, image_bytes):
        self.image_bytes = image_bytes
        self.calls = 0

    def generate(self, *, prompt, config):
        from relief_story_agent.grid_image import GeneratedImage
        self.calls += 1
        return GeneratedImage(
            content=self.image_bytes,
            mime_type="image/png",
            provider="fake",
            model=config.model,
        )


def _grid_png_bytes(tmp_path):
    path = tmp_path / "fixture_grid.png"
    image = Image.new("RGB", (1024, 1024), "white")
    draw = ImageDraw.Draw(image)
    colors = ["red", "green", "blue", "yellow"]
    for index, color in enumerate(colors):
        left = (index % 2) * 512
        top = (index // 2) * 512
        image.paste(color, (left, top, left + 512, top + 512))
        draw.line((left + 20, top + 20, left + 492, top + 492), fill="black", width=8)
    image.save(path)
    return path.read_bytes()


def _write_grid_workflow(tmp_path):
    path = tmp_path / "workflow.json"
    path.write_text(
        json.dumps(build_sanitized_ltx23_workflow(), ensure_ascii=False),
        encoding="utf-8",
    )
    return path


def _grid_request(tmp_path, *, output_root=None):
    return RunRequest(
        idea="grid run",
        approval_mode="auto",
        output_root=str(output_root or (tmp_path / "runs")),
        comfyui=ComfyUIRunConfig(
            enabled=True,
            workflow_api_path=str(_write_grid_workflow(tmp_path)),
        ),
    )


def _prepare_grid_run(tmp_path, provider):
    store = InMemoryRunStore()
    orchestrator = StoryRunOrchestrator(
        provider=FakeModelProvider.minimal_success(),
        store=store,
        grid_image_provider=provider,
    )
    return orchestrator, orchestrator.prepare_run(_grid_request(tmp_path))
```

Add tests:

```python
def test_four_grid_stage_runs_after_prompt_audit_before_artifacts_and_comfyui(
    tmp_path,
    monkeypatch,
):
    provider = FakeGeneratedGridProvider(_grid_png_bytes(tmp_path))
    workflow_path = _write_grid_workflow(tmp_path)
    submitted = []
    monkeypatch.setattr(
        "relief_story_agent.orchestrator.upload_grid_image",
        lambda *args, **kwargs: "run_grid.png",
    )
    monkeypatch.setattr(
        "relief_story_agent.orchestrator.submit_storyboard",
        lambda *args, **kwargs: submitted.append(kwargs["grid_image_asset"]) or [],
    )
    orchestrator = StoryRunOrchestrator(
        provider=FakeModelProvider.minimal_success(),
        store=InMemoryRunStore(),
        grid_image_provider=provider,
    )

    run = orchestrator.create_run(
        RunRequest(
            idea="grid stage",
            approval_mode="auto",
            output_root=str(tmp_path / "runs"),
            comfyui=ComfyUIRunConfig(
                enabled=True,
                workflow_api_path=str(workflow_path),
            ),
        )
    )

    completed = [
        event.stage for event in run.events if event.event_type == "stage_completed"
    ]
    assert completed.index("gpt_prompt_audit") < completed.index("four_grid_asset")
    assert completed.index("four_grid_asset") < completed.index("artifacts")
    assert completed.index("artifacts") < completed.index("comfyui")
    assert run.grid_image_checkpoint == "workflow_patched"
    assert run.grid_image_asset.upload_status == "accepted"
    assert submitted[0].comfyui_filename == "run_grid.png"


def test_retry_after_upload_failure_reuses_acquired_image(tmp_path, monkeypatch):
    provider = FakeGeneratedGridProvider(_grid_png_bytes(tmp_path))
    calls = 0

    def flaky_upload(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise httpx.ConnectError(
                "offline",
                request=httpx.Request("POST", "http://comfy.local/upload/image"),
            )
        return "reused.png"

    monkeypatch.setattr("relief_story_agent.orchestrator.upload_grid_image", flaky_upload)
    orchestrator, run = _prepare_grid_run(tmp_path, provider)
    first = orchestrator.execute_scheduled(run.run_id)
    assert first.status == "failed"
    assert first.grid_image_checkpoint == "image_validated"
    assert provider.calls == 1

    orchestrator.queue_retry(run.run_id, RunRetryRequest(from_stage="four_grid_asset"))
    second = orchestrator.execute_scheduled(run.run_id)

    assert second.grid_image_asset.upload_status == "accepted"
    assert provider.calls == 1
```

Add to `test_failure_policy.py`:

```python
def test_grid_image_validation_is_non_retryable():
    record = classify_failure(
        "four_grid_asset",
        ValueError("grid image quadrant 2 has no pixel variation"),
    )

    assert record.category == "validation"
    assert record.code == "grid_image_invalid"
    assert record.retryable is False
```

- [ ] **Step 2: Verify RED**

Run:

```powershell
python -m pytest relief_story_agent/tests/test_orchestrator.py relief_story_agent/tests/test_failure_policy.py -q -k "four_grid or upload_failure or grid_image_validation"
```

Expected: failures because stage, injection, checkpoints, and classifier rules are missing.

- [ ] **Step 3: Add resource limits**

Create `relief_story_agent/resource_limits.py`:

```python
from contextlib import contextmanager
from threading import BoundedSemaphore


class ExecutionResourceLimits:
    def __init__(
        self,
        *,
        image_generation_concurrency: int = 2,
        comfyui_submission_concurrency: int = 1,
    ):
        if image_generation_concurrency < 1 or comfyui_submission_concurrency < 1:
            raise ValueError("resource concurrency limits must be at least 1")
        self.image_generation_concurrency = image_generation_concurrency
        self.comfyui_submission_concurrency = comfyui_submission_concurrency
        self._image = BoundedSemaphore(image_generation_concurrency)
        self._comfyui = BoundedSemaphore(comfyui_submission_concurrency)

    @contextmanager
    def image_generation(self):
        with self._image:
            yield

    @contextmanager
    def comfyui_submission(self):
        with self._comfyui:
            yield

    def status(self) -> dict[str, int]:
        return {
            "image_generation_concurrency": self.image_generation_concurrency,
            "comfyui_submission_concurrency": self.comfyui_submission_concurrency,
        }
```

- [ ] **Step 4: Wire the stage and checkpoints**

Add imports to `orchestrator.py`:

```python
import httpx
import time
from pathlib import Path

from .models import GridImageAsset, GridImageAttempt, GridImageConfig
from .grid_image import (
    GridImageProvider,
    acquire_generated_grid_image,
    acquire_manual_grid_image,
    compile_four_grid_prompt,
    deterministic_comfyui_filename,
)
from .image_providers import OpenAICompatibleGridImageProvider
from .comfyui import (
    detect_workflow_format,
    load_workflow,
    preview_storyboard_submission,
    upload_grid_image,
)
from .ltx_workflow import find_ltx_injection_points
from .resource_limits import ExecutionResourceLimits
```

Extend `StoryRunOrchestrator.__init__` with:

```python
grid_image_provider: GridImageProvider | None = None,
resource_limits: ExecutionResourceLimits | None = None,
```

Assign both fields in `__init__`:

```python
self.grid_image_provider = grid_image_provider or OpenAICompatibleGridImageProvider()
self.resource_limits = resource_limits or ExecutionResourceLimits()
```

Add a direct topology helper so stage selection does not depend on API response
format:

```python
def _requires_grid_asset(self, run: RunState) -> bool:
    config = run.request.comfyui
    if not config or not config.enabled or not config.workflow_api_path:
        return False
    workflow = load_workflow(config.workflow_api_path)
    if detect_workflow_format(workflow) != "litegraph":
        return False
    return find_ltx_injection_points(workflow).grid_image_node_id is not None
```

Build the tail in `_stage_sequence` as:

```python
requires_grid = self._requires_grid_asset(run)
if requires_grid:
    stages.append("four_grid_asset")
if run.request.output_root or requires_grid:
    stages.append("artifacts")
if run.request.comfyui and run.request.comfyui.enabled:
    stages.append("comfyui")
```

Apply the same tail construction when `start_stage == "gpt_prompt_reviser"`.
This guarantees artifacts `09-11` are written even when the user did not set an
explicit `output_root`.

Add handler:

```python
"four_grid_asset": self._run_four_grid_asset,
```

Implement `_run_four_grid_asset`:

```python
def _acquire_generated_grid_asset(
    self,
    run: RunState,
    *,
    artifact_dir: Path,
    image_config: GridImageConfig,
) -> GridImageAsset:
    for attempt_number in range(1, image_config.max_attempts + 1):
        attempt = GridImageAttempt(attempt_number=attempt_number)
        run.grid_image_attempts.append(attempt)
        self.store.save(run)
        try:
            with self.resource_limits.image_generation():
                asset = acquire_generated_grid_image(
                    self.grid_image_provider,
                    artifact_dir=artifact_dir,
                    prompt=run.grid_image_prompt,
                    config=image_config,
                )
        except Exception as exc:
            attempt.status = "failed"
            attempt.error_type = type(exc).__name__
            attempt.error_message = str(exc)
            attempt.finished_at = datetime.now(timezone.utc).isoformat()
            self.store.save(run)
            failure = classify_failure("four_grid_asset", exc)
            if not failure.retryable or attempt_number == image_config.max_attempts:
                raise
            time.sleep(min(2 ** (attempt_number - 1), 8))
            continue
        attempt.status = "succeeded"
        attempt.finished_at = datetime.now(timezone.utc).isoformat()
        self.store.save(run)
        return asset
    raise RuntimeError("grid image generation exhausted without a result")


def _run_four_grid_asset(self, run: RunState) -> None:
    run.current_stage = "four_grid_asset"
    config = run.request.comfyui
    if not config:
        raise ValueError("ComfyUI config is required for four_grid_asset")
    image_config = config.grid_image
    storyboard = run.final_storyboard or run.storyboard
    artifact_dir = Path(run.request.output_root or "runs") / run.run_id
    artifact_dir.mkdir(parents=True, exist_ok=True)
    run.artifact_dir = str(artifact_dir)

    if not run.grid_image_prompt:
        run.grid_image_prompt = compile_four_grid_prompt(
            storyboard,
            max_chars=image_config.prompt_max_chars,
        )
        run.grid_image_checkpoint = "prompt_compiled"
        self.store.save(run)

    if run.grid_image_asset is None:
        if image_config.effective_mode() == "manual_override":
            run.grid_image_asset = acquire_manual_grid_image(
                image_config.manual_image_path or "",
                artifact_dir=artifact_dir,
                prompt=run.grid_image_prompt,
                config=image_config,
            )
        else:
            run.grid_image_asset = self._acquire_generated_grid_asset(
                run,
                artifact_dir=artifact_dir,
                image_config=image_config,
            )
        run.grid_image_checkpoint = "image_acquired"
        self.store.save(run)

    run.grid_image_checkpoint = "image_validated"
    asset = run.grid_image_asset
    if asset.upload_status != "accepted":
        destination = deterministic_comfyui_filename(
            run.run_id,
            asset.sha256,
            asset.mime_type,
        )
        try:
            asset.comfyui_filename = upload_grid_image(
                config.endpoint,
                asset.local_path,
                destination_name=destination,
            )
            asset.upload_status = "accepted"
            asset.upload_error = ""
        except httpx.TransportError as exc:
            asset.comfyui_filename = destination
            asset.upload_status = "unknown"
            asset.upload_error = str(exc)
            self.store.save(run)
            raise
        run.grid_image_checkpoint = "image_uploaded"
        self.store.save(run)

    preview = preview_storyboard_submission(
        config,
        storyboard,
        run.run_id,
        duration_seconds=run.request.duration_seconds,
        grid_image_asset=asset,
    )
    run.grid_image_replacements = preview["items"][0]["replacements"]
    run.grid_image_checkpoint = "workflow_patched"
    self.store.save(run)
```

In `_run_comfyui`, wrap only `submit_storyboard` with:

```python
with self.resource_limits.comfyui_submission():
    run.comfyui_submissions = submit_storyboard(
        run.request.comfyui,
        run.final_storyboard or run.storyboard,
        run.run_id,
        duration_seconds=run.request.duration_seconds,
        existing_submissions=run.comfyui_submissions,
        on_update=persist_submissions,
        grid_image_asset=run.grid_image_asset,
    )
```

Do not hold this semaphore while waiting for or downloading outputs.

- [ ] **Step 5: Classify grid failures**

In `failure_policy.py`, add before generic workflow matching:

```python
if stage == "four_grid_asset" and (
    "grid image" in lower
    or "quadrant" in lower
    or "loadimage" in lower
    or "grid_image" in lower
):
    return "validation", "grid_image_invalid", False
```

Transport, timeout, HTTP 429, and HTTP 5xx continue through existing retryable
branches.

- [ ] **Step 6: Verify GREEN**

Run:

```powershell
python -m pytest relief_story_agent/tests/test_orchestrator.py relief_story_agent/tests/test_failure_policy.py -q -k "four_grid or upload_failure or grid_image_validation"
```

Expected: selected tests pass.

### Task 7: Add Artifacts, API Preview, and Preflight Validation

**Files:**
- Modify: `relief_story_agent/artifacts.py`
- Modify: `relief_story_agent/models.py`
- Modify: `relief_story_agent/api.py`
- Modify: `relief_story_agent/config_validation.py`
- Extend: `relief_story_agent/tests/test_artifacts.py`
- Extend: `relief_story_agent/tests/test_comfyui_mapping.py`
- Extend: `relief_story_agent/tests/test_config_validation.py`

- [ ] **Step 1: Write failing artifact and API tests**

In `test_artifacts.py`, add:

```python
from PIL import Image, ImageDraw

from relief_story_agent.grid_image import validate_grid_image
from relief_story_agent.models import GridImageAsset


def _completed_run_with_grid_asset(tmp_path):
    image_path = tmp_path / "source.png"
    image = Image.new("RGB", (1024, 1024), "white")
    draw = ImageDraw.Draw(image)
    for index, color in enumerate(["red", "green", "blue", "yellow"]):
        left = (index % 2) * 512
        top = (index // 2) * 512
        image.paste(color, (left, top, left + 512, top + 512))
        draw.line((left + 20, top + 20, left + 492, top + 492), fill="black", width=8)
    image.save(image_path)
    validated = validate_grid_image(
        image_path,
        min_dimension=512,
        max_bytes=10_000_000,
    )
    return RunState(
        run_id="run_grid_artifacts",
        request=RunRequest(
            idea="artifact grid",
            output_root=str(tmp_path / "runs"),
        ),
        status="completed",
        script={"duration_seconds": 4},
        storyboard=[
            {
                "shot_id": 1,
                "time_range": "0-4s",
                "description": "frame",
                "image_prompt": "frame",
                "negative_prompt": "",
                "comfyui_inputs": {"seed": 7},
            }
        ],
        final_storyboard=[
            {
                "shot_id": 1,
                "time_range": "0-4s",
                "description": "frame",
                "image_prompt": "frame",
                "negative_prompt": "",
                "comfyui_inputs": {"seed": 7},
            }
        ],
        grid_image_prompt="compiled prompt",
        grid_image_asset=GridImageAsset(
            source="manual",
            local_path=str(image_path),
            sha256=validated.sha256,
            mime_type="image/png",
            width=validated.width,
            height=validated.height,
            byte_size=validated.byte_size,
            comfyui_filename="run_grid_artifacts_hash.png",
            upload_status="accepted",
        ),
        grid_image_checkpoint="workflow_patched",
    )


def test_grid_image_artifacts_use_09_to_11_without_overwriting_timeline(tmp_path):
    run = _completed_run_with_grid_asset(tmp_path)

    artifact_dir = write_run_artifacts(run)

    assert (artifact_dir / "08_timeline.json").exists()
    assert (artifact_dir / "09_four_grid_prompt.json").exists()
    assert (artifact_dir / "10_four_grid_image.png").exists()
    assert (artifact_dir / "11_comfyui_upload.json").exists()
    manifest = json.loads((artifact_dir / "00_manifest.json").read_text(encoding="utf-8"))
    assert manifest["grid_image_asset"]["sha256"] == run.grid_image_asset.sha256
```

In both `test_comfyui_mapping.py` and `test_config_validation.py`, add:

```python
from relief_story_agent.tests.fixtures.ltx23_workflow_factory import (
    build_sanitized_ltx23_workflow,
)


def _write_sanitized_workflow(tmp_path):
    path = tmp_path / "ltx23_fixture.json"
    path.write_text(
        json.dumps(build_sanitized_ltx23_workflow(), ensure_ascii=False),
        encoding="utf-8",
    )
    return path
```

Add API assertions to `test_comfyui_mapping.py`:

```python
from PIL import Image, ImageDraw


def test_analyze_workflow_reports_grid_requirements(tmp_path):
    workflow_path = _write_sanitized_workflow(tmp_path)
    app = create_app(StoryRunOrchestrator(provider=FakeModelProvider.minimal_success()))

    with TestClient(app) as client:
        response = client.post(
            "/api/comfyui/analyze-workflow",
            json={
                "comfyui": {
                    "enabled": True,
                    "workflow_api_path": str(workflow_path),
                }
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["grid_asset_required"] is True
    assert body["ltx_injection_points"]["grid_image_node_id"] == "196"
    assert body["grid_shape"] == {"columns": 2, "rows": 2}
```

Add preflight tests to `test_config_validation.py`:

```python
from relief_story_agent.config_validation import validate_run_configuration
from relief_story_agent.model_config import ModelConfigRegistry
from relief_story_agent.models import GridImageConfig


def test_preflight_rejects_missing_manual_grid_image(tmp_path):
    request = RunRequest(
        idea="manual missing",
        comfyui=ComfyUIRunConfig(
            enabled=True,
            workflow_api_path=str(_write_sanitized_workflow(tmp_path)),
            grid_image=GridImageConfig(
                mode="manual_override",
                manual_image_path=str(tmp_path / "missing.png"),
            ),
        ),
    )

    result = validate_run_configuration(request, ModelConfigRegistry())
    check = next(item for item in result["checks"] if item["name"] == "grid_image")

    assert check["status"] == "failed"
    assert "not found" in check["message"]


def test_preview_manual_path_validates_without_upload_or_generation(tmp_path, monkeypatch):
    image_path = tmp_path / "manual.png"
    image = Image.new("RGB", (1024, 1024), "white")
    draw = ImageDraw.Draw(image)
    for index, color in enumerate(["red", "green", "blue", "yellow"]):
        left = (index % 2) * 512
        top = (index // 2) * 512
        image.paste(color, (left, top, left + 512, top + 512))
        draw.line((left + 20, top + 20, left + 492, top + 492), fill="black", width=8)
    image.save(image_path)
    workflow_path = _write_sanitized_workflow(tmp_path)
    monkeypatch.setattr(
        "relief_story_agent.comfyui.upload_grid_image",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("preview must not upload")
        ),
    )

    preview = preview_storyboard_submission(
        ComfyUIRunConfig(
            enabled=True,
            workflow_api_path=str(workflow_path),
            grid_image=GridImageConfig(
                mode="manual_override",
                manual_image_path=str(image_path),
            ),
        ),
        [{"shot_id": 1, "time_range": "0-4s", "image_prompt": "frame"}],
        "preview_manual",
        duration_seconds=4,
    )

    image_replacement = preview["items"][0]["replacements"][0]
    assert image_replacement["key"] == "grid_image"
    assert image_replacement["resolution"] == "exact_manual_asset"
    assert preview["will_enqueue"] is False
```

- [ ] **Step 2: Verify RED**

Run:

```powershell
python -m pytest relief_story_agent/tests/test_artifacts.py relief_story_agent/tests/test_comfyui_mapping.py relief_story_agent/tests/test_config_validation.py -q -k "grid_image_artifacts or grid_requirements or missing_manual_grid or preview_manual_path"
```

Expected: failures because artifacts, analysis fields, preflight check, and
side-effect-free manual preview are missing.

- [ ] **Step 3: Write grid artifacts and manifest metadata**

Add to `ARTIFACT_SPECS`:

```python
("four_grid_prompt", "09_four_grid_prompt.json", "json"),
("four_grid_image", "10_four_grid_image", "media"),
("comfyui_upload", "11_comfyui_upload.json", "json"),
```

In `write_run_artifacts`, when `run.grid_image_asset` exists:

```python
_write_json(
    artifact_dir / "09_four_grid_prompt.json",
    {"prompt": run.grid_image_prompt},
)
source = Path(run.grid_image_asset.local_path)
target = artifact_dir / f"10_four_grid_image{source.suffix.lower()}"
if source.resolve() != target.resolve():
    shutil.copyfile(source, target)
run.grid_image_asset.local_path = str(target)
_write_json(
    artifact_dir / "11_comfyui_upload.json",
    {
        "status": run.grid_image_asset.upload_status,
        "comfyui_filename": run.grid_image_asset.comfyui_filename,
        "error": run.grid_image_asset.upload_error,
        "replacements": run.grid_image_replacements,
    },
)
```

Expose `grid_image_asset`, `grid_image_checkpoint`, and
`grid_image_replacements` in manifest and run artifact index.

- [ ] **Step 4: Extend analysis and preview requests**

Add to `analyze_workflow_config` LiteGraph response:

```python
"grid_asset_required": points.grid_image_node_id is not None,
"grid_shape": {
    "columns": points.grid_columns,
    "rows": points.grid_rows,
},
```

Include all new injection-point fields.

Add optional `grid_image_asset: GridImageAsset | None = None` to
`ComfyUIPreviewRequest` and pass it through the API route.

For `preview_storyboard_submission`, when the workflow requires a grid and no
asset was supplied:

```python
preview_prompt = compile_four_grid_prompt(
    storyboard,
    max_chars=config.grid_image.prompt_max_chars,
)
if config.grid_image.effective_mode() == "manual_override":
    validated = validate_grid_image(
        config.grid_image.manual_image_path or "",
        min_dimension=config.grid_image.min_dimension,
        max_bytes=config.grid_image.max_bytes,
    )
    preview_filename = deterministic_comfyui_filename(
        run_id,
        validated.sha256,
        validated.mime_type,
    )
    image_resolution = "exact_manual_asset"
else:
    preview_filename = "pending_generation"
    image_resolution = "pending_generation"
```

Pass this preview-only filename into workflow planning with an
`allow_unuploaded_grid_image=True` flag. Add `"resolution": image_resolution`
to the `grid_image` replacement. `submit_storyboard` must keep
`allow_unuploaded_grid_image=False` and require an accepted asset.

Preview never calls the provider, upload endpoint, or `/prompt`.

- [ ] **Step 5: Add grid preflight validation**

Add imports to `config_validation.py`:

```python
import os
from pathlib import Path

from .grid_image import validate_grid_image
```

Add `_validate_grid_image_config(request)` to the run checks:

```python
def _validate_grid_image_config(request: RunRequest) -> dict[str, Any]:
    config = request.comfyui
    if not config or not config.enabled:
        return _check("grid_image", "skipped", "ComfyUI is disabled.")
    image = config.grid_image
    if image.effective_mode() == "manual_override":
        path = Path(image.manual_image_path or "")
        if not path.is_file():
            return _check("grid_image", "failed", f"Manual grid image not found: {path}")
        try:
            validated = validate_grid_image(
                path,
                min_dimension=image.min_dimension,
                max_bytes=image.max_bytes,
            )
        except ValueError as exc:
            return _check("grid_image", "failed", str(exc))
        return _check(
            "grid_image",
            "passed",
            "Manual grid image is valid.",
            {"path": str(path), "sha256": validated.sha256},
        )
    if not image.api_key and not os.environ.get(image.api_key_env):
        return _check(
            "grid_image",
            "failed",
            f"Missing environment variable for image API key: {image.api_key_env}",
        )
    return _check(
        "grid_image",
        "passed",
        "Automatic grid image provider is configured.",
        {"provider": image.provider, "model": image.model},
    )
```

- [ ] **Step 6: Verify GREEN**

Run:

```powershell
python -m pytest relief_story_agent/tests/test_artifacts.py relief_story_agent/tests/test_comfyui_mapping.py relief_story_agent/tests/test_config_validation.py -q -k "grid_image_artifacts or grid_requirements or missing_manual_grid or preview_manual_path"
```

Expected: selected tests pass.

### Task 8: Wire Independent Concurrency Limits Through the Server

**Files:**
- Modify: `relief_story_agent/server.py`
- Modify: `relief_story_agent/scheduler.py`
- Extend: `relief_story_agent/tests/test_scheduler.py`
- Extend: `relief_story_agent/tests/test_persistent_store.py`

- [ ] **Step 1: Write failing limit tests**

Add a blocking image provider and test:

```python
from PIL import Image, ImageDraw

from relief_story_agent.resource_limits import ExecutionResourceLimits
from relief_story_agent.tests.fixtures.ltx23_workflow_factory import (
    build_sanitized_ltx23_workflow,
)


def _grid_bytes(tmp_path):
    path = tmp_path / "scheduler_grid.png"
    image = Image.new("RGB", (1024, 1024), "white")
    draw = ImageDraw.Draw(image)
    for index, color in enumerate(["red", "green", "blue", "yellow"]):
        left = (index % 2) * 512
        top = (index // 2) * 512
        image.paste(color, (left, top, left + 512, top + 512))
        draw.line((left + 20, top + 20, left + 492, top + 492), fill="black", width=8)
    image.save(path)
    return path.read_bytes()


def _automatic_grid_request(tmp_path, index):
    workflow_path = tmp_path / "scheduler_ltx23.json"
    workflow_path.write_text(
        json.dumps(build_sanitized_ltx23_workflow(), ensure_ascii=False),
        encoding="utf-8",
    )
    return RunRequest(
        idea=f"automatic grid {index}",
        approval_mode="auto",
        output_root=str(tmp_path / "runs"),
        comfyui=ComfyUIRunConfig(
            enabled=True,
            workflow_api_path=str(workflow_path),
        ),
    )


class BlockingGridProvider:
    def __init__(self, image_bytes):
        self.image_bytes = image_bytes
        self.release = threading.Event()
        self.started = threading.Event()
        self.lock = threading.Lock()
        self.active = 0
        self.max_active = 0

    def generate(self, *, prompt, config):
        from relief_story_agent.grid_image import GeneratedImage
        with self.lock:
            self.active += 1
            self.max_active = max(self.max_active, self.active)
            self.started.set()
        try:
            assert self.release.wait(timeout=5)
            return GeneratedImage(
                content=self.image_bytes,
                mime_type="image/png",
                provider="fake",
                model=config.model,
            )
        finally:
            with self.lock:
                self.active -= 1


def test_image_generation_concurrency_is_independent_from_worker_count(
    tmp_path,
    monkeypatch,
):
    provider = BlockingGridProvider(_grid_bytes(tmp_path))
    monkeypatch.setattr(
        "relief_story_agent.orchestrator.upload_grid_image",
        lambda *args, **kwargs: "scheduler_grid.png",
    )
    monkeypatch.setattr(
        "relief_story_agent.orchestrator.submit_storyboard",
        lambda *args, **kwargs: [],
    )
    limits = ExecutionResourceLimits(
        image_generation_concurrency=1,
        comfyui_submission_concurrency=1,
    )
    orchestrator = StoryRunOrchestrator(
        provider=FakeModelProvider.minimal_success(),
        store=InMemoryRunStore(),
        grid_image_provider=provider,
        resource_limits=limits,
    )
    scheduler = PersistentRunScheduler(orchestrator, max_workers=3)

    runs = [
        scheduler.create_run(_automatic_grid_request(tmp_path, index))
        for index in range(3)
    ]
    assert provider.started.wait(timeout=2)
    time.sleep(0.05)
    assert provider.max_active == 1
    provider.release.set()
    assert scheduler.wait_for_idle(timeout=5)
    scheduler.shutdown()
```

Add a server health test:

```python
def test_server_health_reports_resource_limits(tmp_path):
    app = build_app(
        state_dir=str(tmp_path / "state"),
        provider=FakeModelProvider.minimal_success(),
        image_generation_concurrency=2,
        comfyui_submission_concurrency=1,
    )

    with TestClient(app) as client:
        body = client.get("/api/health").json()

    assert body["resources"] == {
        "image_generation_concurrency": 2,
        "comfyui_submission_concurrency": 1,
    }
```

- [ ] **Step 2: Verify RED**

Run:

```powershell
python -m pytest relief_story_agent/tests/test_scheduler.py relief_story_agent/tests/test_persistent_store.py -q -k "image_generation_concurrency or resource_limits"
```

Expected: failures because server options and health metadata are missing.

- [ ] **Step 3: Wire configuration**

Extend `build_app`:

```python
def build_app(
    state_dir: str | None = None,
    provider: OpenAICompatibleProvider | None = None,
    model_config_path: str | None = None,
    max_workers: int = 2,
    lease_seconds: float = 300.0,
    recovery_poll_seconds: float = 5.0,
    image_generation_concurrency: int = 2,
    comfyui_submission_concurrency: int = 1,
):
    store = JsonFileRunStore(state_dir) if state_dir else InMemoryRunStore()
    registry = (
        ModelConfigRegistry.from_file(model_config_path)
        if model_config_path
        else ModelConfigRegistry()
    )
    limits = ExecutionResourceLimits(
        image_generation_concurrency=image_generation_concurrency,
        comfyui_submission_concurrency=comfyui_submission_concurrency,
    )
    orchestrator = StoryRunOrchestrator(
        provider=provider or OpenAICompatibleProvider(),
        store=store,
        model_registry=registry,
        grid_image_provider=OpenAICompatibleGridImageProvider(),
        resource_limits=limits,
    )
    scheduler = PersistentRunScheduler(
        orchestrator,
        max_workers=max_workers,
        lease_seconds=lease_seconds,
        recovery_poll_seconds=recovery_poll_seconds,
    )
    return create_app(orchestrator, scheduler=scheduler)
```

Add CLI flags:

```python
parser.add_argument("--image-generation-concurrency", default=2, type=int)
parser.add_argument("--comfyui-submission-concurrency", default=1, type=int)
```

Pass both parsed values into `build_app` inside `uvicorn.run`.

`ExecutionResourceLimits.status()` was defined in Task 6. Include its result
under `/api/health`:

```python
"resources": orchestrator.resource_limits.status(),
```

- [ ] **Step 4: Verify GREEN**

Run:

```powershell
python -m pytest relief_story_agent/tests/test_scheduler.py relief_story_agent/tests/test_persistent_store.py -q -k "image_generation_concurrency or resource_limits"
```

Expected: selected tests pass.

### Task 9: Full Restart-Safe Integration and Documentation

**Files:**
- Modify: `relief_story_agent/README.md`
- Modify: `relief_story_agent/examples/batch_request.example.json`
- Extend: `relief_story_agent/tests/test_orchestrator.py`
- Extend: `relief_story_agent/tests/test_persistent_store.py`
- Extend: `relief_story_agent/tests/test_comfyui_idempotency.py`

- [ ] **Step 1: Write failing end-to-end restart tests**

Add these imports to the touched test files as needed:

```python
import copy
import json
from pathlib import Path

from PIL import Image, ImageDraw

from relief_story_agent.comfyui import preview_storyboard_submission, submit_storyboard
from relief_story_agent.grid_image import acquire_generated_grid_image, validate_grid_image
from relief_story_agent.models import ComfyUIRunConfig, GridImageAsset, GridImageConfig
```

Add tests proving:

```python
def test_persistent_restart_reuses_generated_asset_after_comfyui_failure(tmp_path, monkeypatch):
    state_dir = tmp_path / "state"
    output_root = tmp_path / "runs"
    provider = FakeGeneratedGridProvider(_grid_png_bytes(tmp_path))
    first = StoryRunOrchestrator(
        provider=FakeModelProvider.minimal_success(),
        store=JsonFileRunStore(state_dir),
        grid_image_provider=provider,
    )
    run = first.prepare_run(_grid_request(tmp_path, output_root=output_root))
    monkeypatch.setattr(
        "relief_story_agent.orchestrator.upload_grid_image",
        lambda *args, **kwargs: "persisted.png",
    )
    monkeypatch.setattr(
        "relief_story_agent.orchestrator.submit_storyboard",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("comfy failed")),
    )

    first.execute_scheduled(run.run_id)
    failed = JsonFileRunStore(state_dir).get(run.run_id)
    assert failed.failed_stage == "comfyui"
    assert failed.grid_image_asset.comfyui_filename == "persisted.png"
    assert provider.calls == 1

    restarted = StoryRunOrchestrator(
        provider=FakeModelProvider.minimal_success(),
        store=JsonFileRunStore(state_dir),
        grid_image_provider=provider,
    )
    monkeypatch.setattr(
        "relief_story_agent.orchestrator.submit_storyboard",
        lambda *args, **kwargs: [],
    )
    restarted.queue_retry(run.run_id, RunRetryRequest(from_stage="comfyui"))
    completed = restarted.execute_scheduled(run.run_id)

    assert completed.status == "completed"
    assert provider.calls == 1
    assert completed.grid_image_asset.comfyui_filename == "persisted.png"
```

Add the following tests to `test_orchestrator.py`:

```python
class ProviderMustNotRun:
    def generate(self, *, prompt, config):
        raise AssertionError("manual override must not call the image provider")


def test_manual_override_never_calls_image_provider(tmp_path, monkeypatch):
    image_path = tmp_path / "manual.png"
    image_path.write_bytes(_grid_png_bytes(tmp_path))
    request = _grid_request(tmp_path)
    request.comfyui.grid_image = GridImageConfig(
        mode="manual_override",
        manual_image_path=str(image_path),
    )
    monkeypatch.setattr(
        "relief_story_agent.orchestrator.upload_grid_image",
        lambda *args, **kwargs: "manual.png",
    )
    monkeypatch.setattr(
        "relief_story_agent.orchestrator.submit_storyboard",
        lambda *args, **kwargs: [],
    )
    orchestrator = StoryRunOrchestrator(
        provider=FakeModelProvider.minimal_success(),
        store=InMemoryRunStore(),
        grid_image_provider=ProviderMustNotRun(),
    )

    run = orchestrator.create_run(request)

    assert run.status == "completed"
    assert run.grid_image_asset.source == "manual"


def test_accepted_upload_receipt_skips_upload_endpoint(tmp_path, monkeypatch):
    provider = FakeGeneratedGridProvider(_grid_png_bytes(tmp_path))
    orchestrator, run = _prepare_grid_run(tmp_path, provider)
    artifact_dir = Path(run.request.output_root) / run.run_id
    asset = acquire_generated_grid_image(
        provider,
        artifact_dir=artifact_dir,
        prompt="persisted prompt",
        config=run.request.comfyui.grid_image,
    )
    asset.comfyui_filename = "accepted.png"
    asset.upload_status = "accepted"
    run.grid_image_prompt = "persisted prompt"
    run.grid_image_asset = asset
    run.grid_image_checkpoint = "image_uploaded"
    orchestrator.store.save(run)
    monkeypatch.setattr(
        "relief_story_agent.orchestrator.upload_grid_image",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("accepted upload must not be repeated")
        ),
    )

    orchestrator._run_four_grid_asset(run)

    assert run.grid_image_asset.comfyui_filename == "accepted.png"


def test_invalid_manual_image_prevents_comfyui_submission(tmp_path, monkeypatch):
    invalid = tmp_path / "invalid.png"
    Image.new("RGB", (1024, 1024), "white").save(invalid)
    request = _grid_request(tmp_path)
    request.comfyui.grid_image = GridImageConfig(
        mode="manual_override",
        manual_image_path=str(invalid),
    )
    monkeypatch.setattr(
        "relief_story_agent.orchestrator.submit_storyboard",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("invalid image must stop before /prompt")
        ),
    )
    orchestrator = StoryRunOrchestrator(
        provider=FakeModelProvider.minimal_success(),
        store=InMemoryRunStore(),
        grid_image_provider=ProviderMustNotRun(),
    )

    run = orchestrator.create_run(request)

    assert run.status == "failed"
    assert run.failed_stage == "four_grid_asset"
```

Add to `test_comfyui_mapping.py`:

```python
def test_preview_and_submission_do_not_mutate_60_node_fixture(tmp_path, monkeypatch):
    workflow = build_sanitized_ltx23_workflow()
    original = copy.deepcopy(workflow)
    workflow_path = tmp_path / "immutable_workflow.json"
    workflow_path.write_text(json.dumps(workflow), encoding="utf-8")
    image_path = tmp_path / "manual.png"
    image = Image.new("RGB", (1024, 1024), "white")
    draw = ImageDraw.Draw(image)
    for index, color in enumerate(["red", "green", "blue", "yellow"]):
        left = (index % 2) * 512
        top = (index // 2) * 512
        image.paste(color, (left, top, left + 512, top + 512))
        draw.line((left + 20, top + 20, left + 492, top + 492), fill="black", width=8)
    image.save(image_path)
    validated = validate_grid_image(
        image_path,
        min_dimension=512,
        max_bytes=10_000_000,
    )
    asset = GridImageAsset(
        source="manual",
        local_path=str(image_path),
        sha256=validated.sha256,
        mime_type=validated.mime_type,
        width=validated.width,
        height=validated.height,
        byte_size=validated.byte_size,
        comfyui_filename="immutable.png",
        upload_status="accepted",
    )
    config = ComfyUIRunConfig(enabled=True, workflow_api_path=str(workflow_path))
    storyboard = [{"shot_id": 1, "time_range": "0-4s", "image_prompt": "frame"}]
    preview_storyboard_submission(
        config,
        storyboard,
        "immutable",
        duration_seconds=4,
        grid_image_asset=asset,
    )
    monkeypatch.setattr(
        "relief_story_agent.comfyui.enqueue_workflow",
        lambda *args, **kwargs: kwargs["prompt_id"],
    )
    submit_storyboard(
        config,
        storyboard,
        "immutable",
        duration_seconds=4,
        grid_image_asset=asset,
    )

    persisted = json.loads(workflow_path.read_text(encoding="utf-8"))
    assert persisted == original
    assert len(persisted["nodes"]) == 60
```

The unknown-upload deterministic-name behavior is already exercised by
`test_retry_after_upload_failure_reuses_acquired_image` from Task 6; retain that
test in the focused suite.

- [ ] **Step 2: Verify RED**

Run:

```powershell
python -m pytest relief_story_agent/tests/test_orchestrator.py relief_story_agent/tests/test_persistent_store.py relief_story_agent/tests/test_comfyui_idempotency.py -q -k "generated_asset or manual_override or accepted_upload or unknown_upload or invalid_image or 60_node"
```

Expected: at least one restart/idempotency assertion fails until all persisted state paths are wired.

- [ ] **Step 3: Complete persistence and idempotency behavior**

Implement `_run_four_grid_asset` idempotency with this shape:

```python
asset = run.grid_image_asset
if asset is None:
    # Only this branch may call the manual copier or image provider.
    if image_config.effective_mode() == "manual_override":
        asset = acquire_manual_grid_image(
            image_config.manual_image_path or "",
            artifact_dir=artifact_dir,
            prompt=run.grid_image_prompt,
            config=image_config,
        )
    else:
        asset = self._acquire_generated_grid_asset(
            run,
            artifact_dir=artifact_dir,
            image_config=image_config,
        )
    run.grid_image_asset = asset
    run.grid_image_checkpoint = "image_acquired"
    self.store.save(run)

if asset.upload_status == "accepted" and asset.comfyui_filename:
    run.grid_image_checkpoint = "image_uploaded"
else:
    destination = deterministic_comfyui_filename(
        run.run_id,
        asset.sha256,
        asset.mime_type,
    )
    try:
        asset.comfyui_filename = upload_grid_image(
            config.endpoint,
            asset.local_path,
            destination_name=destination,
        )
        asset.upload_status = "accepted"
        asset.upload_error = ""
    except httpx.TransportError as exc:
        asset.comfyui_filename = destination
        asset.upload_status = "unknown"
        asset.upload_error = str(exc)
        self.store.save(run)
        raise
    run.grid_image_checkpoint = "image_uploaded"
    self.store.save(run)
```

`queue_retry(from_stage="comfyui")` must preserve every grid-image field.
`queue_retry(from_stage="four_grid_asset")` must preserve the acquired asset and
only resume from its checkpoint.

- [ ] **Step 4: Document user configuration**

In `README.md`, add:

```json
{
  "comfyui": {
    "enabled": true,
    "endpoint": "http://127.0.0.1:8188",
    "workflow_api_path": "C:/path/to/LTX-2.3-four-grid.json",
    "grid_image": {
      "mode": "auto",
      "provider": "openai_compatible",
      "base_url": "https://api.openai.com/v1",
      "api_key_env": "OPENAI_API_KEY",
      "model": "gpt-image-2",
      "size": "1024x1024",
      "quality": "medium",
      "output_format": "png"
    }
  }
}
```

Document manual override:

```json
{
  "grid_image": {
    "mode": "manual_override",
    "manual_image_path": "D:/images/my-four-grid.png"
  }
}
```

Document artifacts `09_four_grid_prompt.json`,
`10_four_grid_image.<ext>`, and `11_comfyui_upload.json`, plus retry behavior.

Update `examples/batch_request.example.json` with an automatic grid-image
configuration that uses `api_key_env`, never a literal secret.

- [ ] **Step 5: Run focused feature tests**

Run:

```powershell
python -m pytest relief_story_agent/tests/test_grid_image.py relief_story_agent/tests/test_image_provider.py relief_story_agent/tests/test_comfyui_mapping.py relief_story_agent/tests/test_orchestrator.py relief_story_agent/tests/test_config_validation.py relief_story_agent/tests/test_scheduler.py relief_story_agent/tests/test_persistent_store.py relief_story_agent/tests/test_comfyui_idempotency.py relief_story_agent/tests/test_artifacts.py relief_story_agent/tests/test_failure_policy.py -q
```

Expected: all selected tests pass.

- [ ] **Step 6: Run the full project suite**

Run:

```powershell
python -m pytest relief_story_agent/tests -q
```

Expected: zero failures.

- [ ] **Step 7: Run compile and package checks**

Run:

```powershell
python -m compileall -q relief_story_agent
python -m pip install -e . --no-deps
python -c "from relief_story_agent.server import build_app; print(build_app)"
```

Expected: all commands exit with code 0 and the import prints the `build_app`
function.

- [ ] **Step 8: Run a no-side-effect real-workflow analysis**

Run:

```powershell
$workflow = Get-ChildItem 'C:\Users\dcf\Downloads' -Filter '*LTX-2.3*4宫格V3.0*.json' | Select-Object -First 1
$env:LTX_WORKFLOW_PATH = $workflow.FullName
@'
import json
import os
from relief_story_agent.comfyui import analyze_workflow_config
from relief_story_agent.models import ComfyUIRunConfig

result = analyze_workflow_config(
    ComfyUIRunConfig(
        enabled=True,
        workflow_api_path=os.environ["LTX_WORKFLOW_PATH"],
    )
)
assert result["ltx_injection_points"]["grid_image_node_id"] == "196"
assert result["ltx_injection_points"]["json_node_id"] == "202"
assert result["ltx_injection_points"]["seed_node_id"] == "37"
assert result["ltx_injection_points"]["filename_prefix_node_id"] == "79"
assert result["grid_shape"] == {"columns": 2, "rows": 2}
print(json.dumps(result, ensure_ascii=False, indent=2))
'@ | python -
```

Expected: exits with code 0 and reports the four exact injection nodes and
`2x2` grid shape without contacting GPT Image or ComfyUI.

## Completion Audit

Before declaring this plan complete, verify each requirement against current
evidence:

1. `RunState` contains persisted prompt, asset, attempt, checkpoint, upload, and
   replacement metadata.
2. Manual and generated paths converge on `GridImageAsset`.
3. The real workflow resolves `196`, `202`, `37`, and `79`.
4. Preview returns four replacements and performs no network side effects.
5. Failed validation cannot reach `/prompt`.
6. Retrying `four_grid_asset` does not regenerate an acquired asset.
7. Retrying `comfyui` does not regenerate or re-upload an accepted asset.
8. Independent concurrency defaults are image `2` and ComfyUI submission `1`.
9. Artifacts `09`, `10`, and `11` exist without overwriting timeline artifact
   `08`.
10. Focused tests, full tests, compile check, editable install, and real-workflow
    analysis all pass with fresh command output.
