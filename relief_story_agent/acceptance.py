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
    checks = refresh_export_evidence(checks)
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
        checks = refresh_export_evidence(checks)
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


def refresh_export_evidence(checks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        _refreshed_export_check(check)
        if str(check.get("id") or "") == "export"
        and str(check.get("status") or "").lower() in PASS_STATUSES
        else check
        for check in checks
    ]


def _refreshed_export_check(check: dict[str, Any]) -> dict[str, Any]:
    details = check.get("details") if isinstance(check.get("details"), dict) else {}
    validation_report = _validation_report_status(details.get("validation_report"))
    zip_validation_report = _validation_report_status(details.get("zip_validation_report"))
    valid = bool(validation_report["valid"] and zip_validation_report["valid"])
    return {
        **check,
        "status": "pass" if valid else "fail",
        "evidence": (
            f"validation_report_valid={str(bool(validation_report['valid'])).lower()}; "
            f"zip_validation_report_valid={str(bool(zip_validation_report['valid'])).lower()}"
        ),
        "details": {
            **details,
            "validation_report": validation_report,
            "zip_validation_report": zip_validation_report,
        },
    }


def _validation_report_status(raw_path: Any) -> dict[str, Any]:
    path_value = _validation_report_path(raw_path)
    result = {
        "path": path_value,
        "exists": False,
        "valid": False,
        "error": "",
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
    return {
        **result,
        "valid": bool(payload.get("valid")),
        "reported_valid": bool(payload.get("valid")),
    }


def _validation_report_path(raw_path: Any) -> str:
    if isinstance(raw_path, dict):
        return str(raw_path.get("path") or "")
    return str(raw_path or "")


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
