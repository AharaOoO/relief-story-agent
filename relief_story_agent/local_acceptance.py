from __future__ import annotations

import json
import subprocess
import sys
from inspect import Parameter, signature
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from .acceptance import build_acceptance_status, write_acceptance_report


CommandRunner = Callable[[list[str]], subprocess.CompletedProcess[str]]


def run_local_acceptance(
    output_dir: str | Path,
    *,
    repo_root: str | Path | None = None,
    python_executable: str | None = None,
    smoke_request: str | Path | None = None,
    model_config: str | Path | None = None,
    run_request: str | Path | None = None,
    batch_request: str | Path | None = None,
    include_local_demo: bool = False,
    local_demo_batch_size: int = 2,
    force_smoke_dry_run: bool = False,
    model_check_real_run: bool = False,
    comfyui_output_prompt_id: str | None = None,
    comfyui_output_endpoint: str = "http://127.0.0.1:8188",
    comfyui_output_artifact_dir: str | Path | None = None,
    comfyui_output_wait: bool = False,
    comfyui_output_download: bool = True,
    comfyui_output_timeout_seconds: float = 600,
    command_timeout_seconds: float = 600,
    command_runner: Callable[..., subprocess.CompletedProcess[str]] | None = None,
) -> dict[str, Any]:
    target_dir = Path(output_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    output_root = target_dir / "command_outputs"
    output_root.mkdir(parents=True, exist_ok=True)

    cwd = Path(repo_root) if repo_root is not None else Path.cwd()
    python = python_executable or sys.executable
    runner = command_runner or _run_command

    commands: list[dict[str, Any]] = []
    checks: list[dict[str, Any]] = []
    sources: dict[str, str] = {}
    video_paths: list[str] = []

    compile_result = _execute_and_record(
        "compileall",
        [python, "-m", "compileall", "-q", "relief_story_agent"],
        cwd=cwd,
        output_root=output_root,
        runner=runner,
        timeout_seconds=command_timeout_seconds,
    )
    commands.append(compile_result)
    checks.append(_check_from_command(compile_result, check_id="compileall", required_evidence="compileall stdout/stderr"))

    pytest_result = _execute_and_record(
        "pytest",
        [python, "-m", "pytest", "relief_story_agent/tests", "-q"],
        cwd=cwd,
        output_root=output_root,
        runner=runner,
        timeout_seconds=command_timeout_seconds,
    )
    commands.append(pytest_result)
    checks.append(
        _check_from_command(
            pytest_result,
            check_id="full_tests",
            required_evidence="python -m pytest relief_story_agent/tests -q output",
        )
    )

    if include_local_demo:
        demo_output_dir = target_dir / "local_demo"
        demo_result = _execute_and_record(
            "local_demo",
            [
                python,
                "-m",
                "relief_story_agent.cli",
                "local-demo",
                "--output-dir",
                str(demo_output_dir),
                "--batch-size",
                str(local_demo_batch_size),
            ],
            cwd=cwd,
            output_root=output_root,
            runner=runner,
            timeout_seconds=command_timeout_seconds,
        )
        commands.append(demo_result)
        local_demo_summary = _local_demo_summary_path_from_stdout(demo_result["stdout"])
        if not local_demo_summary:
            local_demo_summary = demo_output_dir / "local_demo_summary.json"
        if local_demo_summary.exists():
            sources["local_demo_summary"] = str(local_demo_summary)
        else:
            checks.append(
                _check_from_command(
                    demo_result,
                    check_id="local_demo",
                    required_evidence="local_demo_summary.json, fake model run and batch artifacts",
                    extra_evidence="missing local_demo_summary.json",
                )
            )

    if model_config:
        model_command = [
            python,
            "-m",
            "relief_story_agent.cli",
            "model-check",
            "--model-config",
            str(model_config),
        ]
        if run_request:
            model_command.extend(["--run-request", str(run_request)])
        if model_check_real_run:
            model_command.append("--real-run")
        model_result = _execute_and_record(
            "model_check",
            model_command,
            cwd=cwd,
            output_root=output_root,
            runner=runner,
            timeout_seconds=command_timeout_seconds,
        )
        commands.append(model_result)
        checks.append(
            _check_from_command(
                model_result,
                check_id="model_check",
                required_evidence=(
                    "model-check --real-run JSON stdout"
                    if model_check_real_run
                    else "model-check JSON stdout"
                ),
            )
        )

    if run_request:
        diagnose_command = [
            python,
            "-m",
            "relief_story_agent.cli",
            "diagnose",
            "--request",
            str(run_request),
        ]
        if model_config:
            diagnose_command.extend(["--model-config", str(model_config)])
        run_diagnose_result = _execute_and_record(
            "run_diagnose",
            diagnose_command,
            cwd=cwd,
            output_root=output_root,
            runner=runner,
            timeout_seconds=command_timeout_seconds,
        )
        commands.append(run_diagnose_result)
        checks.append(
            _check_from_command(
                run_diagnose_result,
                check_id="run_diagnose",
                required_evidence="diagnose run JSON stdout",
            )
        )

    if batch_request:
        diagnose_command = [
            python,
            "-m",
            "relief_story_agent.cli",
            "diagnose",
            "--request",
            str(batch_request),
            "--kind",
            "batch",
        ]
        if model_config:
            diagnose_command.extend(["--model-config", str(model_config)])
        batch_diagnose_result = _execute_and_record(
            "batch_diagnose",
            diagnose_command,
            cwd=cwd,
            output_root=output_root,
            runner=runner,
            timeout_seconds=command_timeout_seconds,
        )
        commands.append(batch_diagnose_result)
        checks.append(
            _check_from_command(
                batch_diagnose_result,
                check_id="batch_diagnose",
                required_evidence="diagnose batch JSON stdout",
            )
        )

    if smoke_request:
        smoke_command = [python, "-m", "relief_story_agent.smoke_comfyui", "--request", str(smoke_request)]
        if force_smoke_dry_run:
            smoke_command.append("--dry-run")
        smoke_result = _execute_and_record(
            "comfyui_smoke",
            smoke_command,
            cwd=cwd,
            output_root=output_root,
            runner=runner,
            timeout_seconds=command_timeout_seconds,
        )
        commands.append(smoke_result)
        smoke_result_path = _smoke_result_path_from_stdout(smoke_result["stdout"])
        if smoke_result_path and smoke_result_path.exists():
            sources["smoke_result"] = str(smoke_result_path)
        else:
            checks.append(
                _check_from_command(
                    smoke_result,
                    check_id="comfyui_dry_smoke" if force_smoke_dry_run else "comfyui_real_smoke",
                    required_evidence=(
                        "smoke_result.json, no prompt id"
                        if force_smoke_dry_run
                        else "smoke_result.json, prompt id"
                    ),
                    extra_evidence="missing smoke_result.json",
                )
            )

    if comfyui_output_prompt_id:
        output_artifact_dir = (
            Path(comfyui_output_artifact_dir)
            if comfyui_output_artifact_dir
            else target_dir / "comfyui_output_refresh"
        )
        output_command = [
            python,
            "-m",
            "relief_story_agent.cli",
            "comfyui-outputs",
            "--endpoint",
            str(comfyui_output_endpoint),
            "--prompt-id",
            str(comfyui_output_prompt_id),
            "--timeout-seconds",
            str(comfyui_output_timeout_seconds),
            "--artifact-dir",
            str(output_artifact_dir),
        ]
        if comfyui_output_wait:
            output_command.append("--wait")
        if comfyui_output_download:
            output_command.append("--download")
        output_result = _execute_and_record(
            "comfyui_outputs",
            output_command,
            cwd=cwd,
            output_root=output_root,
            runner=runner,
            timeout_seconds=command_timeout_seconds,
        )
        commands.append(output_result)
        output_check, refreshed_video_paths = _check_from_comfyui_outputs_command(
            output_result,
            require_download=comfyui_output_download,
        )
        checks.append(output_check)
        video_paths.extend(refreshed_video_paths)

    status = (
        "completed"
        if all(item["exit_code"] == 0 for item in commands)
        and _executed_checks_pass(checks)
        else "failed"
    )
    report_path = write_acceptance_report(
        target_dir,
        {
            "mode": "local_acceptance",
            "status": status,
            "video_paths": video_paths,
            "checks": checks,
            "sources": sources,
            "include_default_matrix": True,
            "notes": "Generated by relief-story-agent local-acceptance.",
        },
    )
    acceptance_status = build_acceptance_status(report_path)
    acceptance_status_path = target_dir / "acceptance_status.json"
    acceptance_status_path.write_text(
        json.dumps(acceptance_status, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "repo_root": str(cwd),
        "acceptance_report": report_path,
        "acceptance_status": str(acceptance_status_path),
        "markdown_report": str(target_dir / "ACCEPTANCE_REPORT.md"),
        "command_output_dir": str(output_root),
        "commands": commands,
        "sources": sources,
        "video_paths": video_paths,
    }
    summary_path = target_dir / "local_acceptance_summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {
        "status": status,
        "acceptance_report": report_path,
        "acceptance_status": str(acceptance_status_path),
        "markdown_report": str(target_dir / "ACCEPTANCE_REPORT.md"),
        "summary": str(summary_path),
        "command_output_dir": str(output_root),
    }


def _execute_and_record(
    command_id: str,
    command: list[str],
    *,
    cwd: Path,
    output_root: Path,
    runner: Callable[..., subprocess.CompletedProcess[str]],
    timeout_seconds: float,
) -> dict[str, Any]:
    completed = _call_runner(runner, command, cwd=cwd, timeout_seconds=timeout_seconds)
    stdout_path = output_root / f"{command_id}.stdout.txt"
    stderr_path = output_root / f"{command_id}.stderr.txt"
    stdout = completed.stdout or ""
    stderr = completed.stderr or ""
    stdout_path.write_text(stdout, encoding="utf-8")
    stderr_path.write_text(stderr, encoding="utf-8")
    return {
        "id": command_id,
        "command": command,
        "cwd": str(cwd),
        "exit_code": int(completed.returncode),
        "stdout": stdout,
        "stderr": stderr,
        "stdout_path": str(stdout_path),
        "stderr_path": str(stderr_path),
    }


def _run_command(
    command: list[str],
    *,
    cwd: Path,
    timeout_seconds: float,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
    )


def _call_runner(
    runner: Callable[..., subprocess.CompletedProcess[str]],
    command: list[str],
    *,
    cwd: Path,
    timeout_seconds: float,
) -> subprocess.CompletedProcess[str]:
    parameters = signature(runner).parameters
    accepts_timeout = "timeout_seconds" in parameters or any(
        parameter.kind == Parameter.VAR_KEYWORD for parameter in parameters.values()
    )
    if accepts_timeout:
        return runner(command, cwd=cwd, timeout_seconds=timeout_seconds)
    return runner(command, cwd=cwd)


def _check_from_command(
    command_result: dict[str, Any],
    *,
    check_id: str,
    required_evidence: str,
    extra_evidence: str = "",
) -> dict[str, Any]:
    evidence_parts = [f"exit_code={command_result['exit_code']}"]
    summary = _command_output_summary(command_result)
    if summary:
        evidence_parts.extend(summary)
    if extra_evidence:
        evidence_parts.append(extra_evidence)
    semantic_ready = _command_semantic_ready(command_result)
    is_pass = (
        command_result["exit_code"] == 0
        and not extra_evidence
        and semantic_ready
    )
    return {
        "id": check_id,
        "required_evidence": required_evidence,
        "status": "pass" if is_pass else "fail",
        "evidence": "; ".join(evidence_parts),
        "details": {
            "command": command_result["command"],
            "cwd": command_result["cwd"],
            "exit_code": command_result["exit_code"],
            "stdout_path": command_result["stdout_path"],
            "stderr_path": command_result["stderr_path"],
        },
    }


def _executed_checks_pass(checks: list[dict[str, Any]]) -> bool:
    return all(str(check.get("status") or "") == "pass" for check in checks)


def _command_semantic_ready(command_result: dict[str, Any]) -> bool:
    stdout = str(command_result.get("stdout") or "")
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError:
        return True
    if "ready" in payload and not bool(payload.get("ready")):
        return False
    if "valid" in payload and not bool(payload.get("valid")):
        return False
    return True


def _check_from_comfyui_outputs_command(
    command_result: dict[str, Any],
    *,
    require_download: bool,
) -> tuple[dict[str, Any], list[str]]:
    required_evidence = "comfyui-outputs JSON, ready=true, video_count>0"
    try:
        payload = json.loads(str(command_result.get("stdout") or ""))
    except json.JSONDecodeError:
        return (
            _check_from_command(
                command_result,
                check_id="comfyui_outputs",
                required_evidence=required_evidence,
                extra_evidence="invalid comfyui-outputs JSON stdout",
            ),
            [],
        )

    prompt_ids = [str(item) for item in payload.get("prompt_ids") or []]
    ready = bool(payload.get("ready"))
    video_count = int(payload.get("video_count") or 0)
    downloaded_count = int(payload.get("downloaded_count") or 0)
    actual_outputs = payload.get("actual_outputs") or []
    video_paths = [
        str(output.get("local_path") or "")
        for output in actual_outputs
        if isinstance(output, dict)
        and str(output.get("media_type") or "") == "video"
        and str(output.get("local_path") or "")
    ]
    download_ready = not require_download or (downloaded_count > 0 and bool(video_paths))
    is_pass = command_result["exit_code"] == 0 and ready and video_count > 0 and download_ready
    return (
        {
            "id": "comfyui_outputs",
            "required_evidence": required_evidence,
            "status": "pass" if is_pass else "fail",
            "evidence": (
                f"ready={str(ready).lower()}; "
                f"video_count={video_count}; "
                f"downloaded_count={downloaded_count}; "
                f"prompt_ids={','.join(prompt_ids)}"
            ),
            "details": {
                "command": command_result["command"],
                "cwd": command_result["cwd"],
                "exit_code": command_result["exit_code"],
                "stdout_path": command_result["stdout_path"],
                "stderr_path": command_result["stderr_path"],
                "status": str(payload.get("status") or ""),
                "actual_outputs": actual_outputs,
            },
        },
        video_paths,
    )


def _last_nonempty_line(text: str) -> str:
    for line in reversed(text.splitlines()):
        stripped = line.strip()
        if stripped:
            return stripped
    return ""


def _command_output_summary(command_result: dict[str, Any]) -> list[str]:
    stdout = str(command_result.get("stdout") or "")
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError:
        line = _last_nonempty_line(stdout or str(command_result.get("stderr") or ""))
        return [line] if line else []
    parts: list[str] = []
    if "kind" in payload:
        parts.append(f"kind={payload['kind']}")
    if "ready" in payload:
        parts.append(f"ready={str(bool(payload['ready'])).lower()}")
    if "valid" in payload:
        parts.append(f"valid={str(bool(payload['valid'])).lower()}")
    if "status" in payload:
        parts.append(f"status={payload['status']}")
    if not parts:
        line = _last_nonempty_line(stdout)
        return [line] if line else []
    return parts


def _smoke_result_path_from_stdout(stdout: str) -> Path | None:
    artifact_dir = ""
    for line in stdout.splitlines():
        if line.startswith("artifact_dir="):
            artifact_dir = line.split("=", 1)[1].strip()
    if not artifact_dir:
        return None
    return Path(artifact_dir) / "smoke_result.json"


def _local_demo_summary_path_from_stdout(stdout: str) -> Path | None:
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError:
        return None
    summary_path = str(payload.get("summary_path") or "")
    return Path(summary_path) if summary_path else None
