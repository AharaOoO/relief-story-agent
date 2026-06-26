from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from relief_story_agent.acceptance import build_acceptance_status, write_acceptance_report


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
    assert report["checks"][0]["status"] == "pass"
    assert report["summary"]["by_status"]["pass"] == 1
    assert report["summary"]["by_status"]["manual_pending"] == 1
    assert report["summary"]["ready_for_release"] is False

    markdown = (tmp_path / "ACCEPTANCE_REPORT.md").read_text(encoding="utf-8")
    assert "| full_tests | python -m pytest relief_story_agent/tests -q | pass | 238 passed |" in markdown
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
    assert report["summary"]["ready_for_release"] is True


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
    assert status["summary"]["check_count"] == 13
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
    assert status["summary"]["check_count"] == 13
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
    assert blocking_ids[:2] == ["comfyui_real_smoke", "single_run"]
    assert "local_demo" in blocking_ids
    assert "export" in blocking_ids
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
    assert status["summary"]["blocking_count"] == 12
    assert status["summary"]["check_count"] == 13


def test_build_acceptance_status_blocks_single_run_without_video_evidence(tmp_path):
    report_path = tmp_path / "acceptance_report.json"
    report_path.write_text(
        json.dumps(
            {
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
    assert body["blocking_checks"][0]["id"] == "batch_run"
    assert "run_batch_end_to_end" in body["suggested_actions"]
