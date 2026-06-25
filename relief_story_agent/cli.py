from __future__ import annotations

import argparse
import json
from pathlib import Path

from .comfyui import connect_comfyui
from .models import ComfyUIConnectionRequest
from .server import main as server_main
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

    args, rest = parser.parse_known_args(argv)
    if args.command == "serve":
        return server_main(rest)
    if args.command == "smoke-comfyui":
        return smoke_main(rest)
    if args.command == "connect-comfyui":
        return _connect_comfyui(args)
    if rest and rest[0].startswith("-"):
        return server_main(rest)
    parser.print_help()
    return 0


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


if __name__ == "__main__":
    raise SystemExit(main())
