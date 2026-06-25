from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.parse import urlencode

import httpx

from .acceptance import build_acceptance_status, write_acceptance_report
from .config_validation import diagnose_batch_configuration, diagnose_run_configuration
from .comfyui import connect_comfyui, discover_workflows
from .comfyui_outputs import refresh_comfyui_prompt_outputs
from .local_acceptance import run_local_acceptance
from .local_demo import run_local_demo
from .local_runtime import LocalRuntimeConfig, build_local_bootstrap
from .model_config import ModelConfigRegistry
from .model_probe import run_model_probe
from .models import (
    BatchRunRequest,
    ComfyUIConnectionRequest,
    ComfyUIOutputRefreshRequest,
    ComfyUIWorkflowDiscoveryRequest,
    RunRequest,
)
from .pipeline import build_pipeline_schema
from .prompt_templates import validate_prompt_template_file
from .server import main as server_main
from .setup_wizard import write_local_config_bundle
from .smoke_comfyui import main as smoke_main


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="relief-story-agent")
    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("serve", add_help=False, help="Start the local API server.")
    subparsers.add_parser("smoke-comfyui", add_help=False, help="Run local ComfyUI smoke verification.")
    connect_parser = subparsers.add_parser(
        "connect-comfyui",
        help="Check a local ComfyUI endpoint and optional workflow file.",
    )
    connect_parser.add_argument("--request", default="", help="Optional JSON request file.")
    connect_parser.add_argument("--endpoint", default="", help="ComfyUI base URL.")
    connect_parser.add_argument("--workflow-api-path", default="", help="Optional workflow JSON path.")
    connect_parser.add_argument("--timeout-seconds", type=float, default=0, help="Network timeout.")
    connect_parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")
    discover_parser = subparsers.add_parser(
        "discover-comfyui-workflows",
        help="Scan local directories for ComfyUI workflow JSON candidates.",
    )
    discover_parser.add_argument("--search-root", action="append", default=[], help="Directory or JSON file to scan.")
    discover_parser.add_argument("--endpoint", default="http://127.0.0.1:8188", help="ComfyUI base URL.")
    discover_parser.add_argument("--max-results", type=int, default=25, help="Maximum workflow candidates to return.")
    discover_parser.add_argument("--filename-keyword", action="append", default=[], help="Only include JSON filenames containing this text.")
    discover_parser.add_argument("--hide-unsupported", action="store_true", help="Omit workflows that cannot be analyzed.")
    discover_parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")
    outputs_parser = subparsers.add_parser(
        "comfyui-outputs",
        help="Check and optionally download ComfyUI outputs by prompt id.",
    )
    outputs_parser.add_argument("--request", default="", help="Optional JSON request file.")
    outputs_parser.add_argument("--endpoint", default="", help="ComfyUI base URL.")
    outputs_parser.add_argument("--prompt-id", action="append", default=[], help="ComfyUI prompt id. Repeatable.")
    outputs_parser.add_argument("--artifact-dir", default="", help="Directory for downloaded output files.")
    outputs_parser.add_argument("--wait", action="store_true", help="Poll until every prompt id has output or times out.")
    outputs_parser.add_argument("--download", action="store_true", help="Download files returned by /history.")
    outputs_parser.add_argument("--timeout-seconds", type=float, default=None, help="Output wait timeout.")
    outputs_parser.add_argument("--poll-interval-seconds", type=float, default=None, help="Output wait poll interval.")
    outputs_parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")
    diagnose_parser = subparsers.add_parser(
        "diagnose",
        help="Diagnose a local run or batch request without enqueueing work.",
    )
    diagnose_parser.add_argument("--request", required=True, help="Run or batch request JSON file.")
    diagnose_parser.add_argument("--model-config", default="", help="Optional model registry JSON file.")
    diagnose_parser.add_argument(
        "--kind",
        choices=("auto", "run", "batch"),
        default="auto",
        help="Request type. Defaults to auto-detecting batch files with items[].",
    )
    diagnose_parser.add_argument(
        "--check-comfyui-connection",
        action="store_true",
        help="Also ping the configured ComfyUI /queue endpoint.",
    )
    diagnose_parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")
    pipeline_schema_parser = subparsers.add_parser(
        "pipeline-schema",
        help="Print the fixed stage contract used by runs, recovery, and diagnostics.",
    )
    pipeline_schema_parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")
    template_check_parser = subparsers.add_parser(
        "template-check",
        help="Validate editable prompt templates before a real run spends model quota.",
    )
    template_check_parser.add_argument("--writer-template", default="", help="Prompt writer Markdown template.")
    template_check_parser.add_argument("--audit-template", default="", help="Prompt audit Markdown template.")
    template_check_parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")
    model_check_parser = subparsers.add_parser(
        "model-check",
        help="Validate model profile readiness and optionally run a tiny JSON probe.",
    )
    model_check_parser.add_argument("--model-config", required=True, help="Model registry JSON file.")
    model_check_parser.add_argument("--profile", action="append", default=[], help="Profile name to check. Repeatable.")
    model_check_parser.add_argument("--real-run", action="store_true", help="Send a tiny JSON request to each selected model profile.")
    model_check_parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")
    local_bootstrap_parser = subparsers.add_parser(
        "local-bootstrap",
        help="Print local API/UI/ComfyUI ports and endpoint paths for UI integration.",
    )
    local_bootstrap_parser.add_argument("--api-host", default="127.0.0.1", help="API host.")
    local_bootstrap_parser.add_argument("--api-port", type=int, default=8891, help="API port.")
    local_bootstrap_parser.add_argument("--ui-origin", default="http://127.0.0.1:5173", help="Local UI origin.")
    local_bootstrap_parser.add_argument("--comfyui-endpoint", default="http://127.0.0.1:8188", help="ComfyUI endpoint.")
    local_bootstrap_parser.add_argument("--cors-origin", action="append", default=[], help="Extra allowed UI origin.")
    local_bootstrap_parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")
    local_doctor_parser = subparsers.add_parser(
        "local-doctor",
        help="Fetch local server readiness and suggested setup actions.",
    )
    _add_api_base_args(local_doctor_parser)
    local_doctor_parser.add_argument(
        "--check-comfyui-connection",
        action="store_true",
        help="Ask the server to ping ComfyUI /queue.",
    )
    local_doctor_parser.add_argument("--comfyui-endpoint", default="", help="Optional ComfyUI endpoint override.")
    local_doctor_parser.add_argument("--comfyui-workflow-path", default="", help="Optional workflow JSON path for ComfyUI runtime node validation.")
    local_doctor_parser.add_argument("--comfyui-timeout-seconds", type=float, default=5.0, help="ComfyUI ping timeout.")
    local_readiness_parser = subparsers.add_parser(
        "local-readiness",
        help="Fetch one combined local deployment readiness report for launchers and UI.",
    )
    _add_api_base_args(local_readiness_parser)
    local_readiness_parser.add_argument(
        "--acceptance-report",
        default="",
        help="Optional acceptance_report.json path to include release evidence blockers.",
    )
    local_readiness_parser.add_argument(
        "--check-comfyui-connection",
        action="store_true",
        help="Ask the server to ping ComfyUI /queue.",
    )
    local_readiness_parser.add_argument("--comfyui-endpoint", default="", help="Optional ComfyUI endpoint override.")
    local_readiness_parser.add_argument("--comfyui-workflow-path", default="", help="Optional workflow JSON path for ComfyUI runtime node validation.")
    local_readiness_parser.add_argument("--comfyui-timeout-seconds", type=float, default=5.0, help="ComfyUI ping timeout.")
    local_demo_parser = subparsers.add_parser(
        "local-demo",
        help="Run an offline fake-model demo that writes run and batch artifacts.",
    )
    local_demo_parser.add_argument("--output-dir", required=True, help="Directory to write local demo artifacts.")
    local_demo_parser.add_argument("--batch-size", type=int, default=2, help="Number of batch items to simulate.")
    local_demo_parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")
    run_parser = subparsers.add_parser(
        "run",
        help="Create a run through a running local API server.",
    )
    _add_api_request_args(run_parser)
    _add_preflight_args(run_parser)
    batch_plan_parser = subparsers.add_parser(
        "batch-plan",
        help="Preview a batch plan through a running local API server without enqueueing.",
    )
    _add_api_request_args(batch_plan_parser)
    batch_plan_parser.add_argument(
        "--check-comfyui-connection",
        action="store_true",
        help="Ask the server to ping ComfyUI while planning.",
    )
    batch_parser = subparsers.add_parser(
        "batch",
        help="Create a batch through a running local API server.",
    )
    _add_api_request_args(batch_parser)
    _add_preflight_args(batch_parser)
    export_parser = subparsers.add_parser(
        "export-batch",
        help="Export a completed batch through a running local API server.",
    )
    export_parser.add_argument("--server", default="http://127.0.0.1:8891", help="Relief Story Agent API base URL.")
    export_parser.add_argument("--batch-id", required=True, help="Batch id to export.")
    export_parser.add_argument("--export-root", default="", help="Optional export root.")
    export_parser.add_argument("--include-zip", action="store_true", help="Create a zip export.")
    export_parser.add_argument("--timeout-seconds", type=float, default=60, help="HTTP timeout.")
    export_parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")
    recovery_plan_parser = subparsers.add_parser(
        "recovery-plan",
        help="Fetch a batch recovery plan through a running local API server.",
    )
    _add_batch_id_api_args(recovery_plan_parser)
    recover_parser = subparsers.add_parser(
        "recover-batch",
        help="Execute or dry-run safe batch recovery actions through the local API server.",
    )
    _add_batch_id_api_args(recover_parser)
    recover_parser.add_argument("--dry-run", action="store_true", help="Preview recovery actions without executing.")
    recover_parser.add_argument(
        "--action-code",
        action="append",
        default=[],
        help="Restrict recovery to one action code. Repeat for multiple codes.",
    )
    run_status_parser = subparsers.add_parser(
        "run-status",
        help="Fetch one run's current state through the local API server.",
    )
    _add_run_id_api_args(run_status_parser)
    runs_parser = subparsers.add_parser(
        "runs",
        help="List runs through the local API server.",
    )
    _add_api_base_args(runs_parser)
    runs_parser.add_argument("--status", default="", help="Optional run status filter.")
    runs_parser.add_argument("--parent-batch-id", default="", help="Optional parent batch id filter.")
    runs_parser.add_argument("--limit", type=int, default=50, help="Maximum run records to return.")
    batch_status_parser = subparsers.add_parser(
        "batch-status",
        help="Fetch one batch's current state through the local API server.",
    )
    _add_batch_id_api_args(batch_status_parser)
    batches_parser = subparsers.add_parser(
        "batches",
        help="List batches through the local API server.",
    )
    _add_api_base_args(batches_parser)
    batches_parser.add_argument("--status", default="", help="Optional batch status filter.")
    batches_parser.add_argument("--limit", type=int, default=50, help="Maximum batch records to return.")
    scheduler_parser = subparsers.add_parser(
        "scheduler",
        help="Fetch local scheduler queue and worker status.",
    )
    _add_api_base_args(scheduler_parser)
    run_events_parser = subparsers.add_parser(
        "run-events",
        help="Fetch one run's persisted event stream through the local API server.",
    )
    _add_run_id_api_args(run_events_parser)
    run_events_parser.add_argument("--after", type=int, default=0, help="Only return events after this sequence.")
    run_artifacts_parser = subparsers.add_parser(
        "run-artifacts",
        help="Fetch one run's artifact index through the local API server.",
    )
    _add_run_id_api_args(run_artifacts_parser)
    run_timeline_parser = subparsers.add_parser(
        "run-timeline",
        help="Fetch one run's UI-friendly stage timeline through the local API server.",
    )
    _add_run_id_api_args(run_timeline_parser)
    run_audit_parser = subparsers.add_parser(
        "run-audit",
        help="Audit one run's event stream and state consistency.",
    )
    _add_run_id_api_args(run_audit_parser)
    batch_artifacts_parser = subparsers.add_parser(
        "batch-artifacts",
        help="Fetch one batch's artifact index through the local API server.",
    )
    _add_batch_id_api_args(batch_artifacts_parser)
    batch_timeline_parser = subparsers.add_parser(
        "batch-timeline",
        help="Fetch one batch's UI-friendly progress timeline through the local API server.",
    )
    _add_batch_id_api_args(batch_timeline_parser)
    batch_health_parser = subparsers.add_parser(
        "batch-health",
        help="Fetch one batch's health report through the local API server.",
    )
    _add_batch_id_api_args(batch_health_parser)
    validate_export_parser = subparsers.add_parser(
        "validate-export",
        help="Validate a batch export directory through the local API server.",
    )
    _add_batch_id_api_args(validate_export_parser)
    validate_export_parser.add_argument("--export-dir", required=True, help="Export directory to validate.")
    validate_export_parser.add_argument("--save-report", action="store_true", help="Write validation_report.json.")
    validate_zip_parser = subparsers.add_parser(
        "validate-export-zip",
        help="Validate a batch export zip through the local API server.",
    )
    _add_batch_id_api_args(validate_zip_parser)
    validate_zip_parser.add_argument("--zip-path", required=True, help="Zip path to validate.")
    validate_zip_parser.add_argument("--expected-sha256", default="", help="Optional expected sha256.")
    validate_zip_parser.add_argument("--expected-size-bytes", type=int, default=0, help="Optional expected size.")
    validate_zip_parser.add_argument("--save-report", action="store_true", help="Write a validation sidecar report.")
    setup_parser = subparsers.add_parser(
        "setup",
        help="Write a local configuration bundle for first-run deployment.",
    )
    setup_parser.add_argument("--output-dir", required=True, help="Directory to write local config files.")
    setup_parser.add_argument("--workflow-path", required=True, help="Local ComfyUI workflow JSON path.")
    setup_parser.add_argument("--comfyui-endpoint", default="http://127.0.0.1:8188", help="ComfyUI base URL.")
    setup_parser.add_argument("--output-root", default="D:/relief_story_runs", help="Directory for generated runs.")
    setup_parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")
    acceptance_parser = subparsers.add_parser(
        "acceptance",
        help="Write a local acceptance evidence report.",
    )
    acceptance_parser.add_argument("--output-dir", required=True, help="Directory to write acceptance artifacts.")
    acceptance_parser.add_argument("--mode", default="manual", help="Acceptance mode, for example smoke or batch.")
    acceptance_parser.add_argument("--status", default="manual_pending", help="Overall acceptance status.")
    acceptance_parser.add_argument("--run-id", default="", help="Optional run id under review.")
    acceptance_parser.add_argument("--batch-id", default="", help="Optional batch id under review.")
    acceptance_parser.add_argument("--video-path", action="append", default=[], help="Verified local video path.")
    acceptance_parser.add_argument(
        "--check",
        action="append",
        default=[],
        help="Check in id=status[:evidence] format. Repeat for multiple checks.",
    )
    acceptance_parser.add_argument("--smoke-result", default="", help="Optional smoke_result.json path to import.")
    acceptance_parser.add_argument(
        "--include-default-matrix",
        action="store_true",
        help="Append missing standard acceptance checks as manual_pending.",
    )
    acceptance_parser.add_argument("--notes", default="", help="Free-form acceptance notes.")
    acceptance_parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")
    acceptance_status_parser = subparsers.add_parser(
        "acceptance-status",
        help="Read an acceptance_report.json and list missing release evidence.",
    )
    acceptance_status_parser.add_argument("--report", required=True, help="Path to acceptance_report.json.")
    acceptance_status_parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")
    local_acceptance_parser = subparsers.add_parser(
        "local-acceptance",
        help="Run compile/tests and optional ComfyUI smoke, then write acceptance artifacts.",
    )
    local_acceptance_parser.add_argument("--output-dir", required=True, help="Directory to write acceptance artifacts.")
    local_acceptance_parser.add_argument("--repo-root", default=".", help="Repository root for verification commands.")
    local_acceptance_parser.add_argument("--smoke-request", default="", help="Optional smoke_request.json to run.")
    local_acceptance_parser.add_argument("--model-config", default="", help="Optional model registry JSON to check.")
    local_acceptance_parser.add_argument("--run-request", default="", help="Optional run request JSON to diagnose.")
    local_acceptance_parser.add_argument("--batch-request", default="", help="Optional batch request JSON to diagnose.")
    local_acceptance_parser.add_argument(
        "--local-demo",
        action="store_true",
        help="Run the offline fake-model local demo and include its artifact summary.",
    )
    local_acceptance_parser.add_argument(
        "--local-demo-batch-size",
        type=int,
        default=2,
        help="Number of batch items to simulate when --local-demo is used.",
    )
    local_acceptance_parser.add_argument(
        "--smoke-dry-run",
        action="store_true",
        help="Force smoke-comfyui dry-run when --smoke-request is supplied.",
    )
    local_acceptance_parser.add_argument("--comfyui-output-prompt-id", default="", help="Optional ComfyUI prompt id to inspect with comfyui-outputs.")
    local_acceptance_parser.add_argument("--comfyui-output-endpoint", default="http://127.0.0.1:8188", help="ComfyUI endpoint for output inspection.")
    local_acceptance_parser.add_argument("--comfyui-output-artifact-dir", default="", help="Directory for downloaded ComfyUI output evidence.")
    local_acceptance_parser.add_argument("--comfyui-output-wait", action="store_true", help="Wait for ComfyUI output evidence before recording the check.")
    local_acceptance_parser.add_argument(
        "--no-comfyui-output-download",
        action="store_false",
        dest="comfyui_output_download",
        default=True,
        help="Record ComfyUI output readiness without downloading files.",
    )
    local_acceptance_parser.add_argument("--comfyui-output-timeout-seconds", type=float, default=600, help="Timeout for comfyui-outputs wait mode.")
    local_acceptance_parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=600,
        help="Timeout for each local verification command.",
    )
    local_acceptance_parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")

    args, rest = parser.parse_known_args(argv)
    if args.command == "serve":
        return server_main(rest)
    if args.command == "smoke-comfyui":
        return smoke_main(rest)
    if args.command == "connect-comfyui":
        return _connect_comfyui(args)
    if args.command == "discover-comfyui-workflows":
        return _discover_comfyui_workflows(args)
    if args.command == "comfyui-outputs":
        return _comfyui_outputs(args)
    if args.command == "diagnose":
        return _diagnose(args)
    if args.command == "pipeline-schema":
        return _pipeline_schema(args)
    if args.command == "template-check":
        return _template_check(args)
    if args.command == "model-check":
        return _model_check(args)
    if args.command == "local-bootstrap":
        return _local_bootstrap(args)
    if args.command == "local-doctor":
        return _local_doctor(args)
    if args.command == "local-readiness":
        return _local_readiness(args)
    if args.command == "local-demo":
        return _local_demo(args)
    if args.command == "run":
        return _create_run(args)
    if args.command == "batch-plan":
        return _plan_batch(args)
    if args.command == "batch":
        return _create_batch(args)
    if args.command == "export-batch":
        return _export_batch(args)
    if args.command == "recovery-plan":
        return _recovery_plan(args)
    if args.command == "recover-batch":
        return _recover_batch(args)
    if args.command == "run-status":
        return _run_status(args)
    if args.command == "runs":
        return _list_runs(args)
    if args.command == "batch-status":
        return _batch_status(args)
    if args.command == "batches":
        return _list_batches(args)
    if args.command == "scheduler":
        return _scheduler_status(args)
    if args.command == "run-events":
        return _run_events(args)
    if args.command == "run-artifacts":
        return _run_artifacts(args)
    if args.command == "run-timeline":
        return _run_timeline(args)
    if args.command == "run-audit":
        return _run_audit(args)
    if args.command == "batch-artifacts":
        return _batch_artifacts(args)
    if args.command == "batch-timeline":
        return _batch_timeline(args)
    if args.command == "batch-health":
        return _batch_health(args)
    if args.command == "validate-export":
        return _validate_export(args)
    if args.command == "validate-export-zip":
        return _validate_export_zip(args)
    if args.command == "setup":
        return _setup(args)
    if args.command == "acceptance":
        return _acceptance(args)
    if args.command == "acceptance-status":
        return _acceptance_status(args)
    if args.command == "local-acceptance":
        return _local_acceptance(args)
    if rest and rest[0].startswith("-"):
        return server_main(rest)
    parser.print_help()
    return 0


def _add_api_request_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--server", default="http://127.0.0.1:8891", help="Relief Story Agent API base URL.")
    parser.add_argument("--request", required=True, help="Request JSON file.")
    parser.add_argument("--timeout-seconds", type=float, default=60, help="HTTP timeout.")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")


def _add_preflight_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--preflight", action="store_true", help="Ask the server to validate before enqueueing.")
    parser.add_argument(
        "--check-comfyui-connection",
        action="store_true",
        help="Ask the server to ping ComfyUI during preflight.",
    )


def _add_batch_id_api_args(parser: argparse.ArgumentParser) -> None:
    _add_api_base_args(parser)
    parser.add_argument("--batch-id", required=True, help="Batch id.")


def _add_run_id_api_args(parser: argparse.ArgumentParser) -> None:
    _add_api_base_args(parser)
    parser.add_argument("--run-id", required=True, help="Run id.")


def _add_api_base_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--server", default="http://127.0.0.1:8891", help="Relief Story Agent API base URL.")
    parser.add_argument("--timeout-seconds", type=float, default=60, help="HTTP timeout.")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")


def _connect_comfyui(args: argparse.Namespace) -> int:
    payload: dict = {}
    if args.request:
        payload.update(json.loads(Path(args.request).read_text(encoding="utf-8")))
    if args.endpoint:
        payload["endpoint"] = args.endpoint
    if args.workflow_api_path:
        payload["workflow_api_path"] = args.workflow_api_path
    if args.timeout_seconds > 0:
        payload["timeout_seconds"] = args.timeout_seconds

    result = connect_comfyui(ComfyUIConnectionRequest.model_validate(payload))
    print(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2 if args.pretty else None,
        )
    )
    return 0 if result.get("ready") else 1


def _discover_comfyui_workflows(args: argparse.Namespace) -> int:
    request = ComfyUIWorkflowDiscoveryRequest(
        endpoint=args.endpoint,
        search_roots=args.search_root,
        max_results=args.max_results,
        filename_keywords=args.filename_keyword,
        include_unsupported=not args.hide_unsupported,
    )
    result = discover_workflows(
        request.search_roots,
        endpoint=request.endpoint,
        max_results=request.max_results,
        filename_keywords=request.filename_keywords,
        include_unsupported=request.include_unsupported,
    )
    print(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2 if args.pretty else None,
        )
    )
    return 0


def _comfyui_outputs(args: argparse.Namespace) -> int:
    payload: dict = {}
    if args.request:
        payload.update(json.loads(Path(args.request).read_text(encoding="utf-8")))
    if args.endpoint:
        payload["endpoint"] = args.endpoint
    if args.prompt_id:
        payload["prompt_ids"] = args.prompt_id
    if args.artifact_dir:
        payload["artifact_dir"] = args.artifact_dir
    if args.wait:
        payload["wait_for_completion"] = True
    if args.download:
        payload["download_outputs"] = True
    if args.timeout_seconds is not None:
        payload["output_timeout_seconds"] = args.timeout_seconds
    if args.poll_interval_seconds is not None:
        payload["output_poll_interval_seconds"] = args.poll_interval_seconds

    try:
        result = refresh_comfyui_prompt_outputs(
            ComfyUIOutputRefreshRequest.model_validate(payload)
        )
    except ValueError as exc:
        result = {
            "status": "invalid_request",
            "ready": False,
            "error": str(exc),
        }
        print(json.dumps(result, ensure_ascii=False, indent=2 if args.pretty else None))
        return 1

    print(json.dumps(result, ensure_ascii=False, indent=2 if args.pretty else None))
    return 0 if result.get("ready") else 1


def _diagnose(args: argparse.Namespace) -> int:
    payload = json.loads(Path(args.request).read_text(encoding="utf-8"))
    registry = (
        ModelConfigRegistry.from_file(args.model_config)
        if args.model_config
        else ModelConfigRegistry()
    )
    kind = _diagnose_kind(payload, args.kind)
    if kind == "batch":
        request = BatchRunRequest.model_validate(payload)
        result = diagnose_batch_configuration(
            request,
            registry,
            check_comfyui_connection=args.check_comfyui_connection,
        )
    else:
        request = RunRequest.model_validate(payload)
        result = diagnose_run_configuration(
            request,
            registry,
            check_comfyui_connection=args.check_comfyui_connection,
        )
    result = {"kind": kind, **result}
    print(json.dumps(result, ensure_ascii=False, indent=2 if args.pretty else None))
    return 0 if result.get("ready") else 1


def _diagnose_kind(payload: dict, requested_kind: str) -> str:
    if requested_kind in {"run", "batch"}:
        return requested_kind
    return "batch" if isinstance(payload.get("items"), list) else "run"


def _pipeline_schema(args: argparse.Namespace) -> int:
    print(json.dumps(build_pipeline_schema(), ensure_ascii=False, indent=2 if args.pretty else None))
    return 0


def _template_check(args: argparse.Namespace) -> int:
    checks = []
    if args.writer_template:
        checks.append(validate_prompt_template_file(args.writer_template, "writer"))
    if args.audit_template:
        checks.append(validate_prompt_template_file(args.audit_template, "audit"))
    result = {
        "ready": bool(checks) and all(check["status"] == "pass" for check in checks),
        "checks": checks,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2 if args.pretty else None))
    return 0 if result["ready"] else 1


def _model_check(args: argparse.Namespace) -> int:
    registry = ModelConfigRegistry.from_file(args.model_config)
    result = run_model_probe(
        registry,
        real_run=args.real_run,
        profile_names=args.profile or None,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2 if args.pretty else None))
    return 0 if result["ready"] else 1


def _local_bootstrap(args: argparse.Namespace) -> int:
    result = build_local_bootstrap(
        LocalRuntimeConfig(
            api_host=args.api_host,
            api_port=args.api_port,
            ui_origin=args.ui_origin,
            comfyui_endpoint=args.comfyui_endpoint,
            allowed_origins=args.cors_origin,
        )
    )
    print(json.dumps(result, ensure_ascii=False, indent=2 if args.pretty else None))
    return 0


def _local_doctor(args: argparse.Namespace) -> int:
    query: dict[str, str | int | bool] = {}
    if args.check_comfyui_connection:
        query["check_comfyui_connection"] = True
        if args.comfyui_endpoint:
            query["comfyui_endpoint"] = args.comfyui_endpoint
        if args.comfyui_workflow_path:
            query["comfyui_workflow_path"] = args.comfyui_workflow_path
        query["comfyui_timeout_seconds"] = args.comfyui_timeout_seconds
    return _get_json_command(args, "/api/local/doctor", query=query)


def _local_readiness(args: argparse.Namespace) -> int:
    query: dict[str, str | int | bool] = {}
    if args.acceptance_report:
        query["acceptance_report_path"] = args.acceptance_report
    if args.check_comfyui_connection:
        query["check_comfyui_connection"] = True
        if args.comfyui_endpoint:
            query["comfyui_endpoint"] = args.comfyui_endpoint
        if args.comfyui_workflow_path:
            query["comfyui_workflow_path"] = args.comfyui_workflow_path
        query["comfyui_timeout_seconds"] = args.comfyui_timeout_seconds
    return _get_json_command(args, "/api/local/readiness", query=query)


def _local_demo(args: argparse.Namespace) -> int:
    result = run_local_demo(args.output_dir, batch_size=args.batch_size)
    print(json.dumps(result, ensure_ascii=False, indent=2 if args.pretty else None))
    return 0 if result["status"] == "completed" else 1


def _create_run(args: argparse.Namespace) -> int:
    query = {
        "preflight": args.preflight,
        "check_comfyui_connection": args.check_comfyui_connection,
    }
    return _post_json_command(
        args,
        "/api/runs",
        _read_json_file(args.request),
        query={key: value for key, value in query.items() if value},
    )


def _plan_batch(args: argparse.Namespace) -> int:
    query = {"check_comfyui_connection": args.check_comfyui_connection}
    return _post_json_command(
        args,
        "/api/batches/plan",
        _read_json_file(args.request),
        query={key: value for key, value in query.items() if value},
    )


def _create_batch(args: argparse.Namespace) -> int:
    query = {
        "preflight": args.preflight,
        "check_comfyui_connection": args.check_comfyui_connection,
    }
    return _post_json_command(
        args,
        "/api/batches",
        _read_json_file(args.request),
        query={key: value for key, value in query.items() if value},
    )


def _export_batch(args: argparse.Namespace) -> int:
    payload = {"include_zip": args.include_zip}
    if args.export_root:
        payload["export_root"] = args.export_root
    return _post_json_command(
        args,
        f"/api/batches/{args.batch_id}/export",
        payload,
    )


def _recovery_plan(args: argparse.Namespace) -> int:
    return _get_json_command(args, f"/api/batches/{args.batch_id}/recovery-plan")


def _recover_batch(args: argparse.Namespace) -> int:
    payload = {"dry_run": args.dry_run}
    if args.action_code:
        payload["action_codes"] = args.action_code
    return _post_json_command(
        args,
        f"/api/batches/{args.batch_id}/recover",
        payload,
    )


def _run_status(args: argparse.Namespace) -> int:
    return _get_json_command(args, f"/api/runs/{args.run_id}")


def _list_runs(args: argparse.Namespace) -> int:
    query: dict[str, str | int] = {"limit": args.limit}
    if args.status:
        query["status"] = args.status
    if args.parent_batch_id:
        query["parent_batch_id"] = args.parent_batch_id
    return _get_json_command(args, "/api/runs", query=query)


def _batch_status(args: argparse.Namespace) -> int:
    return _get_json_command(args, f"/api/batches/{args.batch_id}")


def _list_batches(args: argparse.Namespace) -> int:
    query: dict[str, str | int] = {"limit": args.limit}
    if args.status:
        query["status"] = args.status
    return _get_json_command(args, "/api/batches", query=query)


def _scheduler_status(args: argparse.Namespace) -> int:
    return _get_json_command(args, "/api/scheduler")


def _run_events(args: argparse.Namespace) -> int:
    return _get_json_command(args, f"/api/runs/{args.run_id}/events", query={"after": args.after})


def _run_artifacts(args: argparse.Namespace) -> int:
    return _get_json_command(args, f"/api/runs/{args.run_id}/artifacts")


def _run_timeline(args: argparse.Namespace) -> int:
    return _get_json_command(args, f"/api/runs/{args.run_id}/timeline")


def _run_audit(args: argparse.Namespace) -> int:
    return _get_json_command(args, f"/api/runs/{args.run_id}/audit")


def _batch_artifacts(args: argparse.Namespace) -> int:
    return _get_json_command(args, f"/api/batches/{args.batch_id}/artifacts")


def _batch_timeline(args: argparse.Namespace) -> int:
    return _get_json_command(args, f"/api/batches/{args.batch_id}/timeline")


def _batch_health(args: argparse.Namespace) -> int:
    return _get_json_command(args, f"/api/batches/{args.batch_id}/health")


def _validate_export(args: argparse.Namespace) -> int:
    return _post_json_command(
        args,
        f"/api/batches/{args.batch_id}/export/validate",
        {
            "export_dir": args.export_dir,
            "save_report": args.save_report,
        },
        fail_when_invalid=True,
    )


def _validate_export_zip(args: argparse.Namespace) -> int:
    return _post_json_command(
        args,
        f"/api/batches/{args.batch_id}/export/validate-zip",
        {
            "zip_path": args.zip_path,
            "expected_sha256": args.expected_sha256,
            "expected_size_bytes": args.expected_size_bytes,
            "save_report": args.save_report,
        },
        fail_when_invalid=True,
    )


def _get_json_command(
    args: argparse.Namespace,
    path: str,
    *,
    query: dict[str, str | int | bool] | None = None,
) -> int:
    url = _api_url(args.server, path, query or {})
    with httpx.Client(timeout=args.timeout_seconds, trust_env=False) as client:
        response = client.get(url)
        result = response.json()
    return _print_api_result(args, response.status_code, result)


def _post_json_command(
    args: argparse.Namespace,
    path: str,
    payload: dict,
    *,
    query: dict[str, str | int | bool] | None = None,
    fail_when_invalid: bool = False,
) -> int:
    url = _api_url(args.server, path, query or {})
    with httpx.Client(timeout=args.timeout_seconds, trust_env=False) as client:
        response = client.post(url, json=payload)
        result = response.json()
    status_code = 400 if fail_when_invalid and result.get("valid") is False else response.status_code
    return _print_api_result(args, status_code, result)


def _print_api_result(args: argparse.Namespace, status_code: int, result: dict) -> int:
    print(json.dumps(result, ensure_ascii=False, indent=2 if args.pretty else None))
    return 1 if status_code >= 400 else 0


def _api_url(server: str, path: str, query: dict[str, str | int | bool]) -> str:
    base = server.rstrip("/")
    url = f"{base}{path}"
    if not query:
        return url
    encoded = {
        key: ("true" if value is True else "false" if value is False else str(value))
        for key, value in query.items()
    }
    return f"{url}?{urlencode(encoded)}"


def _read_json_file(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _setup(args: argparse.Namespace) -> int:
    result = write_local_config_bundle(
        args.output_dir,
        workflow_path=args.workflow_path,
        comfyui_endpoint=args.comfyui_endpoint,
        output_root=args.output_root,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2 if args.pretty else None))
    return 0


def _acceptance(args: argparse.Namespace) -> int:
    sources = {}
    if args.smoke_result:
        sources["smoke_result"] = args.smoke_result
    report_path = write_acceptance_report(
        args.output_dir,
        {
            "run_id": args.run_id,
            "batch_id": args.batch_id,
            "mode": args.mode,
            "status": args.status,
            "video_paths": args.video_path,
            "checks": [_parse_check_arg(value) for value in args.check],
            "sources": sources,
            "include_default_matrix": args.include_default_matrix,
            "notes": args.notes,
        },
    )
    result = {
        "acceptance_report": report_path,
        "markdown_report": str(Path(args.output_dir) / "ACCEPTANCE_REPORT.md"),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2 if args.pretty else None))
    return 0


def _acceptance_status(args: argparse.Namespace) -> int:
    result = build_acceptance_status(args.report)
    print(json.dumps(result, ensure_ascii=False, indent=2 if args.pretty else None))
    return 0 if result.get("ready_for_release") else 1


def _local_acceptance(args: argparse.Namespace) -> int:
    result = run_local_acceptance(
        args.output_dir,
        repo_root=args.repo_root,
        smoke_request=args.smoke_request,
        model_config=args.model_config,
        run_request=args.run_request,
        batch_request=args.batch_request,
        include_local_demo=args.local_demo,
        local_demo_batch_size=args.local_demo_batch_size,
        force_smoke_dry_run=args.smoke_dry_run,
        comfyui_output_prompt_id=args.comfyui_output_prompt_id,
        comfyui_output_endpoint=args.comfyui_output_endpoint,
        comfyui_output_artifact_dir=args.comfyui_output_artifact_dir,
        comfyui_output_wait=args.comfyui_output_wait,
        comfyui_output_download=args.comfyui_output_download,
        comfyui_output_timeout_seconds=args.comfyui_output_timeout_seconds,
        command_timeout_seconds=args.timeout_seconds,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2 if args.pretty else None))
    return 0 if result.get("status") == "completed" else 1


def _parse_check_arg(value: str) -> dict[str, str]:
    if "=" not in value:
        raise ValueError("--check must use id=status[:evidence] format")
    check_id, remainder = value.split("=", 1)
    status, evidence = (remainder.split(":", 1) + [""])[:2] if ":" in remainder else (remainder, "")
    return {
        "id": check_id,
        "status": status,
        "evidence": evidence,
    }


if __name__ == "__main__":
    raise SystemExit(main())
