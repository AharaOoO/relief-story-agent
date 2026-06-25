from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from relief_story_agent import cli
from relief_story_agent.local_acceptance import run_local_acceptance


def test_run_local_acceptance_collects_commands_and_smoke_report(tmp_path):
    smoke_artifact_dir = tmp_path / "smoke_artifacts"
    smoke_artifact_dir.mkdir()
    (smoke_artifact_dir / "smoke_result.json").write_text(
        json.dumps(
            {
                "status": "passed",
                "ready": True,
                "prompt_id": "prompt-local",
                "artifact_dir": str(smoke_artifact_dir),
            }
        ),
        encoding="utf-8",
    )

    calls: list[list[str]] = []

    def runner(command: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        if command[2] == "compileall":
            return subprocess.CompletedProcess(command, 0, "", "")
        if command[2] == "pytest":
            return subprocess.CompletedProcess(command, 0, "318 passed in 52.91s\n", "")
        if command[2] == "relief_story_agent.smoke_comfyui":
            return subprocess.CompletedProcess(
                command,
                0,
                "\n".join(
                    [
                        "status=passed",
                        "ready=true",
                        "prompt_id=prompt-local",
                        f"artifact_dir={smoke_artifact_dir}",
                    ]
                ),
                "",
            )
        raise AssertionError(command)

    result = run_local_acceptance(
        tmp_path / "acceptance",
        repo_root=tmp_path,
        python_executable=sys.executable,
        smoke_request=tmp_path / "smoke_request.json",
        force_smoke_dry_run=False,
        command_runner=runner,
    )

    assert [command[2] for command in calls] == ["compileall", "pytest", "relief_story_agent.smoke_comfyui"]
    assert Path(result["acceptance_report"]).exists()
    assert Path(result["summary"]).exists()
    assert (tmp_path / "acceptance" / "command_outputs" / "pytest.stdout.txt").read_text(encoding="utf-8") == "318 passed in 52.91s\n"

    report = json.loads(Path(result["acceptance_report"]).read_text(encoding="utf-8"))
    checks = {check["id"]: check for check in report["checks"]}

    assert result["status"] == "completed"
    assert checks["compileall"]["status"] == "pass"
    assert checks["full_tests"]["status"] == "pass"
    assert checks["full_tests"]["evidence"] == "exit_code=0; 318 passed in 52.91s"
    assert checks["comfyui_real_smoke"]["status"] == "pass"
    assert checks["comfyui_real_smoke"]["evidence"].startswith("prompt_id=prompt-local")
    assert checks["restart_recovery"]["status"] == "manual_pending"


def test_run_local_acceptance_marks_failed_commands(tmp_path):
    def runner(command: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
        if command[2] == "compileall":
            return subprocess.CompletedProcess(command, 0, "", "")
        if command[2] == "pytest":
            return subprocess.CompletedProcess(command, 1, "1 failed, 317 passed\n", "failure detail\n")
        raise AssertionError(command)

    result = run_local_acceptance(
        tmp_path / "acceptance",
        repo_root=tmp_path,
        python_executable=sys.executable,
        command_runner=runner,
    )

    report = json.loads(Path(result["acceptance_report"]).read_text(encoding="utf-8"))
    checks = {check["id"]: check for check in report["checks"]}

    assert result["status"] == "failed"
    assert checks["compileall"]["status"] == "pass"
    assert checks["full_tests"]["status"] == "fail"
    assert checks["full_tests"]["evidence"] == "exit_code=1; 1 failed, 317 passed"
    assert checks["full_tests"]["details"]["stderr_path"].endswith("pytest.stderr.txt")


def test_cli_local_acceptance_invokes_snapshot_runner(tmp_path, monkeypatch, capsys):
    captured: dict[str, object] = {}

    def fake_run_local_acceptance(
        output_dir: str,
        *,
        repo_root: str,
        smoke_request: str,
        force_smoke_dry_run: bool,
        command_timeout_seconds: float,
    ) -> dict[str, str]:
        captured.update(
            {
                "output_dir": output_dir,
                "repo_root": repo_root,
                "smoke_request": smoke_request,
                "force_smoke_dry_run": force_smoke_dry_run,
                "command_timeout_seconds": command_timeout_seconds,
            }
        )
        return {
            "status": "completed",
            "acceptance_report": str(tmp_path / "acceptance_report.json"),
            "markdown_report": str(tmp_path / "ACCEPTANCE_REPORT.md"),
            "summary": str(tmp_path / "local_acceptance_summary.json"),
            "command_output_dir": str(tmp_path / "command_outputs"),
        }

    monkeypatch.setattr(cli, "run_local_acceptance", fake_run_local_acceptance)

    exit_code = cli.main(
        [
            "local-acceptance",
            "--output-dir",
            str(tmp_path),
            "--repo-root",
            "D:/repo",
            "--smoke-request",
            "D:/smoke_request.json",
            "--smoke-dry-run",
            "--timeout-seconds",
            "12.5",
            "--pretty",
        ]
    )

    assert exit_code == 0
    assert captured == {
        "output_dir": str(tmp_path),
        "repo_root": "D:/repo",
        "smoke_request": "D:/smoke_request.json",
        "force_smoke_dry_run": True,
        "command_timeout_seconds": 12.5,
    }
    output = json.loads(capsys.readouterr().out)
    assert output["summary"].endswith("local_acceptance_summary.json")
