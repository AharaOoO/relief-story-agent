from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path
from typing import Callable, Sequence

from .models import VideoAssemblyState


def assemble_segment_videos(
    clip_paths: Sequence[str | Path],
    output_path: str | Path,
    *,
    ffmpeg_executable: str | None = None,
    runner: Callable[..., object] = subprocess.run,
) -> VideoAssemblyState:
    clips = [Path(path).resolve() for path in clip_paths]
    output = Path(output_path).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    manifest_path = output.with_name(f"{output.stem}_concat.txt")
    state = VideoAssemblyState(
        status="running",
        clip_paths=[str(path) for path in clips],
        concat_manifest_path=str(manifest_path),
        output_path=str(output),
    )
    missing = [str(path) for path in clips if not path.is_file()]
    if not clips or missing:
        state.status = "failed"
        state.error = (
            "No segment clips were supplied"
            if not clips
            else f"Segment clip not found: {', '.join(missing)}"
        )
        return state

    manifest_path.write_text(
        "".join(f"file '{_concat_path(path)}'\n" for path in clips),
        encoding="utf-8",
    )
    ffmpeg = ffmpeg_executable or _resolve_ffmpeg_executable()
    temporary = output.with_name(f"{output.stem}.assembling{output.suffix}")
    temporary.unlink(missing_ok=True)
    copy_command = [
        ffmpeg,
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(manifest_path),
        "-c",
        "copy",
        str(temporary),
    ]
    result = _run(runner, copy_command)
    if result.returncode != 0 or not temporary.is_file():
        temporary.unlink(missing_ok=True)
        normalize_command = [
            ffmpeg,
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(manifest_path),
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-movflags",
            "+faststart",
            str(temporary),
        ]
        result = _run(runner, normalize_command)
        state.command = normalize_command
    else:
        state.command = copy_command

    state.return_code = int(result.returncode)
    state.stderr_tail = str(getattr(result, "stderr", "") or "")[-4000:]
    if result.returncode != 0 or not temporary.is_file():
        temporary.unlink(missing_ok=True)
        state.status = "failed"
        state.error = state.stderr_tail or "FFmpeg did not create an output file"
        return state

    temporary.replace(output)
    state.status = "completed"
    state.output_sha256 = _sha256_file(output)
    state.error = ""
    return state


def _run(runner: Callable[..., object], command: list[str]):
    return runner(
        command,
        capture_output=True,
        text=True,
        check=False,
    )


def _resolve_ffmpeg_executable() -> str:
    import imageio_ffmpeg

    return imageio_ffmpeg.get_ffmpeg_exe()


def _concat_path(path: Path) -> str:
    return str(path).replace("\\", "/").replace("'", "'\\''")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
