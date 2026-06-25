from __future__ import annotations

from urllib.parse import urlsplit, urlunsplit


def normalize_comfyui_endpoint(value: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        raise ValueError("ComfyUI endpoint is required")
    if "://" not in raw:
        raw = f"http://{raw}"
    parsed = urlsplit(raw)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("ComfyUI endpoint must use http or https")
    if not parsed.netloc:
        raise ValueError("ComfyUI endpoint must include a host")
    return urlunsplit((parsed.scheme.lower(), parsed.netloc, "", "", ""))
