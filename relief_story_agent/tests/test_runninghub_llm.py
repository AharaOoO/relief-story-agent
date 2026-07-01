from __future__ import annotations

from types import SimpleNamespace

import pytest

from relief_story_agent.model_runtime import ModelCallExecutor
from relief_story_agent.models import StageModelConfig
from relief_story_agent.runninghub_llm import RunningHubLLMProvider


def test_runninghub_llm_uses_site_key_and_parses_fenced_json(monkeypatch):
    captured = {}
    monkeypatch.setenv("RUNNINGHUB_CN_API_KEY", "cn-secret")
    response = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    content='```json\n{"passed": true, "issues": []}\n```'
                )
            )
        ],
        usage=SimpleNamespace(prompt_tokens=20, completion_tokens=8, total_tokens=28),
        model="deepseek/deepseek-v4-pro",
        _request_id="req_rh_cn",
    )

    class FakeCompletions:
        def create(self, **kwargs):
            captured["request"] = kwargs
            return response

    class FakeOpenAI:
        def __init__(self, **kwargs):
            captured["client"] = kwargs
            self.chat = SimpleNamespace(completions=FakeCompletions())

    monkeypatch.setattr("relief_story_agent.runninghub_llm.OpenAI", FakeOpenAI)
    provider = RunningHubLLMProvider()
    config = StageModelConfig(
        provider_mode="runninghub",
        runninghub_site="cn",
        model="deepseek/deepseek-v4-pro",
    )

    result = provider.generate_json("quality_gate", "Audit this script", config)

    assert captured["client"]["base_url"] == "https://llm.runninghub.cn/v1"
    assert captured["client"]["api_key"] == "cn-secret"
    assert captured["client"]["max_retries"] == 0
    assert captured["request"]["model"] == "deepseek/deepseek-v4-pro"
    assert result.payload == {"passed": True, "issues": []}
    assert result.request_id == "req_rh_cn"
    assert result.usage.total_tokens == 28


def test_runninghub_llm_rejects_a_model_not_curated_for_the_stage(monkeypatch):
    monkeypatch.setenv("RUNNINGHUB_AI_API_KEY", "ai-secret")
    provider = RunningHubLLMProvider()
    config = StageModelConfig(
        provider_mode="runninghub",
        runninghub_site="ai",
        model="google/gemini-3.5-flash",
    )

    with pytest.raises(ValueError, match="not available.*quality_gate"):
        provider.generate_json("quality_gate", "Audit", config)


def test_runninghub_llm_explains_enterprise_shared_key_requirement(monkeypatch):
    monkeypatch.setenv("RUNNINGHUB_AI_API_KEY", "consumer-key")

    class FakeRunningHubAuthError(Exception):
        status_code = 401

        def __str__(self):
            return (
                "Error code: 401 - {'error': {'message': "
                "'only SHARED (enterprise) api keys are accepted', "
                "'type': 'invalid_request_error', "
                "'code': 'auth_apikey_type_forbidden'}}"
            )

    class FakeCompletions:
        def create(self, **kwargs):
            raise FakeRunningHubAuthError()

    class FakeOpenAI:
        def __init__(self, **kwargs):
            self.chat = SimpleNamespace(completions=FakeCompletions())

    monkeypatch.setattr("relief_story_agent.runninghub_llm.OpenAI", FakeOpenAI)
    provider = RunningHubLLMProvider()

    with pytest.raises(ValueError, match="企业共享 API Key"):
        provider.generate_json(
            "chief_screenwriter",
            "Write a story",
            StageModelConfig(
                provider_mode="runninghub",
                runninghub_site="ai",
                model="google/gemini-3.5-flash",
            ),
        )


def test_model_executor_routes_runninghub_without_calling_default_provider():
    class DefaultProvider:
        def generate_json(self, stage, prompt, config=None):
            raise AssertionError("default provider must not receive RunningHub config")

    class RunningHubProvider:
        def __init__(self):
            self.calls = []

        def generate_json(self, stage, prompt, config=None):
            self.calls.append((stage, prompt, config.model))
            return {"ok": True}

    runninghub = RunningHubProvider()
    executor = ModelCallExecutor(
        DefaultProvider(),
        runninghub_provider=runninghub,
    )

    result = executor.execute(
        stage="gpt_prompt_writer",
        prompt="Build shots",
        config=StageModelConfig(
            provider_mode="runninghub",
            runninghub_site="ai",
            model="openai/gpt-5.5",
            max_attempts=1,
        ),
    )

    assert result.payload == {"ok": True}
    assert runninghub.calls == [
        ("gpt_prompt_writer", "Build shots", "openai/gpt-5.5")
    ]
