from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from relief_story_agent.api import create_app
from relief_story_agent.models import StageModelConfig
from relief_story_agent.orchestrator import StoryRunOrchestrator
from relief_story_agent.provider_catalog import (
    RUNNINGHUB_BASE_URLS,
    get_curated_models,
    validate_runninghub_model,
)
from relief_story_agent.providers import FakeModelProvider


def test_runninghub_sites_use_distinct_official_base_urls():
    assert RUNNINGHUB_BASE_URLS == {
        "cn": "https://llm.runninghub.cn/v1",
        "ai": "https://llm.runninghub.ai/v1",
    }


def test_domestic_and_international_catalogs_do_not_cross_mix():
    domestic = get_curated_models("cn", "chief_screenwriter")
    international = get_curated_models("ai", "chief_screenwriter")

    assert domestic == ("qwen/qwen3.7-plus", "qwen/qwen3.7-max")
    assert international == ("google/gemini-3.5-flash",)
    assert set(domestic).isdisjoint(international)


def test_quality_gate_has_a_curated_model_for_each_runninghub_site():
    assert get_curated_models("cn", "quality_gate") == (
        "deepseek/deepseek-v4-pro",
        "deepseek/deepseek-v4-flash",
    )
    assert get_curated_models("ai", "quality_gate") == (
        "deepseek/deepseek-v4-pro",
        "openai/gpt-5.5",
    )


def test_catalog_rejects_unknown_stage_and_cross_site_model():
    with pytest.raises(ValueError, match="Unsupported model stage"):
        get_curated_models("cn", "not-a-stage")

    with pytest.raises(ValueError, match="not available"):
        validate_runninghub_model(
            site="cn",
            stage="chief_screenwriter",
            model="google/gemini-3.5-flash",
        )


def test_stage_model_config_validates_runninghub_site_and_catalog():
    config = StageModelConfig(
        provider_mode="runninghub",
        runninghub_site="ai",
        model="google/gemini-3.5-flash",
    )

    assert config.base_url == "https://llm.runninghub.ai/v1"
    assert config.api_key_env == "RUNNINGHUB_AI_API_KEY"

    with pytest.raises(ValidationError, match="not available"):
        StageModelConfig(
            provider_mode="runninghub",
            runninghub_site="cn",
            model="google/gemini-3.5-flash",
        )


def test_provider_catalog_api_is_the_frontend_source_of_truth():
    client = TestClient(
        create_app(
            StoryRunOrchestrator(provider=FakeModelProvider.minimal_success())
        )
    )

    response = client.get("/api/config/provider-catalog")

    assert response.status_code == 200
    body = response.json()["runninghub"]
    assert body["cn"]["base_url"] == "https://llm.runninghub.cn/v1"
    assert body["ai"]["base_url"] == "https://llm.runninghub.ai/v1"
    assert body["cn"]["stages"]["chief_screenwriter"] == [
        "qwen/qwen3.7-plus",
        "qwen/qwen3.7-max",
    ]
    assert body["ai"]["stages"]["chief_screenwriter"] == [
        "google/gemini-3.5-flash"
    ]
