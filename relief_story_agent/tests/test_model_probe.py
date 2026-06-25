from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from fastapi.testclient import TestClient

from relief_story_agent.api import create_app
from relief_story_agent.model_config import ModelConfigRegistry
from relief_story_agent.model_probe import run_model_probe
from relief_story_agent.models import ModelCallResult, ModelUsage
from relief_story_agent.orchestrator import InMemoryRunStore, StoryRunOrchestrator
from relief_story_agent.providers import FakeModelProvider


class RecordingProbeProvider:
    def __init__(self):
        self.calls: list[tuple[str, str]] = []

    def generate_json(self, stage, prompt, config=None):
        self.calls.append((stage, config.model if config else ""))
        return ModelCallResult(
            payload={"ok": True, "stage": stage},
            model=config.model if config else "unknown",
            request_id=f"req_{stage}",
            usage=ModelUsage(prompt_tokens=3, completion_tokens=4, total_tokens=7),
        )


def _registry(tmp_path: Path, environ: dict[str, str] | None = None) -> ModelConfigRegistry:
    path = tmp_path / "models.json"
    path.write_text(
        json.dumps(
            {
                "profiles": {
                    "gemini_writer": {
                        "base_url": "https://gemini.example/v1",
                        "api_key_env": "GEMINI_API_KEY",
                        "model": "gemini-pro",
                    },
                    "deepseek_editor": {
                        "base_url": "https://deepseek.example/v1",
                        "api_key_env": "DEEPSEEK_API_KEY",
                        "model": "deepseek-chat",
                    },
                    "gpt_visual": {
                        "base_url": "https://api.openai.com/v1",
                        "api_key_env": "OPENAI_API_KEY",
                        "model": "gpt-json",
                    },
                },
                "stages": {
                    "chief_screenwriter": "gemini_writer",
                    "deepseek_polish": "deepseek_editor",
                    "gpt_prompt_writer": "gpt_visual",
                    "gpt_prompt_audit": "gpt_visual",
                    "gpt_prompt_reviser": "gpt_visual",
                },
            }
        ),
        encoding="utf-8",
    )
    return ModelConfigRegistry.from_file(path, environ=environ or {})


def test_model_probe_dry_run_reports_secret_readiness_without_calling_provider(tmp_path):
    provider = RecordingProbeProvider()
    result = run_model_probe(
        _registry(tmp_path, {"GEMINI_API_KEY": "ok", "OPENAI_API_KEY": "ok"}),
        provider=provider,
        real_run=False,
    )

    checks = {check["profile"]: check for check in result["checks"]}
    assert result["ready"] is False
    assert provider.calls == []
    assert checks["gemini_writer"]["status"] == "pass"
    assert checks["deepseek_editor"]["status"] == "fail"
    assert checks["deepseek_editor"]["message"] == "Missing environment variable: DEEPSEEK_API_KEY"
    assert checks["gpt_visual"]["secret_configured"] is True
    assert "ok" not in json.dumps(result)


def test_model_probe_rejects_placeholder_model_settings(tmp_path):
    path = tmp_path / "models.json"
    path.write_text(
        json.dumps(
            {
                "profiles": {
                    "gemini_writer": {
                        "base_url": "https://YOUR_GEMINI_OPENAI_COMPATIBLE_ENDPOINT/v1",
                        "api_key_env": "GEMINI_API_KEY",
                        "model": "YOUR_GEMINI_MODEL",
                    }
                },
                "stages": {"chief_screenwriter": "gemini_writer"},
            }
        ),
        encoding="utf-8",
    )
    registry = ModelConfigRegistry.from_file(path, environ={"GEMINI_API_KEY": "ok"})

    result = run_model_probe(registry, real_run=False)

    assert result["ready"] is False
    assert result["checks"][0]["status"] == "fail"
    assert result["checks"][0]["message"] == "Replace placeholder model/base_url values before probing."


def test_model_probe_real_run_calls_each_ready_profile_once(tmp_path):
    provider = RecordingProbeProvider()
    result = run_model_probe(
        _registry(
            tmp_path,
            {
                "GEMINI_API_KEY": "gemini",
                "DEEPSEEK_API_KEY": "deepseek",
                "OPENAI_API_KEY": "openai",
            },
        ),
        provider=provider,
        real_run=True,
    )

    assert result["ready"] is True
    assert provider.calls == [
        ("model_probe.gemini_writer", "gemini-pro"),
        ("model_probe.deepseek_editor", "deepseek-chat"),
        ("model_probe.gpt_visual", "gpt-json"),
    ]
    assert result["checks"][0]["request_id"] == "req_model_probe.gemini_writer"
    assert result["checks"][0]["usage"]["total_tokens"] == 7


def test_api_model_check_uses_server_model_registry(tmp_path):
    registry = _registry(
        tmp_path,
        {"GEMINI_API_KEY": "gemini", "DEEPSEEK_API_KEY": "deepseek", "OPENAI_API_KEY": "openai"},
    )
    orchestrator = StoryRunOrchestrator(
        provider=FakeModelProvider.minimal_success(),
        store=InMemoryRunStore(),
        model_registry=registry,
    )
    client = TestClient(create_app(orchestrator))

    response = client.post("/api/config/model-check", json={"real_run": False})

    assert response.status_code == 200
    body = response.json()
    assert body["ready"] is True
    assert [check["profile"] for check in body["checks"]] == [
        "gemini_writer",
        "deepseek_editor",
        "gpt_visual",
    ]


def test_cli_model_check_writes_machine_readable_output(tmp_path):
    config_path = tmp_path / "models.json"
    config_path.write_text(
        json.dumps(
            {
                "profiles": {
                    "local": {"base_url": "http://127.0.0.1:8045/v1", "model": "local-json"}
                },
                "stages": {"chief_screenwriter": "local"},
            }
        ),
        encoding="utf-8",
    )

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "relief_story_agent.cli",
            "model-check",
            "--model-config",
            str(config_path),
            "--pretty",
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert completed.returncode == 0
    body = json.loads(completed.stdout)
    assert body["ready"] is True
    assert body["checks"][0]["profile"] == "local"
