from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from relief_story_agent.api import create_app
from relief_story_agent.model_config import ModelConfigRegistry
from relief_story_agent.models import RunRequest, RunState, StageModelConfig
from relief_story_agent.orchestrator import InMemoryRunStore, StoryRunOrchestrator
from relief_story_agent.providers import FakeModelProvider, OpenAICompatibleProvider
from relief_story_agent.storage import JsonFileRunStore


def _write_registry(tmp_path, payload):
    path = tmp_path / "models.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def _registry_payload():
    return {
        "profiles": {
            "gemini_writer": {
                "base_url": "https://gemini.example/v1",
                "api_key_env": "GEMINI_API_KEY",
                "model": "gemini-pro",
                "temperature": 0.7,
                "max_attempts": 4,
            },
            "deepseek_editor": {
                "base_url": "https://deepseek.example/v1",
                "api_key_env": "DEEPSEEK_API_KEY",
                "model": "deepseek-v4-pro",
            },
            "gpt_visual": {
                "base_url": "https://gpt.example/v1",
                "api_key_env": "OPENAI_API_KEY",
                "model": "gpt-image2-compatible",
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


def test_api_key_is_excluded_from_nested_api_and_persistent_state(tmp_path):
    secret = "sk-never-persist-this"
    request = RunRequest(
        idea="密钥脱敏",
        approval_mode="manual",
        model_configs={
            "chief_screenwriter": StageModelConfig(
                model="temporary-model",
                api_key=secret,
            )
        },
    )
    run = RunState(run_id="run_secret", request=request)

    assert secret not in json.dumps(run.model_dump(), ensure_ascii=False)
    assert "api_key" not in run.model_dump()["request"]["model_configs"]["chief_screenwriter"]

    store = JsonFileRunStore(tmp_path / "state")
    store.save(run)
    raw = (tmp_path / "state" / "runs" / "run_secret.json").read_text(encoding="utf-8")
    assert secret not in raw
    assert '"api_key"' not in raw
    assert store.get("run_secret").request.model_configs["chief_screenwriter"].api_key == ""


def test_registry_loads_profiles_and_merges_only_explicit_request_overrides(tmp_path):
    registry = ModelConfigRegistry.from_file(_write_registry(tmp_path, _registry_payload()))
    inline = StageModelConfig(temperature=0.25, timeout_seconds=120)

    resolved = registry.resolve(
        "chief_screenwriter",
        inline=inline,
    )

    assert resolved is not None
    assert resolved.model == "gemini-pro"
    assert resolved.base_url == "https://gemini.example/v1"
    assert resolved.api_key_env == "GEMINI_API_KEY"
    assert resolved.temperature == 0.25
    assert resolved.timeout_seconds == 120
    assert resolved.max_attempts == 4


def test_registry_supports_per_run_profile_override(tmp_path):
    registry = ModelConfigRegistry.from_file(_write_registry(tmp_path, _registry_payload()))

    resolved = registry.resolve(
        "chief_screenwriter",
        profile_override="gpt_visual",
    )

    assert resolved is not None
    assert resolved.model == "gpt-image2-compatible"
    assert resolved.api_key_env == "OPENAI_API_KEY"


def test_registry_rejects_plaintext_api_keys_in_config_file(tmp_path):
    payload = _registry_payload()
    payload["profiles"]["gemini_writer"]["api_key"] = "sk-plain-text"

    with pytest.raises(ValueError, match="api_key_env"):
        ModelConfigRegistry.from_file(_write_registry(tmp_path, payload))


def test_registry_rejects_stage_binding_to_missing_profile(tmp_path):
    payload = _registry_payload()
    payload["stages"]["chief_screenwriter"] = "does_not_exist"

    with pytest.raises(ValueError, match="does_not_exist"):
        ModelConfigRegistry.from_file(_write_registry(tmp_path, payload))


def test_provider_resolves_api_key_from_environment_without_exposing_it(monkeypatch):
    captured = {}
    monkeypatch.setenv("GEMINI_API_KEY", "env-secret-value")
    response = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content='{"ok": true}'))],
        usage=None,
        model="gemini-pro",
        _request_id="req_env",
    )

    class FakeCompletions:
        def create(self, **kwargs):
            return response

    class FakeOpenAI:
        def __init__(self, **kwargs):
            captured.update(kwargs)
            self.chat = SimpleNamespace(completions=FakeCompletions())

    monkeypatch.setattr("relief_story_agent.providers.OpenAI", FakeOpenAI)
    provider = OpenAICompatibleProvider()
    config = StageModelConfig(
        base_url="https://gemini.example/v1",
        api_key_env="GEMINI_API_KEY",
        model="gemini-pro",
    )

    provider.generate_json("chief_screenwriter", "prompt", config)

    assert captured["api_key"] == "env-secret-value"
    assert "env-secret-value" not in repr(config)
    assert "env-secret-value" not in json.dumps(config.model_dump())


def test_provider_fails_clearly_when_referenced_environment_secret_is_missing(monkeypatch):
    monkeypatch.delenv("MISSING_MODEL_KEY", raising=False)
    provider = OpenAICompatibleProvider()

    with pytest.raises(ValueError, match="MISSING_MODEL_KEY"):
        provider.generate_json(
            "chief_screenwriter",
            "prompt",
            StageModelConfig(
                api_key_env="MISSING_MODEL_KEY",
                model="gemini-pro",
            ),
        )


def test_config_status_api_exposes_bindings_but_not_secret_values(tmp_path, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "gemini-secret")
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "openai-secret")
    registry = ModelConfigRegistry.from_file(_write_registry(tmp_path, _registry_payload()))
    orchestrator = StoryRunOrchestrator(
        provider=FakeModelProvider.minimal_success(),
        store=InMemoryRunStore(),
        model_registry=registry,
    )
    client = TestClient(create_app(orchestrator))

    response = client.get("/api/config/models")

    assert response.status_code == 200
    body = response.json()
    serialized = json.dumps(body)
    assert body["stages"]["chief_screenwriter"] == "gemini_writer"
    assert body["profiles"]["gemini_writer"]["secret_configured"] is True
    assert body["profiles"]["deepseek_editor"]["secret_configured"] is False
    assert body["missing_environment_variables"] == ["DEEPSEEK_API_KEY"]
    assert "gemini-secret" not in serialized
    assert "openai-secret" not in serialized
    assert '"api_key":' not in serialized
