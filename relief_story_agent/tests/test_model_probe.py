from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from fastapi.testclient import TestClient

from relief_story_agent.api import create_app
from relief_story_agent.grid_image import GeneratedImage
from relief_story_agent.model_config import ModelConfigRegistry
from relief_story_agent.model_probe import run_model_probe
from relief_story_agent.models import GridImageConfig, ModelCallResult, ModelUsage
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


class RecordingImageProbeProvider:
    def __init__(self):
        self.calls: list[tuple[str, str]] = []

    def generate(self, *, prompt, config):
        self.calls.append((prompt, config.model))
        return GeneratedImage(
            content=b"fake-png-bytes",
            mime_type="image/png",
            provider=config.provider,
            model=config.model,
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


def test_model_probe_can_include_image_provider_real_probe(tmp_path):
    text_provider = RecordingProbeProvider()
    image_provider = RecordingImageProbeProvider()
    result = run_model_probe(
        _registry(
            tmp_path,
            {
                "GEMINI_API_KEY": "gemini",
                "DEEPSEEK_API_KEY": "deepseek",
                "OPENAI_API_KEY": "openai",
            },
        ),
        provider=text_provider,
        image_provider=image_provider,
        image_config=GridImageConfig(model="gpt-image-2", api_key_env="OPENAI_API_KEY"),
        real_run=True,
    )

    checks = {check["profile"]: check for check in result["checks"]}
    assert result["ready"] is True
    assert len(image_provider.calls) == 1
    assert "relief_story_agent_image_probe" in image_provider.calls[0][0]
    assert image_provider.calls[0][1] == "gpt-image-2"
    assert checks["image_provider"]["status"] == "pass"
    assert checks["image_provider"]["message"] == "Image provider probe succeeded."
    assert checks["image_provider"]["byte_size"] == len(b"fake-png-bytes")
    assert checks["image_provider"]["mime_type"] == "image/png"


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


def test_cli_model_check_reports_invalid_model_config_without_traceback(tmp_path):
    config_path = tmp_path / "models.json"
    config_path.write_text("{not valid json", encoding="utf-8")

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

    assert completed.returncode == 1
    assert "Traceback" not in completed.stderr
    body = json.loads(completed.stdout)
    assert body["status"] == "invalid_request"
    assert body["path"] == str(config_path)
    assert "Invalid model config" in body["error"]


def test_cli_model_check_can_include_run_request_image_provider(tmp_path):
    config_path = tmp_path / "models.json"
    config_path.write_text(
        json.dumps(
            {
                "profiles": {
                    "local": {
                        "base_url": "http://127.0.0.1:8045/v1",
                        "model": "local-json",
                        "api_key_env": "LOCAL_MODEL_KEY",
                    }
                },
                "stages": {"chief_screenwriter": "local"},
            }
        ),
        encoding="utf-8",
    )
    run_path = tmp_path / "run.json"
    run_path.write_text(
        json.dumps(
            {
                "idea": "probe image provider",
                "comfyui": {
                    "enabled": True,
                    "grid_image": {
                        "mode": "auto",
                        "base_url": "https://images.example/v1",
                        "api_key_env": "IMAGE_KEY",
                        "model": "image-probe-model",
                    },
                },
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
            "--run-request",
            str(run_path),
            "--pretty",
        ],
        env={**os.environ, "LOCAL_MODEL_KEY": "text", "IMAGE_KEY": "image"},
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert completed.returncode == 0
    body = json.loads(completed.stdout)
    checks = {check["profile"]: check for check in body["checks"]}
    assert body["ready"] is True
    assert checks["image_provider"]["status"] == "pass"
    assert checks["image_provider"]["model"] == "image-probe-model"
