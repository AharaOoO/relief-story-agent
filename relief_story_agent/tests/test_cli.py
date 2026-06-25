from __future__ import annotations

import subprocess
import sys
import tomllib
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_cli_help_lists_core_local_commands():
    completed = subprocess.run(
        [sys.executable, "-m", "relief_story_agent.cli", "--help"],
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert completed.returncode == 0
    assert "serve" in completed.stdout
    assert "smoke-comfyui" in completed.stdout
    assert "connect-comfyui" in completed.stdout
    assert "setup" in completed.stdout
    assert "acceptance" in completed.stdout


def test_console_script_points_to_unified_cli():
    pyproject = tomllib.loads((PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8"))

    assert pyproject["project"]["scripts"]["relief-story-agent"] == "relief_story_agent.cli:main"
