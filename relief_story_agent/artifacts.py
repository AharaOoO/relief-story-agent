from __future__ import annotations

import csv
import hashlib
import json
import shutil
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any

from .comfyui import preview_storyboard_submission
from .ltx_workflow import build_ltx_payload_from_storyboard
from .models import BatchRunState, RunState
from .pipeline import RECOVERABLE_STAGE_ORDER
from .provenance import build_run_configuration_provenance
from .video_validation import check_local_video_file


ARTIFACT_SPECS = [
    ("script", "01_script.json", "json"),
    ("storyboard", "02_storyboard.json", "json"),
    ("ltx_payload", "03_ltx_payload.json", "json"),
    ("prompt_audit", "04_prompt_audit.json", "json"),
    ("final_prompts", "05_final_prompts.json", "json"),
    ("model_execution", "06_model_execution.json", "json"),
    ("comfyui_preview", "07_comfyui_preview.json", "json"),
    ("timeline", "08_timeline.json", "json"),
]

RELEASE_NOTES_FILENAME = "README_RELEASE.md"

PUBLISH_INDEX_COLUMNS = [
    "index",
    "run_id",
    "idea",
    "title",
    "core_sentence",
    "publish_ready",
    "status",
    "primary_video_path",
    "exported_video_path",
    "publish_video_path",
    "publish_video_size_bytes",
    "publish_video_sha256",
    "artifact_dir",
    "export_dir",
    "scores_json",
    "recommended_action_code",
]


def write_run_artifacts(run: RunState) -> Path:
    artifact_dir = _artifact_dir_for_run(run)
    artifact_dir.mkdir(parents=True, exist_ok=True)

    final_storyboard = run.final_storyboard or run.storyboard
    _write_json(artifact_dir / "01_script.json", run.script)
    _write_json(artifact_dir / "02_storyboard.json", run.storyboard)
    _write_json(
        artifact_dir / "03_ltx_payload.json",
        build_ltx_payload_from_storyboard(
            final_storyboard,
            duration_seconds=int(run.script.get("duration_seconds") or run.request.duration_seconds),
        ),
    )
    _write_json(artifact_dir / "04_prompt_audit.json", run.prompt_audit)
    _write_json(artifact_dir / "05_final_prompts.json", final_storyboard)
    _write_json(
        artifact_dir / "06_model_execution.json",
        {
            "summary": run.model_usage_summary.model_dump(),
            "attempts": [attempt.model_dump() for attempt in run.model_attempts],
        },
    )
    _write_json(
        artifact_dir / "07_comfyui_preview.json",
        _build_comfyui_preview(run, final_storyboard),
    )
    write_run_timeline_artifact(run, artifact_dir=artifact_dir)
    write_execution_manifest(run, artifact_dir=artifact_dir)
    if run.grid_image_asset:
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

    run.artifact_dir = str(artifact_dir)
    write_artifact_manifest(run)
    return artifact_dir


def write_run_checkpoint_artifacts(run: RunState) -> Path:
    """Persist every valid result available so far without inventing future outputs."""
    artifact_dir = _artifact_dir_for_run(run)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    final_storyboard = run.final_storyboard or run.storyboard

    if run.script:
        _write_json(artifact_dir / "01_script.json", run.script)
    if run.storyboard:
        _write_json(artifact_dir / "02_storyboard.json", run.storyboard)
        _write_json(
            artifact_dir / "03_ltx_payload.json",
            build_ltx_payload_from_storyboard(
                final_storyboard,
                duration_seconds=int(
                    run.script.get("duration_seconds") or run.request.duration_seconds
                ),
            ),
        )
        _write_json(
            artifact_dir / "07_comfyui_preview.json",
            _build_comfyui_preview(run, final_storyboard),
        )
    if run.prompt_audit:
        _write_json(artifact_dir / "04_prompt_audit.json", run.prompt_audit)
    if run.final_storyboard:
        _write_json(artifact_dir / "05_final_prompts.json", final_storyboard)
    if run.model_attempts:
        _write_json(
            artifact_dir / "06_model_execution.json",
            {
                "summary": run.model_usage_summary.model_dump(),
                "attempts": [attempt.model_dump() for attempt in run.model_attempts],
            },
        )

    run.artifact_dir = str(artifact_dir)
    write_run_timeline_artifact(run, artifact_dir=artifact_dir)
    write_execution_manifest(run, artifact_dir=artifact_dir)
    write_artifact_manifest(run)
    return artifact_dir


def write_run_timeline_artifact(run: RunState, *, artifact_dir: Path | None = None) -> Path:
    if artifact_dir is not None:
        target_dir = artifact_dir
    elif run.artifact_dir:
        target_dir = _absolute_path(Path(run.artifact_dir))
    else:
        target_dir = _artifact_dir_for_run(run)
    target_dir.mkdir(parents=True, exist_ok=True)
    run.artifact_dir = str(target_dir)
    path = target_dir / "08_timeline.json"
    _write_json(path, _build_timeline(run))
    return path


def write_execution_manifest(
    run: RunState,
    *,
    artifact_dir: Path | None = None,
) -> Path:
    target_dir = artifact_dir or (
        _absolute_path(Path(run.artifact_dir))
        if run.artifact_dir
        else _artifact_dir_for_run(run)
    )
    target_dir.mkdir(parents=True, exist_ok=True)
    run.artifact_dir = str(target_dir)
    segments = sorted(run.segment_renders, key=lambda item: item.order)
    first = segments[0] if segments else None
    model_bindings = []
    seen_bindings: set[tuple[str, str, str, str]] = set()
    for segment in segments:
        for binding in segment.workflow_models:
            key = (
                binding.node_id,
                binding.class_type,
                binding.input_name,
                binding.selected,
            )
            if key in seen_bindings:
                continue
            seen_bindings.add(key)
            model_bindings.append(binding.model_dump())
    payload = {
        "run_id": run.run_id,
        "duration_mode": (
            "auto" if run.request.creation_spec.duration_seconds == 0 else "explicit"
        ),
        "target_duration_seconds": run.request.creation_spec.duration_seconds,
        "planned_duration_seconds": sum(
            segment.duration_seconds for segment in segments
        ),
        "workflow": {
            "name": first.workflow_name if first else "",
            "path": first.workflow_path if first else "",
            "sha256": first.workflow_sha256 if first else "",
        },
        "workflow_models": model_bindings,
        "segments": [
            {
                "segment_id": segment.segment_id,
                "shot_id": segment.shot_id,
                "order": segment.order,
                "authored_time_range": segment.authored_time_range,
                "render_time_range": segment.render_time_range,
                "duration_seconds": segment.duration_seconds,
                "fps": segment.fps,
                "frame_count": segment.frame_count,
                "local_frame_indices": list(segment.local_frame_indices),
                "positive_prompt": segment.positive_prompt,
                "negative_prompt": segment.negative_prompt,
                "seed": segment.seed,
                "strength": segment.strength,
                "grid_panel_prompts": list(segment.grid_panel_prompts),
                "grid_image_prompt": segment.grid_image_prompt,
                "workflow_name": segment.workflow_name,
                "workflow_path": segment.workflow_path,
                "workflow_sha256": segment.workflow_sha256,
                "workflow_models": [
                    binding.model_dump() for binding in segment.workflow_models
                ],
                "status": segment.status,
            }
            for segment in segments
        ],
    }
    path = target_dir / "execution_manifest.json"
    _write_json(path, payload)
    return path


def write_artifact_manifest(run: RunState) -> Path:
    artifact_dir = (
        _absolute_path(Path(run.artifact_dir))
        if run.artifact_dir
        else _artifact_dir_for_run(run)
    )
    artifact_dir.mkdir(parents=True, exist_ok=True)
    run.artifact_dir = str(artifact_dir)
    _write_json(artifact_dir / "00_manifest.json", _build_manifest(run, artifact_dir))
    return artifact_dir


def read_run_artifact_index(run: RunState) -> dict[str, Any]:
    artifact_dir = (
        _absolute_path(Path(run.artifact_dir))
        if run.artifact_dir
        else _artifact_dir_for_run(run)
    )
    manifest_path = artifact_dir / "00_manifest.json"
    if not manifest_path.exists() and _has_checkpoint_data(run):
        artifact_dir = write_run_checkpoint_artifacts(run)
        manifest_path = artifact_dir / "00_manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    else:
        manifest = _build_manifest(run, artifact_dir)
    manifest["artifacts"] = [
        {
            **item,
            "path": str(_manifest_artifact_path(item, artifact_dir)),
            "exists": _manifest_artifact_path(item, artifact_dir).exists(),
        }
        for item in manifest.get("artifacts", [])
    ]
    manifest["comfyui_prompt_ids"] = list(run.comfyui_prompt_ids)
    manifest["actual_outputs"] = [output.model_dump() for output in run.comfyui_outputs]
    manifest["comfyui_cancellations"] = [
        item.model_dump() for item in run.comfyui_cancellations
    ]
    manifest["comfyui_diagnostics"] = dict(run.comfyui_diagnostics)
    manifest["last_failure"] = _failure_record_dump(run.last_failure)
    manifest["failure_records"] = [
        record.model_dump() for record in run.failure_records
    ]
    return manifest


def _absolute_path(path: Path) -> Path:
    return path.expanduser().resolve()


def _artifact_dir_for_run(run: RunState) -> Path:
    output_root = _absolute_path(Path(run.request.output_root or "runs"))
    return output_root / run.run_id


def _manifest_artifact_path(item: dict[str, Any], artifact_dir: Path) -> Path:
    path = Path(str(item.get("path") or ""))
    if path.is_absolute():
        return path
    filename = str(item.get("filename") or path.name)
    return artifact_dir / filename


def _has_checkpoint_data(run: RunState) -> bool:
    return bool(
        run.script
        or run.storyboard
        or run.final_storyboard
        or run.prompt_audit
        or run.model_attempts
    )


def read_batch_artifact_index(
    batch: BatchRunState,
    runs: list[RunState],
) -> dict[str, Any]:
    runs_by_id = {run.run_id: run for run in runs}
    items = []
    for batch_item in batch.items:
        run = runs_by_id.get(batch_item.run_id)
        if run is None:
            recommended_action = _recommended_action_for_missing_run(batch_item)
            items.append(
                {
                    "index": batch_item.index,
                    "run_id": batch_item.run_id,
                    "idea": batch_item.idea,
                    "status": batch_item.status,
                    "current_stage": batch_item.current_stage,
                    "error": batch_item.error or "run not found",
                    "publish_ready": False,
                    "failed_stage": "",
                    "retryable": False,
                    "retry_from_stage": "",
                    "recommended_action": recommended_action,
                    "model_usage_summary": _empty_usage_summary(),
                }
            )
            continue
        actual_outputs = [output.model_dump() for output in run.comfyui_outputs]
        primary_video_path = _primary_video_path(actual_outputs)
        timeline_diagnostics = _build_timeline_recovery_diagnostics(run)
        retry_from_stage = _retry_from_stage_for_run(run, timeline_diagnostics)
        retryable = _is_retryable_run(run, retry_from_stage=retry_from_stage)
        recommended_action = _recommended_action_for_run(
            run,
            primary_video_path=primary_video_path,
            retryable=retryable,
            retry_from_stage=retry_from_stage,
        )
        items.append(
            {
                "index": batch_item.index,
                "run_id": run.run_id,
                "idea": batch_item.idea,
                "status": run.status,
                "current_stage": run.current_stage,
                "failed_stage": run.failed_stage,
                "title": str(run.script.get("title") or ""),
                "core_sentence": str(run.script.get("core_sentence") or ""),
                "scores": dict((run.prompt_audit or {}).get("scores") or {}),
                "artifact_dir": run.artifact_dir,
                "actual_outputs": actual_outputs,
                "last_failure": _failure_record_dump(run.last_failure),
                "failure_records": [
                    record.model_dump() for record in run.failure_records
                ],
                "primary_video_path": primary_video_path,
                "publish_ready": run.status == "completed" and bool(primary_video_path),
                "retryable": retryable,
                "retry_from_stage": retry_from_stage if retryable else "",
                "timeline_diagnostics": timeline_diagnostics,
                "recommended_action": recommended_action,
                "model_usage_summary": run.model_usage_summary.model_dump(),
                "error": run.error or batch_item.error,
            }
        )
    audit_summary = _build_batch_audit_summary(items)
    return {
        "batch_id": batch.batch_id,
        "status": batch.status,
        "summary": dict(batch.summary),
        "items": items,
        "publish_ready_count": audit_summary["publish_ready_count"],
        "audit_summary": audit_summary,
    }


def export_batch_artifact_package(
    batch: BatchRunState,
    runs: list[RunState],
    *,
    export_root: str | Path | None = None,
    include_zip: bool = True,
) -> dict[str, Any]:
    runs_by_id = {run.run_id: run for run in runs}
    root = Path(export_root) if export_root else _default_batch_export_root(runs)
    export_dir = root / batch.batch_id
    export_dir.mkdir(parents=True, exist_ok=True)
    publish_videos_dir = export_dir / "publish_videos"
    publish_videos_dir.mkdir(parents=True, exist_ok=True)

    index = read_batch_artifact_index(batch, runs)
    exported_items = []
    for item in index["items"]:
        run = runs_by_id.get(item["run_id"])
        item_dir = export_dir / _export_item_dirname(item)
        item_dir.mkdir(parents=True, exist_ok=True)
        exported_item = dict(item)
        exported_item["export_dir"] = str(item_dir)
        exported_item["exported_files"] = {}
        if run is not None:
            _copy_run_artifacts(run, item_dir, exported_item)
            _copy_primary_video(item, item_dir, exported_item)
            _copy_publish_video(exported_item, publish_videos_dir)
        _write_json(item_dir / "item_manifest.json", exported_item)
        exported_items.append(exported_item)

    publish_index = _build_publish_index(batch.batch_id, export_dir, exported_items)
    publish_index_files = {
        "json": str(export_dir / "publish_index.json"),
        "csv": str(export_dir / "publish_index.csv"),
    }
    _write_json(export_dir / "publish_index.json", publish_index)
    _write_publish_index_csv(export_dir / "publish_index.csv", publish_index["items"])
    release_notes_path = _write_release_notes(export_dir, batch.batch_id, index, publish_index)

    manifest = {
        **index,
        "export_dir": str(export_dir),
        "items": exported_items,
        "publish_index": publish_index,
        "publish_index_files": publish_index_files,
        "release_notes_path": str(release_notes_path),
        "zip_path": "",
    }
    _write_json(export_dir / "batch_export_manifest.json", manifest)
    if include_zip:
        zip_path = export_dir.with_suffix(".zip")
        manifest["zip_path"] = str(zip_path)
        _write_json(export_dir / "batch_export_manifest.json", manifest)
        _zip_directory(export_dir, zip_path)
        manifest["zip_package"] = _build_zip_package_metadata(zip_path)
        _write_json(export_dir / "batch_export_manifest.json", manifest)
    return manifest


def validate_batch_export_zip(
    zip_path: str | Path,
    *,
    expected_sha256: str = "",
    expected_size_bytes: int = 0,
    save_report: bool = False,
) -> dict[str, Any]:
    path = Path(zip_path)
    checks = [_file_check("zip_file", path)]
    actual_sha256 = ""
    actual_size = 0
    if path.exists() and path.is_file():
        actual_size = path.stat().st_size
        actual_sha256 = _sha256_file(path)
        try:
            with zipfile.ZipFile(path) as archive:
                bad_member = archive.testzip()
        except Exception as exc:
            checks.append(
                _check("zip_integrity", "failed", f"Zip file is invalid: {exc}", {"path": str(path)})
            )
        else:
            checks.append(
                _check(
                    "zip_integrity",
                    "passed" if bad_member is None else "failed",
                    "Zip internal CRC checks passed." if bad_member is None else f"Zip member failed CRC: {bad_member}",
                    {"path": str(path), "bad_member": bad_member or ""},
                )
            )
        if expected_sha256:
            checks.append(
                _check(
                    "zip_sha256",
                    "passed" if expected_sha256 == actual_sha256 else "failed",
                    "Zip sha256 matches." if expected_sha256 == actual_sha256 else "Zip sha256 mismatch.",
                    {
                        "path": str(path),
                        "expected_sha256": expected_sha256,
                        "actual_sha256": actual_sha256,
                    },
                )
            )
        if expected_size_bytes:
            checks.append(
                _check(
                    "zip_size",
                    "passed" if int(expected_size_bytes) == actual_size else "failed",
                    "Zip size matches." if int(expected_size_bytes) == actual_size else "Zip size mismatch.",
                    {
                        "path": str(path),
                        "expected_size_bytes": int(expected_size_bytes),
                        "actual_size_bytes": actual_size,
                    },
                )
            )
    result = {
        "batch_id": _batch_id_from_export_zip_path(path),
        "zip_path": str(path),
        "zip_size_bytes": actual_size,
        "zip_sha256": actual_sha256,
        "valid": all(check["status"] != "failed" for check in checks),
        "summary": {
            "total": len(checks),
            "passed": sum(1 for check in checks if check["status"] == "passed"),
            "failed": sum(1 for check in checks if check["status"] == "failed"),
        },
        "checks": checks,
    }
    if save_report:
        _write_validation_report(path.with_suffix(path.suffix + ".validation.json"), result)
    return result


def validate_batch_export_package(
    export_dir: str | Path,
    *,
    save_report: bool = False,
) -> dict[str, Any]:
    root = Path(export_dir)
    checks: list[dict[str, Any]] = []
    manifest_path = root / "batch_export_manifest.json"
    publish_index_path = root / "publish_index.json"
    publish_csv_path = root / "publish_index.csv"
    publish_videos_dir = root / "publish_videos"
    manifest = _read_json_file(manifest_path, checks, "batch_export_manifest")
    publish_index = _read_json_file(publish_index_path, checks, "publish_index")
    checks.append(_file_check("publish_index_csv", publish_csv_path))
    checks.append(_directory_check("publish_videos_dir", publish_videos_dir))

    publish_items = []
    if isinstance(publish_index, dict):
        for item in publish_index.get("items") or []:
            if not isinstance(item, dict) or not item.get("publish_ready"):
                continue
            publish_items.append(item)
            video_path = Path(str(item.get("publish_video_path") or ""))
            checks.append(
                _file_check(
                    "publish_video_exists",
                    video_path,
                    {
                        "run_id": str(item.get("run_id") or ""),
                        "title": str(item.get("title") or ""),
                    },
                )
            )
            checks.append(_publish_video_non_empty_check(item, video_path))
            checks.append(_publish_video_openable_check(item, video_path))
            checks.append(_publish_video_checksum_check(item, video_path))

    if isinstance(manifest, dict) and isinstance(publish_index, dict):
        checks.append(
            _check(
                "publish_ready_count_matches",
                "passed"
                if int(manifest.get("publish_ready_count") or 0)
                == int(publish_index.get("publish_ready_count") or 0)
                else "failed",
                "Manifest and publish index publish-ready counts match.",
                {
                    "manifest_publish_ready_count": int(manifest.get("publish_ready_count") or 0),
                    "publish_index_publish_ready_count": int(publish_index.get("publish_ready_count") or 0),
                },
            )
        )

    batch_id = _batch_id_from_export_package(root, manifest, publish_index)
    result = {
        "batch_id": batch_id,
        "export_dir": str(root),
        "valid": all(check["status"] != "failed" for check in checks),
        "summary": {
            "total": len(checks),
            "passed": sum(1 for check in checks if check["status"] == "passed"),
            "failed": sum(1 for check in checks if check["status"] == "failed"),
            "skipped": sum(1 for check in checks if check["status"] == "skipped"),
        },
        "checks": checks,
        "publish_items": publish_items,
    }
    if save_report:
        _write_validation_report(root / "validation_report.json", result)
    return result


def _batch_id_from_export_package(root: Path, manifest: Any, publish_index: Any) -> str:
    for payload in (publish_index, manifest):
        if isinstance(payload, dict):
            batch_id = str(payload.get("batch_id") or "")
            if batch_id:
                return batch_id
    return root.name


def _batch_id_from_export_zip_path(path: Path) -> str:
    name = path.name
    if name.endswith(".zip"):
        return name[: -len(".zip")]
    return path.stem


def _write_validation_report(path: Path, result: dict[str, Any]) -> None:
    result["report_path"] = str(path)
    _write_json(path, result)


def _read_json_file(path: Path, checks: list[dict[str, Any]], name: str) -> Any:
    if not path.exists() or not path.is_file():
        checks.append(_file_check(name, path))
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        checks.append(
            _check(name, "failed", f"{name} JSON is invalid: {exc}", {"path": str(path)})
        )
        return None
    checks.append(_file_check(name, path))
    return payload


def _file_check(
    name: str,
    path: Path,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    exists = path.exists() and path.is_file()
    return _check(
        name,
        "passed" if exists else "failed",
        f"{name} exists." if exists else f"{name} missing.",
        {"path": str(path), **(details or {})},
    )


def _directory_check(name: str, path: Path) -> dict[str, Any]:
    exists = path.exists() and path.is_dir()
    return _check(
        name,
        "passed" if exists else "failed",
        f"{name} exists." if exists else f"{name} missing.",
        {"path": str(path)},
    )


def _publish_video_checksum_check(item: dict[str, Any], video_path: Path) -> dict[str, Any]:
    expected_sha256 = str(item.get("publish_video_sha256") or "")
    expected_size = int(item.get("publish_video_size_bytes") or 0)
    details = {
        "path": str(video_path),
        "run_id": str(item.get("run_id") or ""),
        "title": str(item.get("title") or ""),
        "expected_size_bytes": expected_size,
        "expected_sha256": expected_sha256,
        "actual_size_bytes": 0,
        "actual_sha256": "",
    }
    if not video_path.exists() or not video_path.is_file():
        return _check(
            "publish_video_checksum",
            "skipped",
            "publish video checksum skipped because the file is missing.",
            details,
        )
    actual_size = video_path.stat().st_size
    actual_sha256 = _sha256_file(video_path)
    details["actual_size_bytes"] = actual_size
    details["actual_sha256"] = actual_sha256
    passed = bool(expected_sha256) and expected_sha256 == actual_sha256 and expected_size == actual_size
    return _check(
        "publish_video_checksum",
        "passed" if passed else "failed",
        "publish video checksum matches." if passed else "publish video checksum mismatch.",
        details,
    )


def _publish_video_non_empty_check(item: dict[str, Any], video_path: Path) -> dict[str, Any]:
    details = {
        "path": str(video_path),
        "run_id": str(item.get("run_id") or ""),
        "title": str(item.get("title") or ""),
        "size_bytes": 0,
    }
    if not video_path.exists() or not video_path.is_file():
        return _check(
            "publish_video_non_empty",
            "skipped",
            "publish video non-empty check skipped because the file is missing.",
            details,
        )
    size_bytes = video_path.stat().st_size
    details["size_bytes"] = size_bytes
    return _check(
        "publish_video_non_empty",
        "passed" if size_bytes > 0 else "failed",
        "publish video is non-empty." if size_bytes > 0 else "publish video is empty.",
        details,
    )


def _publish_video_openable_check(item: dict[str, Any], video_path: Path) -> dict[str, Any]:
    details = {
        **check_local_video_file(str(video_path)),
        "run_id": str(item.get("run_id") or ""),
        "title": str(item.get("title") or ""),
    }
    if not details["exists"]:
        return _check(
            "publish_video_openable",
            "skipped",
            "publish video openability check skipped because the file is missing.",
            details,
        )
    return _check(
        "publish_video_openable",
        "passed" if details["openable"] else "failed",
        "publish video container is recognized."
        if details["openable"]
        else "publish video container is not recognized.",
        details,
    )


def _check(
    name: str,
    status: str,
    message: str,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "name": name,
        "status": status,
        "message": message,
        "details": details or {},
    }


def _build_publish_index(
    batch_id: str,
    export_dir: Path,
    exported_items: list[dict[str, Any]],
) -> dict[str, Any]:
    items = [_build_publish_index_item(item) for item in exported_items]
    return {
        "batch_id": batch_id,
        "export_dir": str(export_dir),
        "total_items": len(items),
        "publish_ready_count": sum(1 for item in items if item["publish_ready"]),
        "items": items,
    }


def _build_publish_index_item(item: dict[str, Any]) -> dict[str, Any]:
    exported_files = item.get("exported_files") or {}
    recommended_action = item.get("recommended_action") or {}
    scores = item.get("scores") or {}
    return {
        "index": item.get("index"),
        "run_id": item.get("run_id", ""),
        "idea": item.get("idea", ""),
        "title": item.get("title", ""),
        "core_sentence": item.get("core_sentence", ""),
        "publish_ready": bool(item.get("publish_ready")),
        "status": item.get("status", ""),
        "primary_video_path": item.get("primary_video_path", ""),
        "exported_video_path": exported_files.get("video", ""),
        "publish_video_path": exported_files.get("publish_video", ""),
        "publish_video_size_bytes": exported_files.get("publish_video_size_bytes", 0),
        "publish_video_sha256": exported_files.get("publish_video_sha256", ""),
        "artifact_dir": item.get("artifact_dir", ""),
        "export_dir": item.get("export_dir", ""),
        "scores": scores,
        "recommended_action_code": recommended_action.get("code", ""),
    }


def _write_publish_index_csv(path: Path, items: list[dict[str, Any]]) -> None:
    rows = []
    for item in items:
        row = {key: item.get(key, "") for key in PUBLISH_INDEX_COLUMNS}
        row["publish_ready"] = "true" if item.get("publish_ready") else "false"
        row["scores_json"] = json.dumps(item.get("scores") or {}, ensure_ascii=False, sort_keys=True)
        rows.append(row)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=PUBLISH_INDEX_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def _write_release_notes(
    export_dir: Path,
    batch_id: str,
    artifact_index: dict[str, Any],
    publish_index: dict[str, Any],
) -> Path:
    path = export_dir / RELEASE_NOTES_FILENAME
    path.write_text(
        _build_release_notes(export_dir, batch_id, artifact_index, publish_index),
        encoding="utf-8",
    )
    return path


def _build_release_notes(
    export_dir: Path,
    batch_id: str,
    artifact_index: dict[str, Any],
    publish_index: dict[str, Any],
) -> str:
    items = publish_index.get("items") or []
    publish_ready_items = [item for item in items if item.get("publish_ready")]
    needs_attention_items = [item for item in items if not item.get("publish_ready")]
    summary = artifact_index.get("summary") or {}

    lines = [
        "# Relief Story Batch Export",
        "",
        f"- Batch ID: `{_md_inline(batch_id)}`",
        f"- Status: `{_md_inline(str(artifact_index.get('status') or ''))}`",
        f"- Total items: {len(items)}",
        f"- Publish-ready videos: {len(publish_ready_items)}",
        f"- Failed items: {summary.get('failed', 0)}",
        "",
        "## Key Files",
        "",
        "- `batch_export_manifest.json` - full export manifest and provenance.",
        "- `publish_index.json` - machine-readable publish index.",
        "- `publish_index.csv` - spreadsheet-friendly publish index.",
        "- `publish_videos/` - flat folder with publish-ready videos only.",
        "- Optional: `validation_report.json` is written after export validation.",
        "",
        "## Publish-Ready Videos",
        "",
    ]

    if publish_ready_items:
        lines.extend(
            [
                "| # | Title | Core | Video |",
                "|---|---|---|---|",
            ]
        )
        for item in publish_ready_items:
            lines.append(
                "| {index} | {title} | {core} | `{video}` |".format(
                    index=_md_cell(item.get("index", "")),
                    title=_md_cell(item.get("title") or item.get("idea") or item.get("run_id") or ""),
                    core=_md_cell(item.get("core_sentence", "")),
                    video=_md_cell(_relative_export_path(item.get("publish_video_path", ""), export_dir)),
                )
            )
    else:
        lines.append("No publish-ready videos yet.")

    lines.extend(["", "## Needs Attention", ""])
    if needs_attention_items:
        lines.extend(
            [
                "| # | Idea | Status | Recommended action |",
                "|---|---|---|---|",
            ]
        )
        for item in needs_attention_items:
            lines.append(
                "| {index} | {idea} | {status} | `{action}` |".format(
                    index=_md_cell(item.get("index", "")),
                    idea=_md_cell(item.get("idea") or item.get("title") or item.get("run_id") or ""),
                    status=_md_cell(item.get("status", "")),
                    action=_md_cell(item.get("recommended_action_code", "")),
                )
            )
    else:
        lines.append("No items need attention.")

    lines.extend(
        [
            "",
            "## Validation",
            "",
            f"- Package validation API: `POST /api/batches/{_md_inline(batch_id)}/export/validate`",
            f"- Zip validation API: `POST /api/batches/{_md_inline(batch_id)}/export/validate-zip`",
            "- When zip export is enabled, a `.sha256` sidecar is generated next to the zip package.",
            "",
        ]
    )
    return "\n".join(lines)


def _relative_export_path(path_value: str, export_dir: Path) -> str:
    if not path_value:
        return ""
    path = Path(path_value)
    try:
        return path.relative_to(export_dir).as_posix()
    except ValueError:
        return str(path).replace("\\", "/")


def _md_cell(value: Any) -> str:
    return _md_inline(str(value)).replace("|", "\\|")


def _md_inline(value: str) -> str:
    return value.replace("\r", " ").replace("\n", " ").strip()


def _build_zip_package_metadata(zip_path: Path) -> dict[str, Any]:
    metadata = {
        "path": str(zip_path),
        "size_bytes": zip_path.stat().st_size,
        "sha256": _sha256_file(zip_path),
        "sha256_path": str(zip_path.with_suffix(zip_path.suffix + ".sha256")),
    }
    zip_path.with_suffix(zip_path.suffix + ".sha256").write_text(
        f"{metadata['sha256']}  {zip_path.name}\n",
        encoding="utf-8",
    )
    return metadata


def _build_manifest(run: RunState, artifact_dir: Path) -> dict[str, Any]:
    final_storyboard = run.final_storyboard or run.storyboard
    comfyui_preview = _build_comfyui_preview(run, final_storyboard)
    artifacts = []
    for name, filename, kind in ARTIFACT_SPECS:
        path = artifact_dir / filename
        artifacts.append(
            {
                "name": name,
                "kind": kind,
                "filename": filename,
                "path": str(path),
                "exists": path.exists(),
            }
        )
    if run.grid_image_asset:
        grid_image_path = Path(run.grid_image_asset.local_path)
        grid_specs = [
            ("four_grid_prompt", "09_four_grid_prompt.json", "json"),
            ("four_grid_image", f"10_four_grid_image{grid_image_path.suffix.lower()}", "media"),
            ("comfyui_upload", "11_comfyui_upload.json", "json"),
        ]
        for name, filename, kind in grid_specs:
            path = artifact_dir / filename
            artifacts.append(
                {
                    "name": name,
                    "kind": kind,
                    "filename": filename,
                    "path": str(path),
                    "exists": path.exists(),
                }
            )
    return {
        "run_id": run.run_id,
        "artifact_dir": str(artifact_dir),
        "artifacts": artifacts,
        "grid_image_asset": (
            run.grid_image_asset.model_dump() if run.grid_image_asset else None
        ),
        "grid_image_checkpoint": run.grid_image_checkpoint,
        "grid_image_replacements": list(run.grid_image_replacements),
        "configuration_provenance": build_run_configuration_provenance(run.request),
        "final_prompt_summary": _build_final_prompt_summary(final_storyboard),
        "timeline_summary": _build_timeline_summary(run),
        "comfyui_preview": comfyui_preview,
        "comfyui_prompt_ids": list(run.comfyui_prompt_ids),
        "actual_outputs": [output.model_dump() for output in run.comfyui_outputs],
        "comfyui_cancellations": [
            item.model_dump() for item in run.comfyui_cancellations
        ],
        "comfyui_diagnostics": dict(run.comfyui_diagnostics),
        "last_failure": _failure_record_dump(run.last_failure),
        "failure_records": [
            record.model_dump() for record in run.failure_records
        ],
        "expected_outputs": [
            {
                "type": "video",
                "path": str(artifact_dir / f"{run.run_id}.mp4"),
                "exists": (artifact_dir / f"{run.run_id}.mp4").exists(),
            }
        ],
    }


def _build_timeline(run: RunState) -> dict[str, Any]:
    return {
        "run_id": run.run_id,
        "status": run.status,
        "current_stage": run.current_stage,
        "failed_stage": run.failed_stage,
        "last_completed_stage": run.last_completed_stage,
        "execution_attempt": run.execution_attempt,
        "retry_count": run.retry_count,
        "created_at": run.created_at,
        "updated_at": run.updated_at,
        "queued_at": run.queued_at,
        "started_at": run.started_at,
        "finished_at": run.finished_at,
        "summary": _build_timeline_summary(run),
        "events": [event.model_dump() for event in run.events],
        "logs": [log.model_dump() for log in run.logs],
    }


def _build_timeline_summary(run: RunState) -> dict[str, Any]:
    stage_event_counts: dict[str, int] = {}
    event_type_counts: dict[str, int] = {}
    stage_durations_seconds: dict[str, float] = {}
    open_stage_starts: dict[str, datetime] = {}

    first_timestamp = ""
    last_timestamp = ""
    for event in run.events:
        if not first_timestamp:
            first_timestamp = event.timestamp
        last_timestamp = event.timestamp
        event_type_counts[event.event_type] = event_type_counts.get(event.event_type, 0) + 1
        if event.stage:
            stage_event_counts[event.stage] = stage_event_counts.get(event.stage, 0) + 1
            event_time = _parse_iso_datetime(event.timestamp)
            if event_time and event.event_type == "stage_started":
                open_stage_starts[event.stage] = event_time
            elif event_time and event.event_type == "stage_completed" and event.stage in open_stage_starts:
                elapsed = max(0.0, (event_time - open_stage_starts.pop(event.stage)).total_seconds())
                stage_durations_seconds[event.stage] = round(
                    stage_durations_seconds.get(event.stage, 0.0) + elapsed,
                    3,
                )

    return {
        "event_count": len(run.events),
        "log_count": len(run.logs),
        "stage_event_counts": stage_event_counts,
        "event_type_counts": event_type_counts,
        "stage_durations_seconds": stage_durations_seconds,
        "first_event_at": first_timestamp,
        "last_event_at": last_timestamp,
        "terminal_status": run.status if run.status in {"completed", "failed", "cancelled"} else "",
        "failed_stage": run.failed_stage,
        "last_completed_stage": run.last_completed_stage,
    }


def _parse_iso_datetime(value: str) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _build_final_prompt_summary(storyboard: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "shot_count": len(storyboard),
        "shots": [
            {
                "shot_id": shot.get("shot_id", index),
                "time_range": str(shot.get("time_range") or ""),
                "description": str(shot.get("description") or ""),
                "image_prompt": str(shot.get("image_prompt") or ""),
                "negative_prompt": str(shot.get("negative_prompt") or ""),
                "comfyui_input_keys": sorted((shot.get("comfyui_inputs") or {}).keys()),
            }
            for index, shot in enumerate(storyboard, start=1)
        ],
    }


def _build_comfyui_preview(run: RunState, storyboard: list[dict[str, Any]]) -> dict[str, Any]:
    config = run.request.comfyui
    if not config or not config.enabled:
        return {"enabled": False, "will_enqueue": False, "items": []}
    if not storyboard:
        return {
            "enabled": True,
            "will_enqueue": False,
            "error": "No final storyboard is available for ComfyUI preview.",
            "items": [],
        }
    try:
        return preview_storyboard_submission(
            config,
            storyboard,
            run.run_id,
            duration_seconds=int(run.script.get("duration_seconds") or run.request.duration_seconds),
            include_workflow=False,
        )
    except Exception as exc:
        return {
            "enabled": True,
            "will_enqueue": False,
            "error": str(exc),
            "items": [],
        }


def _build_batch_audit_summary(items: list[dict[str, Any]]) -> dict[str, Any]:
    by_status: dict[str, int] = {}
    by_failed_stage: dict[str, int] = {}
    usage = _empty_usage_summary()
    failed_items = []
    retryable_items = []
    recommended_actions: dict[str, int] = {}

    for item in items:
        status = str(item.get("status") or "")
        by_status[status] = by_status.get(status, 0) + 1
        failed_stage = str(item.get("failed_stage") or "")
        if failed_stage:
            by_failed_stage[failed_stage] = by_failed_stage.get(failed_stage, 0) + 1
        item_usage = item.get("model_usage_summary") or {}
        _add_usage_summary(usage, item_usage)
        action_code = str((item.get("recommended_action") or {}).get("code") or "")
        if action_code:
            recommended_actions[action_code] = recommended_actions.get(action_code, 0) + 1
        if status == "failed":
            failed_items.append(
                {
                    "index": item.get("index"),
                    "run_id": item.get("run_id"),
                    "idea": item.get("idea", ""),
                    "failed_stage": failed_stage,
                    "retryable": bool(item.get("retryable")),
                    "error": item.get("error", ""),
                }
            )
        if item.get("retryable"):
            retryable_items.append(
                {
                    "index": item.get("index"),
                    "run_id": item.get("run_id"),
                    "retry_from_stage": item.get("retry_from_stage", ""),
                }
            )

    return {
        "total_items": len(items),
        "publish_ready_count": sum(1 for item in items if item.get("publish_ready")),
        "failed_count": sum(1 for item in items if item.get("status") == "failed"),
        "retryable_count": len(retryable_items),
        "by_status": by_status,
        "by_failed_stage": by_failed_stage,
        "usage": usage,
        "failed_items": failed_items,
        "retryable_items": retryable_items,
        "recommended_actions": recommended_actions,
    }


def _empty_usage_summary() -> dict[str, Any]:
    return {
        "total_requests": 0,
        "total_attempts": 0,
        "retry_count": 0,
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
        "estimated_cost_usd": 0.0,
    }


def _add_usage_summary(total: dict[str, Any], current: dict[str, Any]) -> None:
    for key in (
        "total_requests",
        "total_attempts",
        "retry_count",
        "prompt_tokens",
        "completion_tokens",
        "total_tokens",
    ):
        total[key] += int(current.get(key) or 0)
    total["estimated_cost_usd"] = round(
        float(total["estimated_cost_usd"]) + float(current.get("estimated_cost_usd") or 0),
        12,
    )


def _is_retryable_run(run: RunState, *, retry_from_stage: str = "") -> bool:
    if run.last_failure is not None:
        return run.status == "failed" and run.last_failure.retryable and bool(retry_from_stage)
    return run.status == "failed" and bool(retry_from_stage)


def _retry_from_stage_for_run(
    run: RunState,
    timeline_diagnostics: dict[str, Any] | None = None,
) -> str:
    if run.failed_stage:
        return run.failed_stage
    diagnostics = timeline_diagnostics or _build_timeline_recovery_diagnostics(run)
    inferred = str(diagnostics.get("inferred_retry_from_stage") or "")
    if inferred:
        return inferred
    if run.current_stage in RECOVERABLE_STAGE_ORDER:
        return run.current_stage
    return ""


def _build_timeline_recovery_diagnostics(run: RunState) -> dict[str, Any]:
    completed_stages: list[str] = []
    open_stages: list[str] = []
    last_stage = ""
    last_event_type = ""

    for event in run.events:
        if event.stage:
            last_stage = event.stage
        last_event_type = event.event_type
        if not event.stage:
            continue
        if event.event_type == "stage_started":
            if event.stage not in open_stages:
                open_stages.append(event.stage)
        elif event.event_type == "stage_completed":
            if event.stage not in completed_stages:
                completed_stages.append(event.stage)
            open_stages = [stage for stage in open_stages if stage != event.stage]

    inferred = ""
    reason = ""
    if open_stages:
        inferred = open_stages[-1]
        reason = "Last started stage has no matching completion event."
    elif completed_stages:
        inferred = _next_recoverable_stage(completed_stages[-1])
        if inferred:
            reason = "Recovered from the stage after the last completion checkpoint."

    return {
        "event_count": len(run.events),
        "completed_stages": completed_stages,
        "open_stages": open_stages,
        "last_stage": last_stage,
        "last_event_type": last_event_type,
        "inferred_retry_from_stage": inferred,
        "inference_reason": reason,
    }


def _next_recoverable_stage(stage: str) -> str:
    if stage not in RECOVERABLE_STAGE_ORDER:
        return ""
    index = RECOVERABLE_STAGE_ORDER.index(stage) + 1
    return RECOVERABLE_STAGE_ORDER[index] if index < len(RECOVERABLE_STAGE_ORDER) else ""


def _recommended_action_for_missing_run(batch_item) -> dict[str, str]:
    return {
        "code": "inspect_missing_run",
        "label": "Inspect missing run state",
        "description": f"Run state for {batch_item.run_id} was not found. Check persisted state files before retrying.",
        "retry_from_stage": "",
        "endpoint": "",
    }


def _recommended_action_for_run(
    run: RunState,
    *,
    primary_video_path: str,
    retryable: bool,
    retry_from_stage: str = "",
) -> dict[str, str]:
    error = run.error or ""
    error_lower = error.lower()
    failed_stage = retry_from_stage or run.failed_stage or ""

    if run.status == "completed" and primary_video_path:
        return {
            "code": "publish",
            "label": "Ready to publish",
            "description": "A video output is available and this item can be included in publish/export flows.",
            "retry_from_stage": "",
            "endpoint": "",
        }
    if run.status == "completed" and run.comfyui_prompt_ids and not primary_video_path:
        return {
            "code": "refresh_comfyui_outputs",
            "label": "Refresh ComfyUI outputs",
            "description": "Prompt IDs exist but no local or remote video output is indexed yet.",
            "retry_from_stage": "",
            "endpoint": f"/api/runs/{run.run_id}/refresh-comfyui",
        }
    if run.status == "completed":
        return {
            "code": "inspect_outputs",
            "label": "Inspect outputs",
            "description": "The run completed but no publishable video output is indexed.",
            "retry_from_stage": "",
            "endpoint": f"/api/runs/{run.run_id}/artifacts",
        }
    if run.status in {"queued", "running", "paused", "awaiting_approval"}:
        return {
            "code": "wait",
            "label": "Wait for run",
            "description": "The item is not terminal yet.",
            "retry_from_stage": "",
            "endpoint": f"/api/runs/{run.run_id}",
        }
    if run.status == "cancelled":
        return {
            "code": "manual_review_cancelled",
            "label": "Review cancellation",
            "description": "The item was cancelled and needs an operator decision before rerun.",
            "retry_from_stage": "",
            "endpoint": f"/api/runs/{run.run_id}",
        }

    if run.last_failure is not None and not run.last_failure.retryable:
        structured_action = _recommended_action_for_failure(
            run,
            failed_stage=failed_stage,
        )
        if structured_action:
            return structured_action

    if "template" in error_lower or "placeholder(s)" in error_lower:
        return {
            "code": "fix_template",
            "label": "Fix prompt template",
            "description": "A configurable prompt template appears missing, unreadable, or invalid.",
            "retry_from_stage": failed_stage,
            "endpoint": f"/api/runs/{run.run_id}/retry",
        }
    if (
        "placeholder_map" in error_lower
        or "workflow" in error_lower
        or "comfyui" in failed_stage.lower()
    ):
        return {
            "code": "check_comfyui_mapping",
            "label": "Check ComfyUI mapping",
            "description": "ComfyUI workflow or placeholder mapping needs inspection before retry.",
            "retry_from_stage": failed_stage,
            "endpoint": "/api/comfyui/preview",
        }
    if failed_stage in {"gpt_prompt_audit", "gpt_prompt_reviser"} or "axis" in error_lower:
        return {
            "code": "manual_review_prompt_audit",
            "label": "Review prompt audit",
            "description": "The prompt audit or revision stage found visual/spatial logic issues.",
            "retry_from_stage": failed_stage,
            "endpoint": f"/api/runs/{run.run_id}/retry",
        }
    if failed_stage == "quality_gate":
        return {
            "code": "manual_review_script_quality",
            "label": "Review script quality gate",
            "description": "The polished script did not pass low-stimulation quality rules.",
            "retry_from_stage": failed_stage,
            "endpoint": f"/api/runs/{run.run_id}/retry",
        }
    if retryable:
        return {
            "code": "retry_from_stage",
            "label": "Retry from failed stage",
            "description": "The run has a recorded or timeline-inferred retry stage and can be retried without rerunning completed stages.",
            "retry_from_stage": failed_stage,
            "endpoint": f"/api/runs/{run.run_id}/retry",
        }
    return {
        "code": "manual_review",
        "label": "Manual review",
        "description": "No automatic recovery action is safe to recommend from the available state.",
        "retry_from_stage": "",
        "endpoint": f"/api/runs/{run.run_id}",
    }


def _failure_record_dump(record) -> dict[str, Any]:
    return record.model_dump() if record is not None else {}


def _recommended_action_for_failure(
    run: RunState,
    *,
    failed_stage: str,
) -> dict[str, str]:
    assert run.last_failure is not None
    category = run.last_failure.category
    code = run.last_failure.code
    if category == "configuration":
        return {
            "code": "fix_template" if "template" in code else "manual_review",
            "label": "Fix configuration",
            "description": "A configuration or local file issue must be fixed before retry.",
            "retry_from_stage": failed_stage,
            "endpoint": f"/api/runs/{run.run_id}",
        }
    if category == "external":
        return {
            "code": "check_comfyui_mapping",
            "label": "Check ComfyUI mapping",
            "description": "ComfyUI workflow or placeholder mapping needs inspection before retry.",
            "retry_from_stage": failed_stage,
            "endpoint": "/api/comfyui/preview",
        }
    if category == "validation":
        return {
            "code": "manual_review_script_quality"
            if failed_stage == "quality_gate"
            else "manual_review",
            "label": "Review validation failure",
            "description": "A business validation gate failed and needs operator review before retry.",
            "retry_from_stage": failed_stage,
            "endpoint": f"/api/runs/{run.run_id}",
        }
    if category == "contract":
        return {
            "code": "manual_review_prompt_audit"
            if failed_stage in {"gpt_prompt_audit", "gpt_prompt_reviser"}
            else "manual_review",
            "label": "Review output contract",
            "description": "A model or stage output contract failed and should be inspected before retry.",
            "retry_from_stage": failed_stage,
            "endpoint": f"/api/runs/{run.run_id}",
        }
    return {
        "code": "manual_review",
        "label": "Manual review",
        "description": "Structured failure policy does not allow automatic retry for this failure.",
        "retry_from_stage": "",
        "endpoint": f"/api/runs/{run.run_id}",
    }


def _primary_video_path(outputs: list[dict[str, Any]]) -> str:
    for output in outputs:
        if output.get("media_type") == "video" and output.get("local_path"):
            return str(output["local_path"])
    for output in outputs:
        if output.get("media_type") == "video" and output.get("url"):
            return str(output["url"])
    return ""


def _copy_run_artifacts(
    run: RunState,
    item_dir: Path,
    exported_item: dict[str, Any],
) -> None:
    run_index = read_run_artifact_index(run)
    copied = []
    target_dir = item_dir / "run_artifacts"
    target_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = Path(run_index["artifact_dir"]) / "00_manifest.json"
    candidates = [manifest_path] + [
        Path(artifact["path"])
        for artifact in run_index.get("artifacts", [])
        if artifact.get("exists")
    ]
    for source in candidates:
        if not source.exists() or not source.is_file():
            continue
        target = target_dir / source.name
        shutil.copy2(source, target)
        copied.append(str(target))
    exported_item["exported_files"]["run_artifacts"] = copied


def _copy_primary_video(
    item: dict[str, Any],
    item_dir: Path,
    exported_item: dict[str, Any],
) -> None:
    primary_video_path = item.get("primary_video_path") or ""
    if not primary_video_path:
        return
    source = Path(primary_video_path)
    if not source.exists() or not source.is_file():
        return
    target = item_dir / f"video_{source.name}"
    shutil.copy2(source, target)
    exported_item["exported_files"]["video"] = str(target)


def _copy_publish_video(exported_item: dict[str, Any], publish_videos_dir: Path) -> None:
    if not exported_item.get("publish_ready"):
        return
    exported_files = exported_item.get("exported_files") or {}
    video_path = exported_files.get("video", "")
    if not video_path:
        return
    source = Path(video_path)
    if not source.exists() or not source.is_file():
        return
    suffix = source.suffix or ".mp4"
    filename = f"{int(exported_item.get('index') or 0):03d}_{_safe_path_segment(str(exported_item.get('title') or exported_item.get('idea') or exported_item.get('run_id') or 'video'))}{suffix}"
    target = _unique_path(publish_videos_dir / filename)
    shutil.copy2(source, target)
    exported_item["exported_files"]["publish_video"] = str(target)
    exported_item["exported_files"]["publish_video_size_bytes"] = target.stat().st_size
    exported_item["exported_files"]["publish_video_sha256"] = _sha256_file(target)


def _default_batch_export_root(runs: list[RunState]) -> Path:
    for run in runs:
        if run.request.output_root:
            return Path(run.request.output_root) / "batch_exports"
    return Path("runs") / "batch_exports"


def _export_item_dirname(item: dict[str, Any]) -> str:
    label = item.get("title") or item.get("idea") or item.get("run_id") or "run"
    return f"{int(item.get('index') or 0):03d}_{_safe_path_segment(str(label))}"


def _safe_path_segment(value: str) -> str:
    safe = "".join(char if char.isalnum() or char in "._-" else "_" for char in value)
    safe = "_".join(part for part in safe.split("_") if part)
    return (safe or "run")[:64]


def _unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    for index in range(1, 10_000):
        candidate = path.with_name(f"{stem}_{index}{suffix}")
        if not candidate.exists():
            return candidate
    raise ValueError(f"Could not allocate a unique filename for {path}")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _zip_directory(source_dir: Path, zip_path: Path) -> None:
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in source_dir.rglob("*"):
            if path.is_file():
                archive.write(path, path.relative_to(source_dir.parent))


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
