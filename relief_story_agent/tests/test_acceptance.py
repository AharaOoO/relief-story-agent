from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from relief_story_agent.acceptance import write_acceptance_report


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
