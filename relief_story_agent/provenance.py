from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .models import RunRequest


def build_run_configuration_provenance(request: RunRequest) -> dict[str, Any]:
    files = {
        "prompt_writer_template": build_file_provenance(
            request.template_paths.prompt_writer_template_path
        ),
        "prompt_audit_template": build_file_provenance(
            request.template_paths.prompt_audit_template_path
        ),
        "comfyui_workflow": build_file_provenance(
            request.comfyui.workflow_api_path if request.comfyui else None
        ),
        "placeholder_map": build_file_provenance(
            request.comfyui.placeholder_map_path if request.comfyui else None
        ),
    }
    return {
        "files": files,
        "fingerprint": _fingerprint_files(files),
    }


def build_file_provenance(path: str | None) -> dict[str, Any]:
    if not path:
        return {
            "path": "",
            "configured": False,
            "exists": False,
            "kind": "not_configured",
            "size_bytes": 0,
            "sha256": "",
            "modified_at": "",
            "error": "",
        }

    file_path = Path(path)
    if not file_path.exists():
        return {
            "path": path,
            "configured": True,
            "exists": False,
            "kind": "missing",
            "size_bytes": 0,
            "sha256": "",
            "modified_at": "",
            "error": "",
        }
    if not file_path.is_file():
        return {
            "path": path,
            "configured": True,
            "exists": False,
            "kind": "directory",
            "size_bytes": 0,
            "sha256": "",
            "modified_at": _modified_at(file_path),
            "error": "Path is not a file.",
        }

    try:
        data = file_path.read_bytes()
    except OSError as exc:
        return {
            "path": path,
            "configured": True,
            "exists": False,
            "kind": "unreadable",
            "size_bytes": 0,
            "sha256": "",
            "modified_at": _modified_at(file_path),
            "error": str(exc),
        }
    return {
        "path": path,
        "configured": True,
        "exists": True,
        "kind": "file",
        "size_bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        "modified_at": _modified_at(file_path),
        "error": "",
    }


def _fingerprint_files(files: dict[str, dict[str, Any]]) -> str:
    stable = {
        name: {
            "path": item.get("path", ""),
            "configured": bool(item.get("configured")),
            "exists": bool(item.get("exists")),
            "size_bytes": int(item.get("size_bytes") or 0),
            "sha256": str(item.get("sha256") or ""),
        }
        for name, item in sorted(files.items())
    }
    payload = json.dumps(stable, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _modified_at(path: Path) -> str:
    try:
        return datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat()
    except OSError:
        return ""
