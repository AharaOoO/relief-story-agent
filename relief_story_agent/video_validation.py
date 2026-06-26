from __future__ import annotations

from pathlib import Path
from typing import Any


def check_local_video_file(path_value: str) -> dict[str, Any]:
    path = Path(path_value)
    exists = path.exists() and path.is_file()
    size_bytes = path.stat().st_size if exists else 0
    openable = exists and size_bytes > 0 and has_recognized_video_container(path)
    return {
        "path": path_value,
        "exists": exists,
        "size_bytes": size_bytes,
        "openable": openable,
        "valid": exists and size_bytes > 0 and openable,
    }


def has_recognized_video_container(path: Path) -> bool:
    suffix = path.suffix.lower()
    if suffix in {".mp4", ".m4v", ".mov"}:
        try:
            data = path.read_bytes()
        except OSError:
            return False
        return _has_mp4_required_boxes(data)
    return suffix in {".webm", ".mkv", ".avi"}


def _has_mp4_required_boxes(data: bytes) -> bool:
    boxes = set()
    offset = 0
    while offset + 8 <= len(data):
        size = int.from_bytes(data[offset : offset + 4], "big")
        kind = data[offset + 4 : offset + 8]
        if size == 1 or size < 8:
            break
        boxes.add(kind)
        offset += size
    return b"ftyp" in boxes and b"moov" in boxes
