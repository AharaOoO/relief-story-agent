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
    assert Path(result["acceptance_status"]).exists()
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

    acceptance_status = json.loads(Path(result["acceptance_status"]).read_text(encoding="utf-8"))
    assert acceptance_status["ready_for_release"] is False
    assert acceptance_status["summary"]["blocking_count"] > 0


def test_run_local_acceptance_collects_model_and_request_diagnostics(tmp_path):
    calls: list[list[str]] = []
    model_config = tmp_path / "model_config.json"
    run_request = tmp_path / "run_request.json"
    batch_request = tmp_path / "batch_request.json"
    for path in (model_config, run_request, batch_request):
        path.write_text("{}", encoding="utf-8")

    def runner(command: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        if command[2] == "compileall":
            return subprocess.CompletedProcess(command, 0, "", "")
        if command[2] == "pytest":
            return subprocess.CompletedProcess(command, 0, "330 passed in 52.86s\n", "")
        if command[2:5] == ["relief_story_agent.cli", "model-check", "--model-config"]:
            return subprocess.CompletedProcess(command, 0, '{"ready": true, "checks": []}\n', "")
        if command[2:5] == ["relief_story_agent.cli", "diagnose", "--request"] and "--kind" not in command:
            return subprocess.CompletedProcess(command, 0, '{"kind": "run", "ready": true}\n', "")
        if command[2:5] == ["relief_story_agent.cli", "diagnose", "--request"] and "--kind" in command:
            return subprocess.CompletedProcess(command, 0, '{"kind": "batch", "ready": true}\n', "")
        raise AssertionError(command)

    result = run_local_acceptance(
        tmp_path / "acceptance",
        repo_root=tmp_path,
        python_executable=sys.executable,
        model_config=model_config,
        run_request=run_request,
        batch_request=batch_request,
        command_runner=runner,
    )

    assert [command[2] for command in calls] == [
        "compileall",
        "pytest",
        "relief_story_agent.cli",
        "relief_story_agent.cli",
        "relief_story_agent.cli",
    ]
    assert calls[2][3] == "model-check"
    assert "--run-request" in calls[2]
    assert str(run_request) in calls[2]
    assert calls[3][3] == "diagnose"
    assert calls[4][3] == "diagnose"
    assert "--kind" in calls[4]

    report = json.loads(Path(result["acceptance_report"]).read_text(encoding="utf-8"))
    checks = {check["id"]: check for check in report["checks"]}

    assert result["status"] == "completed"
    assert checks["model_check"]["status"] == "pass"
    assert checks["model_check"]["evidence"] == "exit_code=0; ready=true"
    assert checks["run_diagnose"]["status"] == "pass"
    assert checks["run_diagnose"]["evidence"] == "exit_code=0; kind=run; ready=true"
    assert checks["batch_diagnose"]["status"] == "pass"
    assert checks["batch_diagnose"]["evidence"] == "exit_code=0; kind=batch; ready=true"


def test_run_local_acceptance_fails_when_json_readiness_is_false(tmp_path):
    model_config = tmp_path / "model_config.json"
    model_config.write_text("{}", encoding="utf-8")

    def runner(command: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
        if command[2] == "compileall":
            return subprocess.CompletedProcess(command, 0, "", "")
        if command[2] == "pytest":
            return subprocess.CompletedProcess(command, 0, "349 passed in 59.92s\n", "")
        if command[2:5] == ["relief_story_agent.cli", "model-check", "--model-config"]:
            return subprocess.CompletedProcess(
                command,
                0,
                '{"ready": false, "missing_environment_variables": ["OPENAI_API_KEY"]}\n',
                "",
            )
        raise AssertionError(command)

    result = run_local_acceptance(
        tmp_path / "acceptance",
        repo_root=tmp_path,
        python_executable=sys.executable,
        model_config=model_config,
        command_runner=runner,
    )

    report = json.loads(Path(result["acceptance_report"]).read_text(encoding="utf-8"))
    checks = {check["id"]: check for check in report["checks"]}

    assert result["status"] == "failed"
    assert report["status"] == "failed"
    assert checks["model_check"]["status"] == "fail"
    assert checks["model_check"]["evidence"] == "exit_code=0; ready=false"


def test_run_local_acceptance_can_collect_offline_local_demo(tmp_path):
    calls: list[list[str]] = []

    def runner(command: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        if command[2] == "compileall":
            return subprocess.CompletedProcess(command, 0, "", "")
        if command[2] == "pytest":
            return subprocess.CompletedProcess(command, 0, "331 passed in 54.94s\n", "")
        if command[2:4] == ["relief_story_agent.cli", "local-demo"]:
            output_dir = Path(command[command.index("--output-dir") + 1])
            output_dir.mkdir(parents=True, exist_ok=True)
            summary_path = output_dir / "local_demo_summary.json"
            summary_path.write_text(
                json.dumps(
                    {
                        "status": "completed",
                        "single_run": {"status": "completed", "artifact_dir": str(output_dir / "runs" / "run_demo")},
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
            return subprocess.CompletedProcess(
                command,
                0,
                json.dumps({"status": "completed", "summary_path": str(summary_path)}) + "\n",
                "",
            )
        raise AssertionError(command)

    result = run_local_acceptance(
        tmp_path / "acceptance",
        repo_root=tmp_path,
        python_executable=sys.executable,
        include_local_demo=True,
        local_demo_batch_size=2,
        command_runner=runner,
    )

    assert [command[2] for command in calls] == ["compileall", "pytest", "relief_story_agent.cli"]
    assert calls[2][3] == "local-demo"
    assert calls[2][calls[2].index("--batch-size") + 1] == "2"

    report = json.loads(Path(result["acceptance_report"]).read_text(encoding="utf-8"))
    checks = {check["id"]: check for check in report["checks"]}

    assert result["status"] == "completed"
    assert checks["local_demo"]["status"] == "pass"
    assert checks["local_demo"]["evidence"] == "single_run=completed; batch=completed; batch_completed=2/2; restart_recovery=completed; no_external_calls=true"


def test_run_local_acceptance_can_collect_comfyui_output_refresh(tmp_path):
    calls: list[list[str]] = []
    downloaded = tmp_path / "outputs" / "render.mp4"
    downloaded.parent.mkdir(parents=True)
    downloaded.write_bytes(b"video")

    def runner(command: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        if command[2] == "compileall":
            return subprocess.CompletedProcess(command, 0, "", "")
        if command[2] == "pytest":
            return subprocess.CompletedProcess(command, 0, "341 passed in 56.69s\n", "")
        if command[2:4] == ["relief_story_agent.cli", "comfyui-outputs"]:
            return subprocess.CompletedProcess(
                command,
                0,
                json.dumps(
                    {
                        "status": "ready",
                        "ready": True,
                        "prompt_ids": ["prompt_video"],
                        "video_count": 1,
                        "image_count": 0,
                        "downloaded_count": 1,
                        "actual_outputs": [
                            {
                                "prompt_id": "prompt_video",
                                "filename": "render.mp4",
                                "media_type": "video",
                                "local_path": str(downloaded),
                            }
                        ],
                    }
                )
                + "\n",
                "",
            )
        raise AssertionError(command)

    result = run_local_acceptance(
        tmp_path / "acceptance",
        repo_root=tmp_path,
        python_executable=sys.executable,
        comfyui_output_prompt_id="prompt_video",
        comfyui_output_endpoint="http://127.0.0.1:8188",
        command_runner=runner,
    )

    assert [command[2] for command in calls] == ["compileall", "pytest", "relief_story_agent.cli"]
    assert calls[2][3] == "comfyui-outputs"
    assert "--prompt-id" in calls[2]
    assert calls[2][calls[2].index("--prompt-id") + 1] == "prompt_video"
    assert "--download" in calls[2]

    report = json.loads(Path(result["acceptance_report"]).read_text(encoding="utf-8"))
    checks = {check["id"]: check for check in report["checks"]}

    assert result["status"] == "completed"
    assert checks["comfyui_outputs"]["status"] == "pass"
    assert checks["comfyui_outputs"]["evidence"] == "ready=true; video_count=1; downloaded_count=1; prompt_ids=prompt_video"
    assert report["video_paths"] == [str(downloaded)]


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
        model_config: str,
        run_request: str,
        batch_request: str,
        include_local_demo: bool,
        local_demo_batch_size: int,
        force_smoke_dry_run: bool,
        comfyui_output_prompt_id: str,
        comfyui_output_endpoint: str,
        comfyui_output_artifact_dir: str,
        comfyui_output_wait: bool,
        comfyui_output_download: bool,
        comfyui_output_timeout_seconds: float,
        command_timeout_seconds: float,
    ) -> dict[str, str]:
        captured.update(
            {
                "output_dir": output_dir,
                "repo_root": repo_root,
                "smoke_request": smoke_request,
                "model_config": model_config,
                "run_request": run_request,
                "batch_request": batch_request,
                "include_local_demo": include_local_demo,
                "local_demo_batch_size": local_demo_batch_size,
                "force_smoke_dry_run": force_smoke_dry_run,
                "comfyui_output_prompt_id": comfyui_output_prompt_id,
                "comfyui_output_endpoint": comfyui_output_endpoint,
                "comfyui_output_artifact_dir": comfyui_output_artifact_dir,
                "comfyui_output_wait": comfyui_output_wait,
                "comfyui_output_download": comfyui_output_download,
                "comfyui_output_timeout_seconds": comfyui_output_timeout_seconds,
                "command_timeout_seconds": command_timeout_seconds,
            }
        )
        return {
            "status": "completed",
            "acceptance_report": str(tmp_path / "acceptance_report.json"),
            "acceptance_status": str(tmp_path / "acceptance_status.json"),
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
            "--model-config",
            "D:/model_config.json",
            "--run-request",
            "D:/run_request.json",
            "--batch-request",
            "D:/batch_request.json",
            "--local-demo",
            "--local-demo-batch-size",
            "3",
            "--smoke-dry-run",
            "--comfyui-output-prompt-id",
            "prompt_video",
            "--comfyui-output-endpoint",
            "127.0.0.1:8188",
            "--comfyui-output-artifact-dir",
            "D:/outputs",
            "--comfyui-output-wait",
            "--no-comfyui-output-download",
            "--comfyui-output-timeout-seconds",
            "44",
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
        "model_config": "D:/model_config.json",
        "run_request": "D:/run_request.json",
        "batch_request": "D:/batch_request.json",
        "include_local_demo": True,
        "local_demo_batch_size": 3,
        "force_smoke_dry_run": True,
        "comfyui_output_prompt_id": "prompt_video",
        "comfyui_output_endpoint": "127.0.0.1:8188",
        "comfyui_output_artifact_dir": "D:/outputs",
        "comfyui_output_wait": True,
        "comfyui_output_download": False,
        "comfyui_output_timeout_seconds": 44.0,
        "command_timeout_seconds": 12.5,
    }
    output = json.loads(capsys.readouterr().out)
    assert output["summary"].endswith("local_acceptance_summary.json")
