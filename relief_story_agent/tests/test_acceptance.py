from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from relief_story_agent.acceptance import (
    DEFAULT_ACCEPTANCE_MATRIX,
    build_acceptance_status,
    write_acceptance_report,
)


def _mp4_box(kind: bytes, payload: bytes = b"") -> bytes:
    return (len(payload) + 8).to_bytes(4, "big") + kind + payload


def _valid_mp4_bytes() -> bytes:
    return _mp4_box(b"ftyp", b"isom\x00\x00\x02\x00isomiso2") + _mp4_box(b"moov", b"\x00")


def _valid_export_report_paths(tmp_path: Path) -> tuple[Path, Path]:
    validation_report = tmp_path / "exports" / "batch_real" / "validation_report.json"
    validation_report.parent.mkdir(parents=True)
    validation_report.write_text(json.dumps({"valid": True, "batch_id": "batch_real"}), encoding="utf-8")
    zip_validation_report = tmp_path / "exports" / "batch_real.zip.validation.json"
    zip_validation_report.write_text(json.dumps({"valid": True, "batch_id": "batch_real"}), encoding="utf-8")
    return validation_report, zip_validation_report


def _valid_restart_recovery_report_path(tmp_path: Path, *, batch_id: str = "batch_real") -> Path:
    recovery_report = tmp_path / "recovery" / f"{batch_id}_restart_recovery.json"
    recovery_report.parent.mkdir(parents=True)
    recovery_report.write_text(
        json.dumps(
            {
                "status": "completed",
                "before_restart": {
                    "batch_id": batch_id,
                    "summary": {"total_items": 1, "auto_retryable_count": 1},
                    "items": [{"run_id": "run_retry", "safe_to_auto_execute": True}],
                },
                "after_restart": {
                    "batch_id": batch_id,
                    "summary": {"total_items": 1, "auto_retryable_count": 1},
                    "items": [{"run_id": "run_retry", "safe_to_auto_execute": True}],
                },
            }
        ),
        encoding="utf-8",
    )
    return recovery_report


def _model_check_report_path(tmp_path: Path, *, real_run: bool = True, include_image: bool = True) -> Path:
    checks = [
        {"profile": "gemini_writer", "status": "pass", "real_run": real_run},
        {"profile": "deepseek_editor", "status": "pass", "real_run": real_run},
        {"profile": "gpt_visual", "status": "pass", "real_run": real_run},
    ]
    if include_image:
        checks.append({"profile": "image_provider", "status": "pass", "real_run": real_run})
    model_check_report = tmp_path / "model_check" / "model_check.json"
    model_check_report.parent.mkdir(parents=True, exist_ok=True)
    model_check_report.write_text(
        json.dumps({"real_run": real_run, "ready": True, "checks": checks}),
        encoding="utf-8",
    )
    return model_check_report


def _diagnose_report_path(tmp_path: Path, *, kind: str, ready: bool = True) -> Path:
    diagnose_report = tmp_path / "diagnose" / f"{kind}_diagnose.json"
    diagnose_report.parent.mkdir(parents=True, exist_ok=True)
    diagnose_report.write_text(json.dumps({"kind": kind, "ready": ready}), encoding="utf-8")
    return diagnose_report


def _pipeline_schema_report_path(
    tmp_path: Path,
    *,
    stage_order: list[str] | None = None,
) -> Path:
    pipeline_schema_report = tmp_path / "pipeline" / "pipeline_schema.json"
    pipeline_schema_report.parent.mkdir(parents=True, exist_ok=True)
    pipeline_schema_report.write_text(
        json.dumps(
            {
                "canonical_stage_order": stage_order
                or [
                    "chief_screenwriter",
                    "deepseek_polish",
                    "quality_gate",
                    "gpt_prompt_writer",
                    "gpt_prompt_audit",
                    "gpt_prompt_reviser",
                    "final_prompts",
                    "four_grid_asset",
                    "artifacts",
                    "comfyui",
                ],
                "invariants": {
                    "fixed_order": True,
                    "prompt_reviser_max_auto_attempts": 1,
                    "quality_gate_after": "deepseek_polish",
                    "comfyui_workflow_generation": "never",
                },
            }
        ),
        encoding="utf-8",
    )
    return pipeline_schema_report


def _pytest_stdout_path(tmp_path: Path, content: str = "414 passed in 71.02s\n") -> Path:
    pytest_stdout = tmp_path / "tests" / "pytest.stdout.txt"
    pytest_stdout.parent.mkdir(parents=True, exist_ok=True)
    pytest_stdout.write_text(content, encoding="utf-8")
    return pytest_stdout


def _valid_recovery_plan_path(tmp_path: Path, name: str, *, batch_id: str = "batch_real") -> Path:
    recovery_plan = tmp_path / "recovery" / name
    recovery_plan.parent.mkdir(parents=True, exist_ok=True)
    recovery_plan.write_text(
        json.dumps(
            {
                "batch_id": batch_id,
                "summary": {"total_items": 1, "auto_retryable_count": 1},
                "items": [{"run_id": "run_retry", "safe_to_auto_execute": True}],
            }
        ),
        encoding="utf-8",
    )
    return recovery_plan


def _valid_batch_artifacts_report_path(tmp_path: Path, *, batch_id: str = "batch_real") -> Path:
    ready_video = tmp_path / "batch" / "run_ready" / "output.mp4"
    ready_video.parent.mkdir(parents=True, exist_ok=True)
    ready_video.write_bytes(_valid_mp4_bytes())
    batch_report = tmp_path / "batch" / f"{batch_id}_artifacts.json"
    batch_report.parent.mkdir(parents=True, exist_ok=True)
    batch_report.write_text(
        json.dumps(
            {
                "batch_id": batch_id,
                "status": "partial_failed",
                "publish_ready_count": 1,
                "audit_summary": {
                    "total_items": 2,
                    "publish_ready_count": 1,
                    "failed_count": 1,
                },
                "items": [
                    {
                        "run_id": "run_ready",
                        "status": "completed",
                        "publish_ready": True,
                        "primary_video_path": str(ready_video),
                        "recommended_action": {"code": "publish"},
                    },
                    {
                        "run_id": "run_failed",
                        "status": "failed",
                        "failed_stage": "gpt_prompt_audit",
                        "publish_ready": False,
                        "recommended_action": {"code": "manual_review_prompt_audit"},
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    return batch_report


def _batch_artifacts_report_path_with_missing_publish_video(tmp_path: Path) -> Path:
    batch_report = _valid_batch_artifacts_report_path(tmp_path)
    payload = json.loads(batch_report.read_text(encoding="utf-8"))
    payload["items"][0]["primary_video_path"] = str(tmp_path / "missing" / "output.mp4")
    batch_report.write_text(json.dumps(payload), encoding="utf-8")
    return batch_report


def _batch_artifacts_report_path_with_failed_publish_ready_item(tmp_path: Path) -> Path:
    batch_report = _valid_batch_artifacts_report_path(tmp_path)
    payload = json.loads(batch_report.read_text(encoding="utf-8"))
    payload["items"][0]["status"] = "failed"
    payload["items"][0]["failed_stage"] = "comfyui"
    batch_report.write_text(json.dumps(payload), encoding="utf-8")
    return batch_report


def _comfyui_outputs_details(video_path: Path) -> dict[str, object]:
    return {
        "status": "ready",
        "ready": True,
        "video_count": 1,
        "downloaded_count": 1,
        "actual_outputs": [
            {
                "prompt_id": "prompt_video",
                "node_id": "10",
                "filename": video_path.name,
                "subfolder": "",
                "type": "output",
                "media_type": "video",
                "local_path": str(video_path),
            }
        ],
    }


def _passing_release_checks(
    *,
    validation_report: Path,
    zip_validation_report: Path,
    batch_artifacts_report: Path | None = None,
    restart_recovery_report: Path | None = None,
    comfyui_output_video: Path | None = None,
    model_check_report: Path | None = None,
    run_diagnose_report: Path | None = None,
    batch_diagnose_report: Path | None = None,
    pipeline_schema_report: Path | None = None,
    pytest_stdout: Path | None = None,
) -> list[dict[str, object]]:
    if comfyui_output_video is None:
        comfyui_output_video = validation_report.parent / "comfyui_output.mp4"
        comfyui_output_video.write_bytes(_valid_mp4_bytes())
    if model_check_report is None:
        model_check_report = _model_check_report_path(validation_report.parent)
    if run_diagnose_report is None:
        run_diagnose_report = _diagnose_report_path(validation_report.parent, kind="run")
    if batch_diagnose_report is None:
        batch_diagnose_report = _diagnose_report_path(validation_report.parent, kind="batch")
    if pipeline_schema_report is None:
        pipeline_schema_report = _pipeline_schema_report_path(validation_report.parent)
    if pytest_stdout is None:
        pytest_stdout = _pytest_stdout_path(validation_report.parent)
    checks = []
    for default_check in DEFAULT_ACCEPTANCE_MATRIX:
        check: dict[str, object] = {
            "id": default_check["id"],
            "status": "pass",
            "required_evidence": default_check["required_evidence"],
            "evidence": "verified",
        }
        if default_check["id"] == "comfyui_outputs":
            check["details"] = _comfyui_outputs_details(comfyui_output_video)
        if default_check["id"] == "model_check":
            check["details"] = {
                "model_check_report": str(model_check_report),
            }
        if default_check["id"] == "run_diagnose":
            check["details"] = {
                "diagnose_report": str(run_diagnose_report),
            }
        if default_check["id"] == "batch_diagnose":
            check["details"] = {
                "diagnose_report": str(batch_diagnose_report),
            }
        if default_check["id"] == "pipeline_schema":
            check["details"] = {
                "pipeline_schema_report": str(pipeline_schema_report),
            }
        if default_check["id"] == "full_tests":
            check["details"] = {
                "stdout_path": str(pytest_stdout),
                "exit_code": 0,
            }
        if default_check["id"] == "export":
            check["details"] = {
                "validation_report": str(validation_report),
                "zip_validation_report": str(zip_validation_report),
            }
        if default_check["id"] == "batch_run" and batch_artifacts_report:
            check["details"] = {
                "batch_artifacts_report": str(batch_artifacts_report),
            }
        if default_check["id"] == "restart_recovery" and restart_recovery_report:
            check["details"] = {
                "restart_recovery_report": str(restart_recovery_report),
            }
        checks.append(check)
    return checks


def test_write_acceptance_report_records_matrix_and_markdown(tmp_path):
    report_path = write_acceptance_report(
        tmp_path,
        {
            "run_id": "run_demo",
            "batch_id": "batch_demo",
            "mode": "single_run",
            "status": "completed",
            "video_paths": ["D:/relief_story_runs/run_demo/output.mp4"],
            "checks": [
                {
                    "id": "full_tests",
                    "status": "pass",
                    "required_evidence": "python -m pytest relief_story_agent/tests -q",
                    "evidence": "238 passed",
                },
                {
                    "id": "comfyui_real_smoke",
                    "status": "manual_pending",
                    "required_evidence": "smoke_result.json, prompt id",
                    "evidence": "",
                },
            ],
            "notes": "local acceptance demo",
        },
    )

    report = json.loads(Path(report_path).read_text(encoding="utf-8"))

    assert report["mode"] == "single_run"
    assert report["status"] == "completed"
    assert report["run_id"] == "run_demo"
    assert report["batch_id"] == "batch_demo"
    assert report["video_paths"] == ["D:/relief_story_runs/run_demo/output.mp4"]
    assert report["checks"][0]["id"] == "full_tests"
    assert report["checks"][0]["status"] == "fail"
    assert report["checks"][0]["details"]["full_tests_evidence"]["error"] == "missing_pytest_stdout"
    assert report["summary"]["check_count"] == 15
    assert "pass" not in report["summary"]["by_status"]
    assert report["summary"]["by_status"]["manual_pending"] == 13
    assert report["summary"]["by_status"]["fail"] == 2
    assert report["summary"]["ready_for_release"] is False

    markdown = (tmp_path / "ACCEPTANCE_REPORT.md").read_text(encoding="utf-8")
    assert "| full_tests | python -m pytest relief_story_agent/tests -q | fail | full_tests_valid=false; exit_code=None; passed=0; failed=0; errors=0 |" in markdown
    assert "| comfyui_real_smoke | smoke_result.json, prompt id | manual_pending |  |" in markdown


def test_write_acceptance_report_marks_missing_video_path_failed(tmp_path):
    missing_video = tmp_path / "missing.mp4"

    report_path = write_acceptance_report(
        tmp_path,
        {
            "mode": "single_run",
            "status": "completed",
            "video_paths": [str(missing_video)],
        },
    )

    report = json.loads(Path(report_path).read_text(encoding="utf-8"))
    video_check = next(check for check in report["checks"] if check["id"] == "video_files")

    assert video_check["status"] == "fail"
    assert video_check["required_evidence"] == "local video files exist, are non-empty, and are openable"
    assert video_check["details"]["videos"] == [
        {"path": str(missing_video), "exists": False, "size_bytes": 0, "openable": False, "valid": False}
    ]
    assert report["summary"]["ready_for_release"] is False


def test_write_acceptance_report_rejects_unopenable_video_file(tmp_path):
    bad_video = tmp_path / "bad.mp4"
    bad_video.write_bytes(b"not an mp4 video")

    report_path = write_acceptance_report(
        tmp_path,
        {
            "mode": "single_run",
            "status": "completed",
            "video_paths": [str(bad_video)],
        },
    )

    report = json.loads(Path(report_path).read_text(encoding="utf-8"))
    video_check = next(check for check in report["checks"] if check["id"] == "video_files")

    assert video_check["status"] == "fail"
    assert video_check["details"]["videos"][0]["exists"] is True
    assert video_check["details"]["videos"][0]["size_bytes"] == len(b"not an mp4 video")
    assert video_check["details"]["videos"][0]["openable"] is False
    assert video_check["details"]["videos"][0]["valid"] is False


def test_write_acceptance_report_requires_video_path_for_single_run_pass(tmp_path):
    report_path = write_acceptance_report(
        tmp_path,
        {
            "mode": "single_run",
            "status": "completed",
            "checks": [
                {
                    "id": "single_run",
                    "status": "pass",
                    "required_evidence": "run artifact dir, openable downloaded video path",
                    "evidence": "run completed",
                }
            ],
        },
    )

    report = json.loads(Path(report_path).read_text(encoding="utf-8"))
    checks = {check["id"]: check for check in report["checks"]}

    assert checks["video_files"]["status"] == "fail"
    assert checks["video_files"]["evidence"] == "missing video_paths for single_run acceptance"
    assert report["summary"]["ready_for_release"] is False


def test_write_acceptance_report_can_collect_smoke_result(tmp_path):
    smoke_result_path = tmp_path / "smoke_result.json"
    smoke_result_path.write_text(
        json.dumps(
            {
                "status": "passed",
                "ready": True,
                "prompt_id": "prompt-abc",
                "artifact_dir": "D:/relief_story_smoke/smoke_demo",
            }
        ),
        encoding="utf-8",
    )

    report_path = write_acceptance_report(
        tmp_path / "report",
        {
            "mode": "smoke",
            "status": "completed",
            "sources": {"smoke_result": str(smoke_result_path)},
        },
    )
    report = json.loads(Path(report_path).read_text(encoding="utf-8"))

    smoke_check = next(check for check in report["checks"] if check["id"] == "comfyui_real_smoke")
    assert smoke_check["status"] == "pass"
    assert smoke_check["evidence"] == "prompt_id=prompt-abc; artifact_dir=D:/relief_story_smoke/smoke_demo"
    check_ids = {check["id"] for check in report["checks"]}
    assert "full_tests" in check_ids
    assert "single_run" in check_ids
    assert report["summary"]["ready_for_release"] is False
    assert report["summary"]["check_count"] == 14
    assert report["summary"]["by_status"]["manual_pending"] == 13


def test_write_acceptance_report_can_collect_local_demo_summary(tmp_path):
    summary_path = tmp_path / "local_demo_summary.json"
    summary_path.write_text(
        json.dumps(
            {
                "status": "completed",
                "single_run": {"status": "completed", "artifact_dir": "D:/demo/run_demo"},
                "batch": {
                    "status": "completed",
                    "summary": {"total": 2, "completed": 2},
                },
                "external_calls": {
                    "model_provider": "fake",
                    "comfyui": False,
                    "image_generation": False,
                },
                "restart_recovery": {
                    "status": "completed",
                },
            }
        ),
        encoding="utf-8",
    )

    report_path = write_acceptance_report(
        tmp_path / "report",
        {
            "mode": "offline_demo",
            "status": "completed",
            "sources": {"local_demo_summary": str(summary_path)},
        },
    )
    report = json.loads(Path(report_path).read_text(encoding="utf-8"))

    demo_check = next(check for check in report["checks"] if check["id"] == "local_demo")
    assert demo_check["status"] == "pass"
    assert demo_check["evidence"] == "single_run=completed; batch=completed; batch_completed=2/2; restart_recovery=completed; no_external_calls=true"
    assert demo_check["details"]["source"] == str(summary_path)


def test_write_acceptance_report_can_include_default_matrix(tmp_path):
    report_path = write_acceptance_report(
        tmp_path,
        {
            "mode": "local_e2e",
            "status": "manual_pending",
            "include_default_matrix": True,
        },
    )

    report = json.loads(Path(report_path).read_text(encoding="utf-8"))
    check_ids = [check["id"] for check in report["checks"]]

    assert "full_tests" in check_ids
    assert "local_demo" in check_ids
    assert "pipeline_schema" in check_ids
    assert "model_check" in check_ids
    assert "run_diagnose" in check_ids
    assert "batch_diagnose" in check_ids
    assert "restart_recovery" in check_ids
    assert "fresh_setup" in check_ids
    assert all(check["status"] == "manual_pending" for check in report["checks"])


def test_build_acceptance_status_reports_missing_report_with_default_matrix(tmp_path):
    report_path = tmp_path / "missing" / "acceptance_report.json"

    status = build_acceptance_status(report_path)

    assert status["exists"] is False
    assert status["ready_for_release"] is False
    assert status["summary"]["check_count"] == 14
    assert status["blocking_checks"][0]["id"] == "full_tests"
    assert status["suggested_actions"][0] == "run_local_acceptance"


def test_build_acceptance_status_requires_full_release_matrix_for_partial_report(tmp_path):
    smoke_result_path = tmp_path / "smoke_result.json"
    smoke_result_path.write_text(
        json.dumps(
            {
                "status": "passed",
                "ready": True,
                "prompt_id": "prompt-abc",
                "artifact_dir": "D:/relief_story_smoke/smoke_demo",
            }
        ),
        encoding="utf-8",
    )
    report_path = write_acceptance_report(
        tmp_path / "report",
        {
            "mode": "smoke",
            "status": "completed",
            "sources": {"smoke_result": str(smoke_result_path)},
        },
    )

    status = build_acceptance_status(report_path)

    blocking_ids = [check["id"] for check in status["blocking_checks"]]
    assert status["ready_for_release"] is False
    assert status["summary"]["check_count"] == 14
    assert "comfyui_real_smoke" not in blocking_ids
    assert "full_tests" in blocking_ids
    assert "single_run" in blocking_ids
    assert "run_full_tests" in status["suggested_actions"]


def test_build_acceptance_status_lists_blocking_checks_from_existing_report(tmp_path):
    report_path = write_acceptance_report(
        tmp_path,
        {
            "mode": "local_e2e",
            "status": "completed",
            "checks": [
                {
                    "id": "full_tests",
                    "status": "pass",
                    "required_evidence": "pytest output",
                    "evidence": "353 passed",
                },
                {
                    "id": "comfyui_real_smoke",
                    "status": "manual_pending",
                    "required_evidence": "smoke_result.json, prompt id",
                    "evidence": "",
                },
                {
                    "id": "single_run",
                    "status": "fail",
                    "required_evidence": "downloaded video path",
                    "evidence": "missing video",
                },
            ],
        },
    )

    status = build_acceptance_status(report_path)

    assert status["exists"] is True
    assert status["ready_for_release"] is False
    blocking_ids = [check["id"] for check in status["blocking_checks"]]
    assert blocking_ids[:3] == ["full_tests", "comfyui_real_smoke", "single_run"]
    assert "local_demo" in blocking_ids
    assert "export" in blocking_ids
    assert "run_full_tests" in status["suggested_actions"]
    assert "run_real_comfyui_smoke" in status["suggested_actions"]
    assert "run_single_end_to_end" in status["suggested_actions"]
    assert "run_local_demo" in status["suggested_actions"]


def test_build_acceptance_status_does_not_trust_stale_ready_summary(tmp_path):
    report_path = tmp_path / "acceptance_report.json"
    report_path.write_text(
        json.dumps(
            {
                "status": "completed",
                "checks": [
                    {"id": "full_tests", "status": "pass"},
                    {"id": "export", "status": "manual_pending"},
                ],
                "summary": {"ready_for_release": True, "check_count": 2},
            }
        ),
        encoding="utf-8",
    )

    status = build_acceptance_status(report_path)

    assert status["ready_for_release"] is False
    assert status["summary"]["blocking_count"] == 14
    assert status["summary"]["check_count"] == 14


def test_build_acceptance_status_reports_failed_overall_status_as_blocker(tmp_path):
    video_path = tmp_path / "complete.webm"
    video_path.write_bytes(b"\x1a\x45\xdf\xa3\x42\x82\x84webm\x00")
    report_path = write_acceptance_report(
        tmp_path,
        {
            "mode": "local_acceptance",
            "status": "failed",
            "video_paths": [str(video_path)],
            "checks": [
                {
                    "id": default_check["id"],
                    "status": "pass",
                    "required_evidence": default_check["required_evidence"],
                    "evidence": "verified",
                }
                for default_check in DEFAULT_ACCEPTANCE_MATRIX
            ],
        },
    )

    status = build_acceptance_status(report_path)

    assert status["ready_for_release"] is False
    assert status["blocking_checks"][0]["id"] == "overall_status"
    assert status["blocking_checks"][0]["status"] == "fail"
    assert status["blocking_checks"][0]["evidence"] == "status=failed"
    assert "rerun_local_acceptance" in status["suggested_actions"]


def test_build_acceptance_status_revalidates_stale_export_validation_reports(tmp_path):
    video_path = tmp_path / "complete.mp4"
    video_path.write_bytes(_valid_mp4_bytes())
    missing_export_report = tmp_path / "exports" / "batch_missing" / "validation_report.json"
    _, zip_validation_report = _valid_export_report_paths(tmp_path)
    checks = [
        {
            "id": default_check["id"],
            "status": "pass",
            "required_evidence": default_check["required_evidence"],
            "evidence": "verified",
        }
        for default_check in DEFAULT_ACCEPTANCE_MATRIX
        if default_check["id"] != "export"
    ]
    checks.append(
        {
            "id": "export",
            "status": "pass",
            "required_evidence": "publish index, zip, sha256",
            "evidence": "export_dir=D:/exports/batch_real; valid=true",
            "details": {
                "validation_report": str(missing_export_report),
                "zip_validation_report": str(zip_validation_report),
            },
        }
    )
    report_path = write_acceptance_report(
        tmp_path,
        {
            "run_id": "run_real",
            "batch_id": "batch_real",
            "mode": "local_acceptance",
            "status": "completed",
            "video_paths": [str(video_path)],
            "checks": checks,
        },
    )

    status = build_acceptance_status(report_path)

    export_check = next(check for check in status["blocking_checks"] if check["id"] == "export")
    assert status["ready_for_release"] is False
    assert export_check["status"] == "fail"
    assert export_check["details"]["validation_report"]["exists"] is False
    assert "export_and_validate_batch" in status["suggested_actions"]


def test_build_acceptance_status_blocks_export_report_for_different_batch(tmp_path):
    video_path = tmp_path / "complete.mp4"
    video_path.write_bytes(_valid_mp4_bytes())
    validation_report, zip_validation_report = _valid_export_report_paths(tmp_path)
    validation_report.write_text(
        json.dumps(
            {
                "valid": True,
                "batch_id": "batch_other",
                "export_dir": str(tmp_path / "exports" / "batch_other"),
            }
        ),
        encoding="utf-8",
    )
    report_path = write_acceptance_report(
        tmp_path,
        {
            "run_id": "run_real",
            "batch_id": "batch_real",
            "mode": "local_acceptance",
            "status": "completed",
            "video_paths": [str(video_path)],
            "checks": _passing_release_checks(
                validation_report=validation_report,
                zip_validation_report=zip_validation_report,
            ),
        },
    )

    status = build_acceptance_status(report_path)

    export_check = next(check for check in status["blocking_checks"] if check["id"] == "export")
    assert status["ready_for_release"] is False
    assert export_check["status"] == "fail"
    assert export_check["details"]["validation_report"]["expected_batch_id"] == "batch_real"
    assert export_check["details"]["validation_report"]["reported_batch_id"] == "batch_other"
    assert export_check["details"]["validation_report"]["batch_id_matches"] is False


def test_build_acceptance_status_blocks_export_report_without_explicit_batch_id(tmp_path):
    video_path = tmp_path / "complete.mp4"
    video_path.write_bytes(_valid_mp4_bytes())
    validation_report, zip_validation_report = _valid_export_report_paths(tmp_path)
    validation_report.write_text(json.dumps({"valid": True}), encoding="utf-8")
    zip_validation_report.write_text(json.dumps({"valid": True}), encoding="utf-8")
    report_path = write_acceptance_report(
        tmp_path,
        {
            "run_id": "run_real",
            "batch_id": "batch_real",
            "mode": "local_acceptance",
            "status": "completed",
            "video_paths": [str(video_path)],
            "checks": _passing_release_checks(
                validation_report=validation_report,
                zip_validation_report=zip_validation_report,
            ),
        },
    )

    status = build_acceptance_status(report_path)

    export_check = next(check for check in status["blocking_checks"] if check["id"] == "export")
    assert status["ready_for_release"] is False
    assert export_check["status"] == "fail"
    assert export_check["details"]["validation_report"]["error"] == "missing_report_batch_id"
    assert export_check["details"]["zip_validation_report"]["error"] == "missing_report_batch_id"


def test_build_acceptance_status_blocks_restart_recovery_pass_without_structured_evidence(tmp_path):
    video_path = tmp_path / "complete.mp4"
    video_path.write_bytes(_valid_mp4_bytes())
    validation_report, zip_validation_report = _valid_export_report_paths(tmp_path)
    report_path = write_acceptance_report(
        tmp_path,
        {
            "run_id": "run_real",
            "batch_id": "batch_real",
            "mode": "local_acceptance",
            "status": "completed",
            "video_paths": [str(video_path)],
            "checks": _passing_release_checks(
                validation_report=validation_report,
                zip_validation_report=zip_validation_report,
            ),
        },
    )

    status = build_acceptance_status(report_path)

    restart_check = next(
        check for check in status["blocking_checks"] if check["id"] == "restart_recovery"
    )
    assert status["ready_for_release"] is False
    assert restart_check["status"] == "fail"
    assert restart_check["details"]["recovery_evidence"]["valid"] is False
    assert restart_check["details"]["recovery_evidence"]["error"] == "missing_recovery_evidence"
    assert "run_restart_recovery_drill" in status["suggested_actions"]


def test_build_acceptance_status_accepts_restart_recovery_report_for_same_batch(tmp_path):
    video_path = tmp_path / "complete.mp4"
    video_path.write_bytes(_valid_mp4_bytes())
    validation_report, zip_validation_report = _valid_export_report_paths(tmp_path)
    batch_artifacts_report = _valid_batch_artifacts_report_path(tmp_path)
    restart_recovery_report = _valid_restart_recovery_report_path(tmp_path)
    report_path = write_acceptance_report(
        tmp_path,
        {
            "run_id": "run_real",
            "batch_id": "batch_real",
            "mode": "local_acceptance",
            "status": "completed",
            "video_paths": [str(video_path)],
            "checks": _passing_release_checks(
                validation_report=validation_report,
                zip_validation_report=zip_validation_report,
                batch_artifacts_report=batch_artifacts_report,
                restart_recovery_report=restart_recovery_report,
            ),
        },
    )

    status = build_acceptance_status(report_path)
    report = json.loads(Path(report_path).read_text(encoding="utf-8"))
    restart_check = next(
        check for check in report["checks"] if check["id"] == "restart_recovery"
    )

    assert status["ready_for_release"] is True
    assert restart_check["status"] == "pass"
    assert restart_check["details"]["recovery_evidence"]["valid"] is True
    assert restart_check["details"]["recovery_evidence"]["before_batch_id"] == "batch_real"
    assert restart_check["details"]["recovery_evidence"]["after_batch_id"] == "batch_real"


def test_build_acceptance_status_blocks_batch_run_pass_without_structured_evidence(tmp_path):
    video_path = tmp_path / "complete.mp4"
    video_path.write_bytes(_valid_mp4_bytes())
    validation_report, zip_validation_report = _valid_export_report_paths(tmp_path)
    restart_recovery_report = _valid_restart_recovery_report_path(tmp_path)
    report_path = write_acceptance_report(
        tmp_path,
        {
            "run_id": "run_real",
            "batch_id": "batch_real",
            "mode": "local_acceptance",
            "status": "completed",
            "video_paths": [str(video_path)],
            "checks": _passing_release_checks(
                validation_report=validation_report,
                zip_validation_report=zip_validation_report,
                restart_recovery_report=restart_recovery_report,
            ),
        },
    )

    status = build_acceptance_status(report_path)

    batch_check = next(check for check in status["blocking_checks"] if check["id"] == "batch_run")
    assert status["ready_for_release"] is False
    assert batch_check["status"] == "fail"
    assert batch_check["details"]["batch_evidence"]["valid"] is False
    assert batch_check["details"]["batch_evidence"]["error"] == "missing_batch_evidence"
    assert "run_batch_end_to_end" in status["suggested_actions"]


def test_build_acceptance_status_accepts_batch_artifacts_report_for_same_batch(tmp_path):
    video_path = tmp_path / "complete.mp4"
    video_path.write_bytes(_valid_mp4_bytes())
    validation_report, zip_validation_report = _valid_export_report_paths(tmp_path)
    batch_artifacts_report = _valid_batch_artifacts_report_path(tmp_path)
    restart_recovery_report = _valid_restart_recovery_report_path(tmp_path)
    report_path = write_acceptance_report(
        tmp_path,
        {
            "run_id": "run_real",
            "batch_id": "batch_real",
            "mode": "local_acceptance",
            "status": "completed",
            "video_paths": [str(video_path)],
            "checks": _passing_release_checks(
                validation_report=validation_report,
                zip_validation_report=zip_validation_report,
                batch_artifacts_report=batch_artifacts_report,
                restart_recovery_report=restart_recovery_report,
            ),
        },
    )

    status = build_acceptance_status(report_path)
    report = json.loads(Path(report_path).read_text(encoding="utf-8"))
    batch_check = next(check for check in report["checks"] if check["id"] == "batch_run")

    assert status["ready_for_release"] is True
    assert batch_check["status"] == "pass"
    assert batch_check["details"]["batch_evidence"]["valid"] is True
    assert batch_check["details"]["batch_evidence"]["reported_batch_id"] == "batch_real"
    assert batch_check["details"]["batch_evidence"]["item_count"] == 2
    assert batch_check["details"]["batch_evidence"]["publish_ready_count"] == 1


def test_build_acceptance_status_blocks_batch_artifacts_with_missing_publish_video(tmp_path):
    video_path = tmp_path / "complete.mp4"
    video_path.write_bytes(_valid_mp4_bytes())
    validation_report, zip_validation_report = _valid_export_report_paths(tmp_path)
    batch_artifacts_report = _batch_artifacts_report_path_with_missing_publish_video(tmp_path)
    restart_recovery_report = _valid_restart_recovery_report_path(tmp_path)
    report_path = write_acceptance_report(
        tmp_path,
        {
            "run_id": "run_real",
            "batch_id": "batch_real",
            "mode": "local_acceptance",
            "status": "completed",
            "video_paths": [str(video_path)],
            "checks": _passing_release_checks(
                validation_report=validation_report,
                zip_validation_report=zip_validation_report,
                batch_artifacts_report=batch_artifacts_report,
                restart_recovery_report=restart_recovery_report,
            ),
        },
    )

    status = build_acceptance_status(report_path)

    batch_check = next(check for check in status["blocking_checks"] if check["id"] == "batch_run")
    assert status["ready_for_release"] is False
    assert batch_check["status"] == "fail"
    assert batch_check["details"]["batch_evidence"]["error"] == "invalid_batch_items"
    assert batch_check["details"]["batch_evidence"]["invalid_items"][0]["reason"] == "publish_ready_invalid_video"


def test_build_acceptance_status_blocks_failed_publish_ready_batch_item(tmp_path):
    video_path = tmp_path / "complete.mp4"
    video_path.write_bytes(_valid_mp4_bytes())
    validation_report, zip_validation_report = _valid_export_report_paths(tmp_path)
    batch_artifacts_report = _batch_artifacts_report_path_with_failed_publish_ready_item(tmp_path)
    restart_recovery_report = _valid_restart_recovery_report_path(tmp_path)
    report_path = write_acceptance_report(
        tmp_path,
        {
            "run_id": "run_real",
            "batch_id": "batch_real",
            "mode": "local_acceptance",
            "status": "completed",
            "video_paths": [str(video_path)],
            "checks": _passing_release_checks(
                validation_report=validation_report,
                zip_validation_report=zip_validation_report,
                batch_artifacts_report=batch_artifacts_report,
                restart_recovery_report=restart_recovery_report,
            ),
        },
    )

    status = build_acceptance_status(report_path)

    batch_check = next(check for check in status["blocking_checks"] if check["id"] == "batch_run")
    assert status["ready_for_release"] is False
    assert batch_check["status"] == "fail"
    assert batch_check["details"]["batch_evidence"]["error"] == "invalid_batch_items"
    assert batch_check["details"]["batch_evidence"]["invalid_items"][0]["reason"] == "publish_ready_status_not_completed"


def test_build_acceptance_status_blocks_comfyui_outputs_with_missing_downloaded_video(tmp_path):
    video_path = tmp_path / "complete.mp4"
    video_path.write_bytes(_valid_mp4_bytes())
    missing_comfyui_video = tmp_path / "missing" / "comfyui_output.mp4"
    validation_report, zip_validation_report = _valid_export_report_paths(tmp_path)
    batch_artifacts_report = _valid_batch_artifacts_report_path(tmp_path)
    restart_recovery_report = _valid_restart_recovery_report_path(tmp_path)
    report_path = write_acceptance_report(
        tmp_path,
        {
            "run_id": "run_real",
            "batch_id": "batch_real",
            "mode": "local_acceptance",
            "status": "completed",
            "video_paths": [str(video_path)],
            "checks": _passing_release_checks(
                validation_report=validation_report,
                zip_validation_report=zip_validation_report,
                batch_artifacts_report=batch_artifacts_report,
                restart_recovery_report=restart_recovery_report,
                comfyui_output_video=missing_comfyui_video,
            ),
        },
    )

    status = build_acceptance_status(report_path)

    comfyui_check = next(check for check in status["blocking_checks"] if check["id"] == "comfyui_outputs")
    assert status["ready_for_release"] is False
    assert comfyui_check["status"] == "fail"
    assert comfyui_check["details"]["comfyui_outputs_evidence"]["valid"] is False
    assert comfyui_check["details"]["comfyui_outputs_evidence"]["error"] == "invalid_downloaded_videos"
    assert comfyui_check["details"]["comfyui_outputs_evidence"]["video_file_checks"][0]["exists"] is False
    assert "check_comfyui_outputs" in status["suggested_actions"]


def test_build_acceptance_status_blocks_model_check_without_real_run(tmp_path):
    video_path = tmp_path / "complete.mp4"
    video_path.write_bytes(_valid_mp4_bytes())
    validation_report, zip_validation_report = _valid_export_report_paths(tmp_path)
    batch_artifacts_report = _valid_batch_artifacts_report_path(tmp_path)
    restart_recovery_report = _valid_restart_recovery_report_path(tmp_path)
    model_check_report = _model_check_report_path(tmp_path, real_run=False)
    report_path = write_acceptance_report(
        tmp_path,
        {
            "run_id": "run_real",
            "batch_id": "batch_real",
            "mode": "local_acceptance",
            "status": "completed",
            "video_paths": [str(video_path)],
            "checks": _passing_release_checks(
                validation_report=validation_report,
                zip_validation_report=zip_validation_report,
                batch_artifacts_report=batch_artifacts_report,
                restart_recovery_report=restart_recovery_report,
                model_check_report=model_check_report,
            ),
        },
    )

    status = build_acceptance_status(report_path)

    model_check = next(check for check in status["blocking_checks"] if check["id"] == "model_check")
    assert status["ready_for_release"] is False
    assert model_check["status"] == "fail"
    assert model_check["details"]["model_check_evidence"]["valid"] is False
    assert model_check["details"]["model_check_evidence"]["error"] == "model_check_not_real_run"
    assert "configure_and_check_models" in status["suggested_actions"]


def test_build_acceptance_status_blocks_model_check_without_image_provider_probe(tmp_path):
    video_path = tmp_path / "complete.mp4"
    video_path.write_bytes(_valid_mp4_bytes())
    validation_report, zip_validation_report = _valid_export_report_paths(tmp_path)
    batch_artifacts_report = _valid_batch_artifacts_report_path(tmp_path)
    restart_recovery_report = _valid_restart_recovery_report_path(tmp_path)
    model_check_report = _model_check_report_path(tmp_path, real_run=True, include_image=False)
    report_path = write_acceptance_report(
        tmp_path,
        {
            "run_id": "run_real",
            "batch_id": "batch_real",
            "mode": "local_acceptance",
            "status": "completed",
            "video_paths": [str(video_path)],
            "checks": _passing_release_checks(
                validation_report=validation_report,
                zip_validation_report=zip_validation_report,
                batch_artifacts_report=batch_artifacts_report,
                restart_recovery_report=restart_recovery_report,
                model_check_report=model_check_report,
            ),
        },
    )

    status = build_acceptance_status(report_path)

    model_check = next(check for check in status["blocking_checks"] if check["id"] == "model_check")
    assert status["ready_for_release"] is False
    assert model_check["status"] == "fail"
    assert model_check["details"]["model_check_evidence"]["valid"] is False
    assert model_check["details"]["model_check_evidence"]["error"] == "missing_image_provider_check"


def test_build_acceptance_status_blocks_run_diagnose_when_not_ready(tmp_path):
    video_path = tmp_path / "complete.mp4"
    video_path.write_bytes(_valid_mp4_bytes())
    validation_report, zip_validation_report = _valid_export_report_paths(tmp_path)
    batch_artifacts_report = _valid_batch_artifacts_report_path(tmp_path)
    restart_recovery_report = _valid_restart_recovery_report_path(tmp_path)
    run_diagnose_report = _diagnose_report_path(tmp_path, kind="run", ready=False)
    report_path = write_acceptance_report(
        tmp_path,
        {
            "run_id": "run_real",
            "batch_id": "batch_real",
            "mode": "local_acceptance",
            "status": "completed",
            "video_paths": [str(video_path)],
            "checks": _passing_release_checks(
                validation_report=validation_report,
                zip_validation_report=zip_validation_report,
                batch_artifacts_report=batch_artifacts_report,
                restart_recovery_report=restart_recovery_report,
                run_diagnose_report=run_diagnose_report,
            ),
        },
    )

    status = build_acceptance_status(report_path)

    diagnose_check = next(check for check in status["blocking_checks"] if check["id"] == "run_diagnose")
    assert status["ready_for_release"] is False
    assert diagnose_check["status"] == "fail"
    assert diagnose_check["details"]["diagnose_evidence"]["valid"] is False
    assert diagnose_check["details"]["diagnose_evidence"]["error"] == "diagnose_not_ready"
    assert "fix_run_preflight" in status["suggested_actions"]


def test_build_acceptance_status_blocks_batch_diagnose_with_wrong_kind(tmp_path):
    video_path = tmp_path / "complete.mp4"
    video_path.write_bytes(_valid_mp4_bytes())
    validation_report, zip_validation_report = _valid_export_report_paths(tmp_path)
    batch_artifacts_report = _valid_batch_artifacts_report_path(tmp_path)
    restart_recovery_report = _valid_restart_recovery_report_path(tmp_path)
    batch_diagnose_report = _diagnose_report_path(tmp_path, kind="run", ready=True)
    report_path = write_acceptance_report(
        tmp_path,
        {
            "run_id": "run_real",
            "batch_id": "batch_real",
            "mode": "local_acceptance",
            "status": "completed",
            "video_paths": [str(video_path)],
            "checks": _passing_release_checks(
                validation_report=validation_report,
                zip_validation_report=zip_validation_report,
                batch_artifacts_report=batch_artifacts_report,
                restart_recovery_report=restart_recovery_report,
                batch_diagnose_report=batch_diagnose_report,
            ),
        },
    )

    status = build_acceptance_status(report_path)

    diagnose_check = next(check for check in status["blocking_checks"] if check["id"] == "batch_diagnose")
    assert status["ready_for_release"] is False
    assert diagnose_check["status"] == "fail"
    assert diagnose_check["details"]["diagnose_evidence"]["valid"] is False
    assert diagnose_check["details"]["diagnose_evidence"]["error"] == "diagnose_kind_mismatch"
    assert "fix_batch_preflight" in status["suggested_actions"]


def test_build_acceptance_status_blocks_pipeline_schema_with_wrong_stage_order(tmp_path):
    video_path = tmp_path / "complete.mp4"
    video_path.write_bytes(_valid_mp4_bytes())
    validation_report, zip_validation_report = _valid_export_report_paths(tmp_path)
    batch_artifacts_report = _valid_batch_artifacts_report_path(tmp_path)
    restart_recovery_report = _valid_restart_recovery_report_path(tmp_path)
    pipeline_schema_report = _pipeline_schema_report_path(
        tmp_path,
        stage_order=[
            "chief_screenwriter",
            "quality_gate",
            "deepseek_polish",
            "gpt_prompt_writer",
            "gpt_prompt_audit",
            "gpt_prompt_reviser",
            "final_prompts",
            "four_grid_asset",
            "artifacts",
            "comfyui",
        ],
    )
    report_path = write_acceptance_report(
        tmp_path,
        {
            "run_id": "run_real",
            "batch_id": "batch_real",
            "mode": "local_acceptance",
            "status": "completed",
            "video_paths": [str(video_path)],
            "checks": _passing_release_checks(
                validation_report=validation_report,
                zip_validation_report=zip_validation_report,
                batch_artifacts_report=batch_artifacts_report,
                restart_recovery_report=restart_recovery_report,
                pipeline_schema_report=pipeline_schema_report,
            ),
        },
    )

    status = build_acceptance_status(report_path)

    pipeline_check = next(check for check in status["blocking_checks"] if check["id"] == "pipeline_schema")
    assert status["ready_for_release"] is False
    assert pipeline_check["status"] == "fail"
    assert pipeline_check["details"]["pipeline_schema_evidence"]["valid"] is False
    assert pipeline_check["details"]["pipeline_schema_evidence"]["error"] == "stage_order_mismatch"
    assert "verify_pipeline_schema" in status["suggested_actions"]


def test_build_acceptance_status_blocks_full_tests_with_failed_pytest_output(tmp_path):
    video_path = tmp_path / "complete.mp4"
    video_path.write_bytes(_valid_mp4_bytes())
    validation_report, zip_validation_report = _valid_export_report_paths(tmp_path)
    batch_artifacts_report = _valid_batch_artifacts_report_path(tmp_path)
    restart_recovery_report = _valid_restart_recovery_report_path(tmp_path)
    pytest_stdout = _pytest_stdout_path(tmp_path, "1 failed, 413 passed in 72.00s\n")
    report_path = write_acceptance_report(
        tmp_path,
        {
            "run_id": "run_real",
            "batch_id": "batch_real",
            "mode": "local_acceptance",
            "status": "completed",
            "video_paths": [str(video_path)],
            "checks": _passing_release_checks(
                validation_report=validation_report,
                zip_validation_report=zip_validation_report,
                batch_artifacts_report=batch_artifacts_report,
                restart_recovery_report=restart_recovery_report,
                pytest_stdout=pytest_stdout,
            ),
        },
    )

    status = build_acceptance_status(report_path)

    full_tests_check = next(check for check in status["blocking_checks"] if check["id"] == "full_tests")
    assert status["ready_for_release"] is False
    assert full_tests_check["status"] == "fail"
    assert full_tests_check["details"]["full_tests_evidence"]["valid"] is False
    assert full_tests_check["details"]["full_tests_evidence"]["error"] == "pytest_failures_reported"
    assert "run_full_tests" in status["suggested_actions"]


def test_build_acceptance_status_blocks_full_tests_without_exit_code(tmp_path):
    video_path = tmp_path / "complete.mp4"
    video_path.write_bytes(_valid_mp4_bytes())
    validation_report, zip_validation_report = _valid_export_report_paths(tmp_path)
    batch_artifacts_report = _valid_batch_artifacts_report_path(tmp_path)
    restart_recovery_report = _valid_restart_recovery_report_path(tmp_path)
    pytest_stdout = _pytest_stdout_path(tmp_path)
    checks = _passing_release_checks(
        validation_report=validation_report,
        zip_validation_report=zip_validation_report,
        batch_artifacts_report=batch_artifacts_report,
        restart_recovery_report=restart_recovery_report,
        pytest_stdout=pytest_stdout,
    )
    for check in checks:
        if check["id"] == "full_tests":
            check["details"] = {"stdout_path": str(pytest_stdout)}
            break
    report_path = write_acceptance_report(
        tmp_path,
        {
            "run_id": "run_real",
            "batch_id": "batch_real",
            "mode": "local_acceptance",
            "status": "completed",
            "video_paths": [str(video_path)],
            "checks": checks,
        },
    )

    status = build_acceptance_status(report_path)

    full_tests_check = next(check for check in status["blocking_checks"] if check["id"] == "full_tests")
    assert status["ready_for_release"] is False
    assert full_tests_check["status"] == "fail"
    assert full_tests_check["details"]["full_tests_evidence"]["valid"] is False
    assert full_tests_check["details"]["full_tests_evidence"]["error"] == "missing_pytest_exit_code"
    assert "run_full_tests" in status["suggested_actions"]


def test_write_acceptance_report_normalizes_failed_full_tests_command_evidence(tmp_path):
    pytest_stdout = _pytest_stdout_path(tmp_path, "1 failed, 413 passed in 72.00s\n")

    report_path = write_acceptance_report(
        tmp_path,
        {
            "mode": "local_acceptance",
            "status": "failed",
            "checks": [
                {
                    "id": "full_tests",
                    "status": "fail",
                    "evidence": "exit_code=1; 1 failed, 413 passed",
                    "details": {
                        "stdout_path": str(pytest_stdout),
                        "exit_code": 1,
                    },
                }
            ],
        },
    )

    report = json.loads(Path(report_path).read_text(encoding="utf-8"))
    full_tests_check = report["checks"][0]

    assert full_tests_check["status"] == "fail"
    assert full_tests_check["evidence"] == (
        "full_tests_valid=false; exit_code=1; passed=413; failed=1; errors=0"
    )
    assert full_tests_check["details"]["full_tests_evidence"]["valid"] is False
    assert full_tests_check["details"]["full_tests_evidence"]["error"] == "pytest_exit_code_nonzero"


def test_build_acceptance_status_blocks_single_run_pass_without_run_id(tmp_path):
    video_path = tmp_path / "complete.mp4"
    video_path.write_bytes(_valid_mp4_bytes())
    validation_report, zip_validation_report = _valid_export_report_paths(tmp_path)
    report_path = write_acceptance_report(
        tmp_path,
        {
            "batch_id": "batch_real",
            "mode": "local_acceptance",
            "status": "completed",
            "video_paths": [str(video_path)],
            "checks": _passing_release_checks(
                validation_report=validation_report,
                zip_validation_report=zip_validation_report,
            ),
        },
    )

    status = build_acceptance_status(report_path)

    single_run_check = next(check for check in status["blocking_checks"] if check["id"] == "single_run")
    assert status["ready_for_release"] is False
    assert single_run_check["status"] == "fail"
    assert single_run_check["evidence"] == "missing run_id for single_run acceptance"
    assert "run_single_end_to_end" in status["suggested_actions"]


def test_build_acceptance_status_blocks_batch_release_checks_without_batch_id(tmp_path):
    video_path = tmp_path / "complete.mp4"
    video_path.write_bytes(_valid_mp4_bytes())
    validation_report, zip_validation_report = _valid_export_report_paths(tmp_path)
    report_path = write_acceptance_report(
        tmp_path,
        {
            "run_id": "run_real",
            "mode": "local_acceptance",
            "status": "completed",
            "video_paths": [str(video_path)],
            "checks": _passing_release_checks(
                validation_report=validation_report,
                zip_validation_report=zip_validation_report,
            ),
        },
    )

    status = build_acceptance_status(report_path)

    blocking_ids = [check["id"] for check in status["blocking_checks"]]
    assert status["ready_for_release"] is False
    assert "batch_run" in blocking_ids
    assert "restart_recovery" in blocking_ids
    assert "export" in blocking_ids
    assert "run_batch_end_to_end" in status["suggested_actions"]
    assert "run_restart_recovery_drill" in status["suggested_actions"]
    assert "export_and_validate_batch" in status["suggested_actions"]


def test_build_acceptance_status_blocks_single_run_without_video_evidence(tmp_path):
    report_path = tmp_path / "acceptance_report.json"
    report_path.write_text(
        json.dumps(
            {
                "run_id": "run_real",
                "mode": "single_run",
                "status": "completed",
                "video_paths": [],
                "checks": [
                    {
                        "id": "single_run",
                        "status": "pass",
                        "required_evidence": "run artifact dir, openable downloaded video path",
                        "evidence": "run completed",
                    }
                ],
                "summary": {"ready_for_release": True, "check_count": 1},
            }
        ),
        encoding="utf-8",
    )

    status = build_acceptance_status(report_path)

    assert status["ready_for_release"] is False
    assert status["blocking_checks"][0]["id"] == "video_files"
    assert "verify_video_files" in status["suggested_actions"]


def test_build_acceptance_status_revalidates_stale_video_file_check(tmp_path):
    missing_video = tmp_path / "deleted.mp4"
    report_path = tmp_path / "acceptance_report.json"
    report_path.write_text(
        json.dumps(
            {
                "run_id": "run_real",
                "mode": "single_run",
                "status": "completed",
                "video_paths": [str(missing_video)],
                "checks": [
                    {
                        "id": "single_run",
                        "status": "pass",
                        "required_evidence": "run artifact dir, openable downloaded video path",
                        "evidence": "run completed",
                    },
                    {
                        "id": "video_files",
                        "status": "pass",
                        "required_evidence": "local video files exist, are non-empty, and are openable",
                        "evidence": "valid_videos=1/1",
                        "details": {
                            "videos": [
                                {
                                    "path": str(missing_video),
                                    "exists": True,
                                    "size_bytes": 1024,
                                    "openable": True,
                                    "valid": True,
                                }
                            ]
                        },
                    },
                ],
                "summary": {"ready_for_release": True, "check_count": 2},
            }
        ),
        encoding="utf-8",
    )

    status = build_acceptance_status(report_path)

    assert status["ready_for_release"] is False
    video_check = status["blocking_checks"][0]
    assert video_check["id"] == "video_files"
    assert video_check["status"] == "fail"
    assert video_check["details"]["videos"][0]["exists"] is False


def test_build_acceptance_status_rejects_stale_video_pass_without_video_paths(tmp_path):
    report_path = tmp_path / "acceptance_report.json"
    report_path.write_text(
        json.dumps(
            {
                "run_id": "run_real",
                "mode": "single_run",
                "status": "completed",
                "video_paths": [],
                "checks": [
                    {
                        "id": "single_run",
                        "status": "pass",
                        "required_evidence": "run artifact dir, openable downloaded video path",
                        "evidence": "run completed",
                    },
                    {
                        "id": "video_files",
                        "status": "pass",
                        "required_evidence": "local video files exist, are non-empty, and are openable",
                        "evidence": "valid_videos=1/1",
                    },
                ],
                "summary": {"ready_for_release": True, "check_count": 2},
            }
        ),
        encoding="utf-8",
    )

    status = build_acceptance_status(report_path)

    assert status["ready_for_release"] is False
    assert status["blocking_checks"][0]["id"] == "video_files"
    assert status["blocking_checks"][0]["evidence"] == "missing video_paths for single_run acceptance"


def test_cli_acceptance_writes_report(tmp_path):
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "relief_story_agent.cli",
            "acceptance",
            "--output-dir",
            str(tmp_path),
            "--mode",
            "single_run",
            "--status",
            "completed",
            "--run-id",
            "run_demo",
            "--video-path",
            "D:/relief_story_runs/run_demo/output.mp4",
            "--check",
            "full_tests=pass:238 passed",
            "--include-default-matrix",
            "--notes",
            "demo acceptance",
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert completed.returncode == 0
    assert "acceptance_report.json" in completed.stdout
    report = json.loads((tmp_path / "acceptance_report.json").read_text(encoding="utf-8"))
    assert report["run_id"] == "run_demo"
    assert report["checks"][0]["id"] == "full_tests"
    assert any(check["id"] == "restart_recovery" for check in report["checks"])


def test_cli_acceptance_attaches_restart_recovery_report(tmp_path):
    restart_recovery_report = _valid_restart_recovery_report_path(tmp_path)
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "relief_story_agent.cli",
            "acceptance",
            "--output-dir",
            str(tmp_path),
            "--mode",
            "restart_recovery",
            "--status",
            "completed",
            "--batch-id",
            "batch_real",
            "--check",
            "restart_recovery=pass:restart drill verified",
            "--restart-recovery-report",
            str(restart_recovery_report),
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert completed.returncode == 0
    report = json.loads((tmp_path / "acceptance_report.json").read_text(encoding="utf-8"))
    restart_check = next(check for check in report["checks"] if check["id"] == "restart_recovery")
    assert restart_check["status"] == "pass"
    assert restart_check["details"]["restart_recovery_report"] == str(restart_recovery_report)
    assert restart_check["details"]["recovery_evidence"]["valid"] is True


def test_cli_acceptance_attaches_batch_artifacts_report(tmp_path):
    batch_artifacts_report = _valid_batch_artifacts_report_path(tmp_path)
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "relief_story_agent.cli",
            "acceptance",
            "--output-dir",
            str(tmp_path),
            "--mode",
            "batch_run",
            "--status",
            "completed",
            "--batch-id",
            "batch_real",
            "--check",
            "batch_run=pass:batch produced item summaries",
            "--batch-artifacts-report",
            str(batch_artifacts_report),
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert completed.returncode == 0
    report = json.loads((tmp_path / "acceptance_report.json").read_text(encoding="utf-8"))
    batch_check = next(check for check in report["checks"] if check["id"] == "batch_run")
    assert batch_check["status"] == "pass"
    assert batch_check["details"]["batch_artifacts_report"] == str(batch_artifacts_report)
    assert batch_check["details"]["batch_evidence"]["valid"] is True


def test_cli_acceptance_attaches_export_validation_reports(tmp_path):
    validation_report, zip_validation_report = _valid_export_report_paths(tmp_path)
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "relief_story_agent.cli",
            "acceptance",
            "--output-dir",
            str(tmp_path),
            "--mode",
            "export",
            "--status",
            "completed",
            "--batch-id",
            "batch_real",
            "--check",
            "export=pass:publish package validated",
            "--export-validation-report",
            str(validation_report),
            "--export-zip-validation-report",
            str(zip_validation_report),
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert completed.returncode == 0
    report = json.loads((tmp_path / "acceptance_report.json").read_text(encoding="utf-8"))
    export_check = next(check for check in report["checks"] if check["id"] == "export")
    assert export_check["status"] == "pass"
    assert export_check["details"]["validation_report"]["path"] == str(validation_report)
    assert export_check["details"]["zip_validation_report"]["path"] == str(zip_validation_report)
    assert export_check["details"]["validation_report"]["valid"] is True
    assert export_check["details"]["zip_validation_report"]["valid"] is True


def test_cli_acceptance_attaches_restart_recovery_before_after_reports(tmp_path):
    before_report = _valid_recovery_plan_path(tmp_path, "before_restart.json")
    after_report = _valid_recovery_plan_path(tmp_path, "after_restart.json")
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "relief_story_agent.cli",
            "acceptance",
            "--output-dir",
            str(tmp_path),
            "--mode",
            "restart_recovery",
            "--status",
            "completed",
            "--batch-id",
            "batch_real",
            "--check",
            "restart_recovery=pass:restart drill verified",
            "--restart-recovery-before-report",
            str(before_report),
            "--restart-recovery-after-report",
            str(after_report),
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert completed.returncode == 0
    report = json.loads((tmp_path / "acceptance_report.json").read_text(encoding="utf-8"))
    restart_check = next(check for check in report["checks"] if check["id"] == "restart_recovery")
    assert restart_check["status"] == "pass"
    assert restart_check["details"]["restart_recovery_before_report"] == str(before_report)
    assert restart_check["details"]["restart_recovery_after_report"] == str(after_report)
    assert restart_check["details"]["recovery_evidence"]["valid"] is True


def test_cli_acceptance_status_reports_blockers(tmp_path):
    report_path = write_acceptance_report(
        tmp_path,
        {
            "mode": "local_e2e",
            "status": "completed",
            "checks": [
                {
                    "id": "full_tests",
                    "status": "pass",
                    "evidence": "353 passed",
                },
                {
                    "id": "batch_run",
                    "status": "manual_pending",
                    "required_evidence": "batch id, item summaries",
                },
            ],
        },
    )

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "relief_story_agent.cli",
            "acceptance-status",
            "--report",
            report_path,
            "--pretty",
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert completed.returncode == 1
    body = json.loads(completed.stdout)
    assert body["ready_for_release"] is False
    assert body["blocking_checks"][0]["id"] == "full_tests"
    assert body["blocking_checks"][1]["id"] == "batch_run"
    assert "run_full_tests" in body["suggested_actions"]
    assert "run_batch_end_to_end" in body["suggested_actions"]
