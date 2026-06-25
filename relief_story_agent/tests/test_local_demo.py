from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from relief_story_agent.local_demo import run_local_demo


def test_run_local_demo_writes_single_and_batch_artifacts(tmp_path):
    result = run_local_demo(tmp_path, batch_size=2)

    assert result["status"] == "completed"
    assert result["mode"] == "offline_demo"
    assert result["external_calls"]["model_provider"] == "fake"
    assert result["external_calls"]["comfyui"] is False

    summary_path = Path(result["summary_path"])
    assert summary_path.exists()
    assert json.loads(summary_path.read_text(encoding="utf-8"))["status"] == "completed"

    single = result["single_run"]
    assert single["status"] == "completed"
    assert single["comfyui_prompt_ids"] == []
    single_artifact_dir = Path(single["artifact_dir"])
    assert (single_artifact_dir / "00_manifest.json").exists()
    assert (single_artifact_dir / "01_script.json").exists()
    assert (single_artifact_dir / "05_final_prompts.json").exists()

    batch = result["batch"]
    assert batch["status"] == "completed"
    assert batch["summary"]["total"] == 2
    assert batch["summary"]["completed"] == 2
    assert len(batch["items"]) == 2
    for item in batch["items"]:
        assert item["status"] == "completed"
        artifact_dir = Path(item["artifact_dir"])
        assert (artifact_dir / "00_manifest.json").exists()
        assert (artifact_dir / "05_final_prompts.json").exists()


def test_cli_local_demo_command_outputs_summary_json(tmp_path):
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "relief_story_agent.cli",
            "local-demo",
            "--output-dir",
            str(tmp_path),
            "--batch-size",
            "2",
            "--pretty",
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )

    assert completed.returncode == 0
    body = json.loads(completed.stdout)
    assert body["status"] == "completed"
    assert body["batch"]["summary"]["completed"] == 2
    assert Path(body["summary_path"]).exists()
