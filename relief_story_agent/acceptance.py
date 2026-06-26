from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .video_validation import check_local_video_file


PASS_STATUSES = {"pass", "passed", "ok", "completed"}


DEFAULT_ACCEPTANCE_MATRIX: tuple[dict[str, str], ...] = (
    {
        "id": "full_tests",
        "required_evidence": "python -m pytest relief_story_agent/tests -q output",
    },
    {
        "id": "pipeline_schema",
        "required_evidence": "pipeline-schema JSON with fixed canonical stage order and invariants",
    },
    {
        "id": "local_demo",
        "required_evidence": "local_demo_summary.json, fake model run and batch artifacts",
    },
    {
        "id": "comfyui_dry_smoke",
        "required_evidence": "smoke_result.json, no prompt id",
    },
    {
        "id": "comfyui_real_smoke",
        "required_evidence": "smoke_result.json, prompt id",
    },
    {
        "id": "comfyui_outputs",
        "required_evidence": "comfyui-outputs JSON, ready=true, video_count>0, openable downloaded video path",
    },
    {
        "id": "model_check",
        "required_evidence": "model-check JSON, ready=true, text profiles and image provider covered",
    },
    {
        "id": "run_diagnose",
        "required_evidence": "diagnose run JSON, ready=true",
    },
    {
        "id": "batch_diagnose",
        "required_evidence": "diagnose batch JSON, ready=true",
    },
    {
        "id": "single_run",
        "required_evidence": "run artifact dir, openable downloaded video path",
    },
    {
        "id": "batch_run",
        "required_evidence": "batch id, item summaries",
    },
    {
        "id": "restart_recovery",
        "required_evidence": "recovery-plan before/after restart",
    },
    {
        "id": "export",
        "required_evidence": "publish index, zip, sha256",
    },
    {
        "id": "fresh_setup",
        "required_evidence": "commands from docs run on clean env",
    },
)


def write_acceptance_report(output_dir: str | Path, payload: dict[str, Any]) -> str:
    target_dir = Path(output_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    video_paths = _string_list(payload.get("video_paths") or [])
    checks = [_normalize_check(check) for check in payload.get("checks") or []]
    checks.extend(checks_from_sources(payload.get("sources") or {}))
    checks = refresh_video_evidence(
        checks,
        video_paths=video_paths,
        mode=str(payload.get("mode") or "manual"),
    )
    checks = refresh_comfyui_outputs_evidence(checks)
    checks = refresh_batch_evidence(checks, batch_id=str(payload.get("batch_id") or ""))
    checks = refresh_export_evidence(checks, batch_id=str(payload.get("batch_id") or ""))
    checks = refresh_recovery_evidence(checks, batch_id=str(payload.get("batch_id") or ""))
    checks = refresh_identity_evidence(
        checks,
        run_id=str(payload.get("run_id") or ""),
        batch_id=str(payload.get("batch_id") or ""),
    )
    checks = _merge_default_matrix(checks)

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "run_id": str(payload.get("run_id") or ""),
        "batch_id": str(payload.get("batch_id") or ""),
        "mode": str(payload.get("mode") or "manual"),
        "status": str(payload.get("status") or "manual_pending"),
        "video_paths": video_paths,
        "checks": checks,
        "notes": str(payload.get("notes") or ""),
    }
    report["summary"] = _build_summary(report)

    json_path = target_dir / "acceptance_report.json"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (target_dir / "ACCEPTANCE_REPORT.md").write_text(_render_markdown(report), encoding="utf-8")
    return str(json_path)


def build_acceptance_status(report_path: str | Path) -> dict[str, Any]:
    path = Path(report_path)
    if path.exists():
        report = json.loads(path.read_text(encoding="utf-8"))
        checks = [_normalize_check(check) for check in report.get("checks") or []]
        checks = refresh_video_evidence(
            checks,
            video_paths=_string_list(report.get("video_paths") or []),
            mode=str(report.get("mode") or ""),
        )
        checks = refresh_comfyui_outputs_evidence(checks)
        checks = refresh_batch_evidence(checks, batch_id=str(report.get("batch_id") or ""))
        checks = refresh_export_evidence(checks, batch_id=str(report.get("batch_id") or ""))
        checks = refresh_recovery_evidence(checks, batch_id=str(report.get("batch_id") or ""))
        checks = refresh_identity_evidence(
            checks,
            run_id=str(report.get("run_id") or ""),
            batch_id=str(report.get("batch_id") or ""),
        )
        checks = _merge_default_matrix(checks)
        summary = _build_summary({**report, "checks": checks})
        ready_for_release = bool(summary.get("ready_for_release"))
    else:
        checks = _merge_default_matrix([])
        report = {
            "mode": "",
            "status": "missing",
            "checks": checks,
            "video_paths": [],
        }
        summary = _build_summary(report)
        ready_for_release = False

    blocking_checks = [
        check
        for check in checks
        if str(check.get("status") or "").lower() not in PASS_STATUSES
    ]
    overall_status = str(report.get("status") or "missing")
    if path.exists() and overall_status.lower() not in PASS_STATUSES:
        blocking_checks.insert(
            0,
            {
                "id": "overall_status",
                "required_evidence": "acceptance report top-level status is completed",
                "status": "fail",
                "evidence": f"status={overall_status}",
                "details": {"status": overall_status},
            },
        )
    ready_for_release = ready_for_release and not blocking_checks
    return {
        "report_path": str(path),
        "exists": path.exists(),
        "ready_for_release": ready_for_release,
        "summary": {
            **summary,
            "check_count": len(checks),
            "blocking_count": len(blocking_checks),
        },
        "blocking_checks": blocking_checks,
        "suggested_actions": _acceptance_status_actions(path, blocking_checks),
    }


def _normalize_check(raw_check: Any) -> dict[str, Any]:
    if not isinstance(raw_check, dict):
        return {
            "id": str(raw_check),
            "required_evidence": "",
            "status": "manual_pending",
            "evidence": "",
        }
    return {
        "id": str(raw_check.get("id") or ""),
        "required_evidence": str(raw_check.get("required_evidence") or ""),
        "status": str(raw_check.get("status") or "manual_pending"),
        "evidence": str(raw_check.get("evidence") or ""),
        "details": raw_check.get("details") or {},
    }


def checks_from_sources(sources: dict[str, Any]) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    smoke_result = sources.get("smoke_result")
    if smoke_result:
        checks.append(_check_from_smoke_result(Path(str(smoke_result))))
    local_demo_summary = sources.get("local_demo_summary")
    if local_demo_summary:
        checks.append(_check_from_local_demo_summary(Path(str(local_demo_summary))))
    return checks


def _check_from_video_paths(video_paths: list[str]) -> dict[str, Any]:
    video_checks = [check_local_video_file(path_value) for path_value in video_paths]
    valid_count = sum(1 for check in video_checks if check["valid"])
    return {
        "id": "video_files",
        "required_evidence": "local video files exist, are non-empty, and are openable",
        "status": "pass" if valid_count == len(video_checks) else "fail",
        "evidence": f"valid_videos={valid_count}/{len(video_checks)}",
        "details": {"videos": video_checks},
    }


def refresh_video_evidence(
    checks: list[dict[str, Any]],
    *,
    video_paths: list[str],
    mode: str,
) -> list[dict[str, Any]]:
    checks_without_video = [
        check for check in checks if str(check.get("id") or "") != "video_files"
    ]
    if video_paths:
        return [*checks_without_video, _check_from_video_paths(video_paths)]

    single_run_passed = any(
        str(check.get("id") or "") == "single_run"
        and str(check.get("status") or "").lower() in PASS_STATUSES
        for check in checks
    )
    if mode != "single_run" and not single_run_passed:
        return checks
    return [
        *checks_without_video,
        {
            "id": "video_files",
            "required_evidence": "local video files exist, are non-empty, and are openable",
            "status": "fail",
            "evidence": "missing video_paths for single_run acceptance",
            "details": {"videos": []},
        },
    ]


def refresh_comfyui_outputs_evidence(checks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        _refreshed_comfyui_outputs_check(check)
        if str(check.get("id") or "") == "comfyui_outputs"
        and str(check.get("status") or "").lower() in PASS_STATUSES
        else check
        for check in checks
    ]


def _refreshed_comfyui_outputs_check(check: dict[str, Any]) -> dict[str, Any]:
    details = check.get("details") if isinstance(check.get("details"), dict) else {}
    output_evidence = _comfyui_outputs_evidence_status(details)
    valid = bool(output_evidence["valid"])
    return {
        **check,
        "status": "pass" if valid else "fail",
        "evidence": (
            f"comfyui_outputs_valid={str(valid).lower()}; "
            f"ready={str(bool(output_evidence['ready'])).lower()}; "
            f"video_count={output_evidence['video_count']}; "
            f"downloaded_videos_valid="
            f"{output_evidence['valid_downloaded_video_count']}/{output_evidence['downloaded_video_count']}"
        ),
        "details": {
            **details,
            "comfyui_outputs_evidence": output_evidence,
        },
    }


def _comfyui_outputs_evidence_status(details: dict[str, Any]) -> dict[str, Any]:
    result = {
        "valid": False,
        "error": "",
        "path": "",
        "exists": False,
        "ready": False,
        "status": "",
        "video_count": 0,
        "downloaded_count": 0,
        "video_output_count": 0,
        "downloaded_video_count": 0,
        "valid_downloaded_video_count": 0,
        "actual_outputs": [],
        "video_file_checks": [],
    }
    payload_result = _comfyui_outputs_payload(details)
    result = {**result, **payload_result}
    payload = payload_result.get("payload")
    if not isinstance(payload, dict):
        result.pop("payload", None)
        if not result["error"]:
            result["error"] = "missing_comfyui_outputs_evidence"
        return result

    status = str(payload.get("status") or "")
    ready = _comfyui_outputs_ready(payload)
    actual_outputs = payload.get("actual_outputs") or []
    if not isinstance(actual_outputs, list):
        actual_outputs = []
    video_outputs = [
        output
        for output in actual_outputs
        if isinstance(output, dict) and _is_comfyui_video_output(output)
    ]
    video_paths = [
        str(output.get("local_path") or "")
        for output in video_outputs
        if str(output.get("local_path") or "")
    ]
    video_file_checks = [check_local_video_file(path_value) for path_value in video_paths]
    valid_downloaded_video_count = sum(1 for check in video_file_checks if check["valid"])
    video_count = _safe_int(payload.get("video_count"), default=len(video_outputs))
    downloaded_count = _safe_int(payload.get("downloaded_count"), default=len(video_paths))

    error = ""
    if not ready:
        error = "comfyui_outputs_not_ready"
    elif video_count <= 0:
        error = "missing_video_outputs"
    elif not video_outputs:
        error = "missing_actual_video_outputs"
    elif downloaded_count <= 0 or not video_paths:
        error = "missing_downloaded_video_paths"
    elif valid_downloaded_video_count != len(video_file_checks):
        error = "invalid_downloaded_videos"

    result.update(
        {
            "valid": not error,
            "error": error,
            "ready": ready,
            "status": status,
            "video_count": video_count,
            "downloaded_count": downloaded_count,
            "video_output_count": len(video_outputs),
            "downloaded_video_count": len(video_file_checks),
            "valid_downloaded_video_count": valid_downloaded_video_count,
            "actual_outputs": video_outputs,
            "video_file_checks": video_file_checks,
        }
    )
    result.pop("payload", None)
    return result


def _comfyui_outputs_payload(details: dict[str, Any]) -> dict[str, Any]:
    raw_path = (
        details.get("comfyui_outputs_report")
        or details.get("comfyui_output_report")
        or details.get("outputs_report")
        or details.get("report_path")
        or ""
    )
    if raw_path:
        path = Path(str(raw_path))
        base = {"path": str(path), "exists": path.exists() and path.is_file()}
        if not base["exists"]:
            return {**base, "error": "missing_comfyui_outputs_report"}
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {**base, "error": "invalid_comfyui_outputs_report_json"}
        return {**base, "payload": payload}
    if "actual_outputs" in details or "ready" in details or "video_count" in details:
        return {"payload": details}
    return {"error": "missing_comfyui_outputs_evidence"}


def _comfyui_outputs_ready(payload: dict[str, Any]) -> bool:
    if "ready" in payload:
        return bool(payload.get("ready"))
    return str(payload.get("status") or "").lower() == "ready"


def _is_comfyui_video_output(output: dict[str, Any]) -> bool:
    media_type = str(output.get("media_type") or "").lower()
    if media_type == "video":
        return True
    filename = str(output.get("filename") or "")
    return Path(filename).suffix.lower() in {".mp4", ".mov", ".webm", ".mkv", ".avi"}


def _safe_int(value: Any, *, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def refresh_batch_evidence(
    checks: list[dict[str, Any]],
    *,
    batch_id: str = "",
) -> list[dict[str, Any]]:
    return [
        _refreshed_batch_run_check(check, batch_id=batch_id)
        if str(check.get("id") or "") == "batch_run"
        and str(check.get("status") or "").lower() in PASS_STATUSES
        else check
        for check in checks
    ]


def _refreshed_batch_run_check(check: dict[str, Any], *, batch_id: str) -> dict[str, Any]:
    details = check.get("details") if isinstance(check.get("details"), dict) else {}
    batch_evidence = _batch_evidence_status(details, expected_batch_id=batch_id)
    valid = bool(batch_evidence["valid"])
    return {
        **check,
        "status": "pass" if valid else "fail",
        "evidence": (
            f"batch_evidence_valid={str(valid).lower()}; "
            f"batch_id_matches={str(bool(batch_evidence['batch_id_matches'])).lower()}; "
            f"items={batch_evidence['item_count']}; "
            f"publish_ready={batch_evidence['publish_ready_count']}"
        ),
        "details": {
            **details,
            "batch_evidence": batch_evidence,
        },
    }


def _batch_evidence_status(details: dict[str, Any], *, expected_batch_id: str = "") -> dict[str, Any]:
    result = {
        "valid": False,
        "error": "",
        "path": "",
        "exists": False,
        "expected_batch_id": expected_batch_id,
        "reported_batch_id": "",
        "batch_id_matches": False,
        "status": "",
        "item_count": 0,
        "publish_ready_count": 0,
        "failed_count": 0,
        "invalid_items": [],
    }
    if not expected_batch_id:
        result["error"] = "missing_expected_batch_id"
        return result

    payload_result = _batch_evidence_payload(details)
    result = {**result, **payload_result}
    payload = payload_result.get("payload")
    if not isinstance(payload, dict):
        result.pop("payload", None)
        if not result["error"]:
            result["error"] = "missing_batch_evidence"
        return result

    reported_batch_id = str(payload.get("batch_id") or "")
    status = str(payload.get("status") or "")
    items = payload.get("items") or []
    if not isinstance(items, list):
        items = []
    invalid_items = _invalid_batch_items(items)
    publish_ready_count = sum(1 for item in items if isinstance(item, dict) and item.get("publish_ready"))
    failed_count = sum(1 for item in items if isinstance(item, dict) and str(item.get("status") or "") == "failed")
    batch_id_matches = reported_batch_id == expected_batch_id
    error = ""
    if status not in {"completed", "partial_failed"}:
        error = "batch_status_not_completed"
    elif not items:
        error = "missing_batch_items"
    elif not reported_batch_id:
        error = "missing_report_batch_id"
    elif not batch_id_matches:
        error = "batch_id_mismatch"
    elif invalid_items:
        error = "invalid_batch_items"

    result.update(
        {
            "valid": not error,
            "error": error,
            "reported_batch_id": reported_batch_id,
            "batch_id_matches": batch_id_matches,
            "status": status,
            "item_count": len(items),
            "publish_ready_count": publish_ready_count,
            "failed_count": failed_count,
            "invalid_items": invalid_items,
        }
    )
    result.pop("payload", None)
    return result


def _batch_evidence_payload(details: dict[str, Any]) -> dict[str, Any]:
    raw_path = (
        details.get("batch_artifacts_report")
        or details.get("batch_run_report")
        or details.get("batch_status_report")
        or ""
    )
    if raw_path:
        path = Path(str(raw_path))
        base = {"path": str(path), "exists": path.exists() and path.is_file()}
        if not base["exists"]:
            return {**base, "error": "missing_batch_report"}
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {**base, "error": "invalid_batch_report_json"}
        return {**base, "payload": payload}
    if "items" in details:
        return {"payload": details}
    return {"error": "missing_batch_evidence"}


def _invalid_batch_items(items: list[Any]) -> list[dict[str, Any]]:
    invalid: list[dict[str, Any]] = []
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            invalid.append({"index": index, "reason": "item_not_object"})
            continue
        run_id = str(item.get("run_id") or "")
        status = str(item.get("status") or "")
        publish_ready = bool(item.get("publish_ready"))
        primary_video_path = str(item.get("primary_video_path") or "")
        failed_stage = str(item.get("failed_stage") or "")
        action_code = str((item.get("recommended_action") or {}).get("code") or "")
        if not run_id:
            invalid.append({"index": index, "reason": "missing_run_id"})
        if publish_ready:
            if status != "completed":
                invalid.append(
                    {
                        "index": index,
                        "run_id": run_id,
                        "reason": "publish_ready_status_not_completed",
                        "status": status,
                    }
                )
            if not primary_video_path:
                invalid.append({"index": index, "run_id": run_id, "reason": "publish_ready_missing_video"})
            else:
                video_check = check_local_video_file(primary_video_path)
                if not video_check["valid"]:
                    invalid.append(
                        {
                            "index": index,
                            "run_id": run_id,
                            "reason": "publish_ready_invalid_video",
                            "video": video_check,
                        }
                    )
            continue
        if status == "failed":
            if not failed_stage:
                invalid.append({"index": index, "run_id": run_id, "reason": "failed_item_missing_failed_stage"})
            if not action_code:
                invalid.append({"index": index, "run_id": run_id, "reason": "failed_item_missing_recommended_action"})
            continue
        invalid.append({"index": index, "run_id": run_id, "reason": "item_not_publish_ready_or_failed"})
    return invalid


def refresh_export_evidence(
    checks: list[dict[str, Any]],
    *,
    batch_id: str = "",
) -> list[dict[str, Any]]:
    return [
        _refreshed_export_check(check, batch_id=batch_id)
        if str(check.get("id") or "") == "export"
        and str(check.get("status") or "").lower() in PASS_STATUSES
        else check
        for check in checks
    ]


def _refreshed_export_check(check: dict[str, Any], *, batch_id: str) -> dict[str, Any]:
    details = check.get("details") if isinstance(check.get("details"), dict) else {}
    validation_report = _validation_report_status(
        details.get("validation_report"),
        expected_batch_id=batch_id,
    )
    zip_validation_report = _validation_report_status(
        details.get("zip_validation_report"),
        expected_batch_id=batch_id,
    )
    valid = bool(validation_report["valid"] and zip_validation_report["valid"])
    return {
        **check,
        "status": "pass" if valid else "fail",
        "evidence": (
            f"validation_report_valid={str(bool(validation_report['valid'])).lower()}; "
            f"zip_validation_report_valid={str(bool(zip_validation_report['valid'])).lower()}; "
            f"validation_report_batch_id_matches={str(bool(validation_report['batch_id_matches'])).lower()}; "
            f"zip_validation_report_batch_id_matches={str(bool(zip_validation_report['batch_id_matches'])).lower()}"
        ),
        "details": {
            **details,
            "validation_report": validation_report,
            "zip_validation_report": zip_validation_report,
        },
    }


def _validation_report_status(raw_path: Any, *, expected_batch_id: str = "") -> dict[str, Any]:
    path_value = _validation_report_path(raw_path)
    result = {
        "path": path_value,
        "exists": False,
        "valid": False,
        "error": "",
        "expected_batch_id": expected_batch_id,
        "reported_batch_id": "",
        "batch_id_matches": False,
    }
    if not path_value:
        return {**result, "error": "missing_report_path"}
    path = Path(path_value)
    result["exists"] = path.exists() and path.is_file()
    if not result["exists"]:
        return {**result, "error": "missing_report"}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {**result, "error": "invalid_report_json"}
    reported_batch_id = str(payload.get("batch_id") or "") if isinstance(payload, dict) else ""
    batch_id_matches = bool(expected_batch_id and reported_batch_id == expected_batch_id)
    error = ""
    if not expected_batch_id:
        error = "missing_expected_batch_id"
    elif not reported_batch_id:
        error = "missing_report_batch_id"
    elif not batch_id_matches:
        error = "batch_id_mismatch"
    return {
        **result,
        "valid": bool(payload.get("valid")) and batch_id_matches,
        "reported_valid": bool(payload.get("valid")),
        "reported_batch_id": reported_batch_id,
        "batch_id_matches": batch_id_matches,
        "error": error,
    }


def _validation_report_path(raw_path: Any) -> str:
    if isinstance(raw_path, dict):
        return str(raw_path.get("path") or "")
    return str(raw_path or "")


def refresh_recovery_evidence(
    checks: list[dict[str, Any]],
    *,
    batch_id: str = "",
) -> list[dict[str, Any]]:
    return [
        _refreshed_restart_recovery_check(check, batch_id=batch_id)
        if str(check.get("id") or "") == "restart_recovery"
        and str(check.get("status") or "").lower() in PASS_STATUSES
        else check
        for check in checks
    ]


def _refreshed_restart_recovery_check(
    check: dict[str, Any],
    *,
    batch_id: str,
) -> dict[str, Any]:
    details = check.get("details") if isinstance(check.get("details"), dict) else {}
    recovery_evidence = _restart_recovery_evidence_status(details, expected_batch_id=batch_id)
    valid = bool(recovery_evidence["valid"])
    return {
        **check,
        "status": "pass" if valid else "fail",
        "evidence": (
            f"recovery_evidence_valid={str(valid).lower()}; "
            f"before_batch_id_matches={str(bool(recovery_evidence['before_batch_id_matches'])).lower()}; "
            f"after_batch_id_matches={str(bool(recovery_evidence['after_batch_id_matches'])).lower()}"
        ),
        "details": {
            **details,
            "recovery_evidence": recovery_evidence,
        },
    }


def _restart_recovery_evidence_status(
    details: dict[str, Any],
    *,
    expected_batch_id: str = "",
) -> dict[str, Any]:
    result = {
        "valid": False,
        "error": "",
        "path": "",
        "exists": False,
        "expected_batch_id": expected_batch_id,
        "status": "",
        "has_before_restart": False,
        "has_after_restart": False,
        "before_batch_id": "",
        "after_batch_id": "",
        "before_batch_id_matches": False,
        "after_batch_id_matches": False,
        "before_summary_present": False,
        "after_summary_present": False,
    }
    if not expected_batch_id:
        result["error"] = "missing_expected_batch_id"
        return result

    payload_result = _restart_recovery_payload(details)
    result = {**result, **payload_result}
    payload = payload_result.get("payload")
    if not isinstance(payload, dict):
        result.pop("payload", None)
        if not result["error"]:
            result["error"] = "missing_recovery_evidence"
        return result

    status = str(payload.get("status") or "")
    before_restart = payload.get("before_restart") or {}
    after_restart = payload.get("after_restart") or {}
    before_batch_id = _recovery_plan_batch_id(before_restart)
    after_batch_id = _recovery_plan_batch_id(after_restart)
    before_summary_present = bool(
        isinstance(before_restart, dict) and isinstance(before_restart.get("summary"), dict)
    )
    after_summary_present = bool(
        isinstance(after_restart, dict) and isinstance(after_restart.get("summary"), dict)
    )
    before_batch_id_matches = before_batch_id == expected_batch_id
    after_batch_id_matches = after_batch_id == expected_batch_id
    error = ""
    if status.lower() not in PASS_STATUSES:
        error = "recovery_status_not_completed"
    elif not isinstance(before_restart, dict) or not before_restart:
        error = "missing_before_restart_plan"
    elif not isinstance(after_restart, dict) or not after_restart:
        error = "missing_after_restart_plan"
    elif not before_summary_present:
        error = "missing_before_restart_summary"
    elif not after_summary_present:
        error = "missing_after_restart_summary"
    elif not before_batch_id_matches or not after_batch_id_matches:
        error = "batch_id_mismatch"

    valid = not error
    result.update(
        {
            "valid": valid,
            "error": error,
            "status": status,
            "has_before_restart": isinstance(before_restart, dict) and bool(before_restart),
            "has_after_restart": isinstance(after_restart, dict) and bool(after_restart),
            "before_batch_id": before_batch_id,
            "after_batch_id": after_batch_id,
            "before_batch_id_matches": before_batch_id_matches,
            "after_batch_id_matches": after_batch_id_matches,
            "before_summary_present": before_summary_present,
            "after_summary_present": after_summary_present,
        }
    )
    result.pop("payload", None)
    return result


def _restart_recovery_payload(details: dict[str, Any]) -> dict[str, Any]:
    raw_path = (
        details.get("restart_recovery_report")
        or details.get("recovery_report")
        or details.get("report_path")
        or ""
    )
    if raw_path:
        path = Path(str(raw_path))
        base = {"path": str(path), "exists": path.exists() and path.is_file()}
        if not base["exists"]:
            return {**base, "error": "missing_recovery_report"}
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {**base, "error": "invalid_recovery_report_json"}
        return {**base, "payload": payload}
    if "before_restart" in details or "after_restart" in details:
        return {"payload": details}
    return {"error": "missing_recovery_evidence"}


def _recovery_plan_batch_id(payload: Any) -> str:
    if not isinstance(payload, dict):
        return ""
    return str(payload.get("batch_id") or "")


def refresh_identity_evidence(
    checks: list[dict[str, Any]],
    *,
    run_id: str,
    batch_id: str,
) -> list[dict[str, Any]]:
    return [
        _refreshed_identity_check(check, run_id=run_id, batch_id=batch_id)
        if str(check.get("status") or "").lower() in PASS_STATUSES
        else check
        for check in checks
    ]


def _refreshed_identity_check(
    check: dict[str, Any],
    *,
    run_id: str,
    batch_id: str,
) -> dict[str, Any]:
    check_id = str(check.get("id") or "")
    if check_id == "single_run" and not run_id:
        return _identity_blocker_check(check, "missing run_id for single_run acceptance")
    if check_id in {"batch_run", "restart_recovery", "export"} and not batch_id:
        return _identity_blocker_check(check, f"missing batch_id for {check_id} acceptance")
    return check


def _identity_blocker_check(check: dict[str, Any], evidence: str) -> dict[str, Any]:
    details = check.get("details") if isinstance(check.get("details"), dict) else {}
    return {
        **check,
        "status": "fail",
        "evidence": evidence,
        "details": {
            **details,
            "identity_check": {
                "valid": False,
                "reason": evidence,
            },
        },
    }


def _merge_default_matrix(checks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    existing_ids = {str(check.get("id") or "") for check in checks}
    merged = list(checks)
    for default_check in DEFAULT_ACCEPTANCE_MATRIX:
        if default_check["id"] in existing_ids:
            continue
        merged.append(
            {
                "id": default_check["id"],
                "required_evidence": default_check["required_evidence"],
                "status": "manual_pending",
                "evidence": "",
                "details": {},
            }
        )
    return merged


def _acceptance_status_actions(
    report_path: Path,
    blocking_checks: list[dict[str, Any]],
) -> list[str]:
    actions: list[str] = []
    if not report_path.exists():
        actions.append("run_local_acceptance")
    action_by_check = {
        "full_tests": "run_full_tests",
        "pipeline_schema": "verify_pipeline_schema",
        "local_demo": "run_local_demo",
        "comfyui_dry_smoke": "run_smoke_dry_run",
        "comfyui_real_smoke": "run_real_comfyui_smoke",
        "comfyui_outputs": "check_comfyui_outputs",
        "video_files": "verify_video_files",
        "overall_status": "rerun_local_acceptance",
        "model_check": "configure_and_check_models",
        "run_diagnose": "fix_run_preflight",
        "batch_diagnose": "fix_batch_preflight",
        "single_run": "run_single_end_to_end",
        "batch_run": "run_batch_end_to_end",
        "restart_recovery": "run_restart_recovery_drill",
        "export": "export_and_validate_batch",
        "fresh_setup": "run_fresh_setup_acceptance",
    }
    for check in blocking_checks:
        action = action_by_check.get(str(check.get("id") or ""))
        if action:
            actions.append(action)
    return _dedupe(actions)


def _check_from_smoke_result(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {
            "id": "comfyui_real_smoke",
            "required_evidence": "smoke_result.json, prompt id",
            "status": "fail",
            "evidence": f"missing smoke_result={path}",
        }

    payload = json.loads(path.read_text(encoding="utf-8"))
    prompt_id = str(payload.get("prompt_id") or "")
    ready = bool(payload.get("ready"))
    status = str(payload.get("status") or "")
    artifact_dir = str(payload.get("artifact_dir") or "")
    is_pass = ready and status in {"passed", "pass", "completed"}
    check_id = "comfyui_real_smoke" if prompt_id else "comfyui_dry_smoke"
    evidence_parts = []
    if prompt_id:
        evidence_parts.append(f"prompt_id={prompt_id}")
    evidence_parts.append(f"artifact_dir={artifact_dir}")
    return {
        "id": check_id,
        "required_evidence": "smoke_result.json, prompt id" if prompt_id else "smoke_result.json, no prompt id",
        "status": "pass" if is_pass else "fail",
        "evidence": "; ".join(evidence_parts),
        "details": {
            "source": str(path),
            "ready": ready,
            "status": status,
        },
    }


def _check_from_local_demo_summary(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {
            "id": "local_demo",
            "required_evidence": "local_demo_summary.json, fake model run and batch artifacts",
            "status": "fail",
            "evidence": f"missing local_demo_summary={path}",
            "details": {"source": str(path)},
        }

    payload = json.loads(path.read_text(encoding="utf-8"))
    single_status = str((payload.get("single_run") or {}).get("status") or "")
    batch = payload.get("batch") or {}
    batch_status = str(batch.get("status") or "")
    batch_summary = batch.get("summary") or {}
    batch_total = int(batch_summary.get("total") or 0)
    batch_completed = int(batch_summary.get("completed") or 0)
    restart_recovery = payload.get("restart_recovery") or {}
    restart_recovery_status = str(restart_recovery.get("status") or "")
    external_calls = payload.get("external_calls") or {}
    no_external_calls = (
        str(external_calls.get("model_provider") or "") == "fake"
        and external_calls.get("comfyui") is False
        and external_calls.get("image_generation") is False
    )
    is_pass = (
        str(payload.get("status") or "") == "completed"
        and single_status == "completed"
        and batch_status == "completed"
        and batch_total > 0
        and batch_completed == batch_total
        and restart_recovery_status == "completed"
        and no_external_calls
    )
    return {
        "id": "local_demo",
        "required_evidence": "local_demo_summary.json, fake model run and batch artifacts",
        "status": "pass" if is_pass else "fail",
        "evidence": (
            f"single_run={single_status}; "
            f"batch={batch_status}; "
            f"batch_completed={batch_completed}/{batch_total}; "
            f"restart_recovery={restart_recovery_status}; "
            f"no_external_calls={str(no_external_calls).lower()}"
        ),
        "details": {
            "source": str(path),
            "status": str(payload.get("status") or ""),
            "single_run_status": single_status,
            "batch_status": batch_status,
            "batch_summary": batch_summary,
            "restart_recovery": restart_recovery,
            "external_calls": external_calls,
        },
    }


def _build_summary(report: dict[str, Any]) -> dict[str, Any]:
    by_status = Counter(str(check.get("status") or "manual_pending") for check in report["checks"])
    checks_ready = bool(report["checks"]) and all(
        str(check.get("status") or "").lower() in PASS_STATUSES for check in report["checks"]
    )
    overall_ready = str(report["status"]).lower() in PASS_STATUSES
    return {
        "check_count": len(report["checks"]),
        "by_status": dict(sorted(by_status.items())),
        "ready_for_release": checks_ready and overall_ready,
    }


def _render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Acceptance Report",
        "",
        f"- Generated at: `{report['generated_at']}`",
        f"- Mode: `{_markdown_inline(report['mode'])}`",
        f"- Status: `{_markdown_inline(report['status'])}`",
        f"- Run ID: `{_markdown_inline(report['run_id'])}`",
        f"- Batch ID: `{_markdown_inline(report['batch_id'])}`",
        "",
        "## Checks",
        "",
        "| Check | Required Evidence | Status | Evidence |",
        "| --- | --- | --- | --- |",
    ]
    for check in report["checks"]:
        lines.append(
            "| "
            + " | ".join(
                [
                    _markdown_cell(check.get("id")),
                    _markdown_cell(check.get("required_evidence")),
                    _markdown_cell(check.get("status")),
                    _markdown_cell(check.get("evidence")),
                ]
            )
            + " |"
        )
    lines.extend(["", "## Video Paths", ""])
    if report["video_paths"]:
        lines.extend(f"- `{_markdown_inline(path)}`" for path in report["video_paths"])
    else:
        lines.append("-")
    lines.extend(["", "## Notes", "", str(report["notes"] or ""), ""])
    return "\n".join(lines)


def _string_list(value: Any) -> list[str]:
    if isinstance(value, (str, bytes)):
        return [str(value)]
    return [str(item) for item in value]


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _markdown_cell(value: Any) -> str:
    return str(value or "").replace("|", "\\|").replace("\r\n", "<br>").replace("\n", "<br>")


def _markdown_inline(value: Any) -> str:
    return str(value or "").replace("`", "'")
