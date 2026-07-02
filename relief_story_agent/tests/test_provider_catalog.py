from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from relief_story_agent.api import create_app
from relief_story_agent.models import GridImageConfig, StageModelConfig
from relief_story_agent.orchestrator import StoryRunOrchestrator
from relief_story_agent.provider_catalog import (
    RUNNINGHUB_BASE_URLS,
    get_available_models,
    get_recommended_models,
    validate_runninghub_model,
)
from relief_story_agent.providers import FakeModelProvider


def test_runninghub_sites_use_distinct_official_base_urls():
    assert RUNNINGHUB_BASE_URLS == {
        "cn": "https://llm.runninghub.cn/v1",
        "ai": "https://llm.runninghub.ai/v1",
    }


def test_provider_catalog_exposes_complete_official_snapshots():
    domestic = get_available_models("cn")
    international = get_available_models("ai")

    assert len(domestic) == 20
    assert len(international) == 42
    assert "anthropic/claude-sonnet-5" not in domestic
    assert "anthropic/claude-sonnet-5" in international
    assert "minimax/minimax-m2.7" in domestic


def test_quality_gate_has_a_curated_model_for_each_runninghub_site():
    assert get_recommended_models("cn", "quality_gate") == (
        "deepseek/deepseek-v4-flash",
        "deepseek/deepseek-v4-pro",
    )
    assert get_recommended_models("ai", "quality_gate") == (
        "deepseek/deepseek-v4-flash",
        "openai/gpt-5.5",
    )


def test_catalog_rejects_unknown_stage_and_cross_site_model():
    with pytest.raises(ValueError, match="Unsupported model stage"):
        get_recommended_models("cn", "not-a-stage")

    with pytest.raises(ValueError, match="not available"):
        validate_runninghub_model(
            site="cn",
            stage="chief_screenwriter",
            model="google/gemini-3.5-flash",
        )


@pytest.mark.parametrize(
    "stage",
    [
        "chief_screenwriter",
        "deepseek_polish",
        "quality_gate",
        "gpt_prompt_writer",
        "gpt_prompt_audit",
        "gpt_prompt_reviser",
    ],
)
def test_any_site_model_is_allowed_for_every_model_stage(stage):
    assert validate_runninghub_model(
        site="cn",
        stage=stage,
        model="minimax/minimax-m2.7",
    ) == "minimax/minimax-m2.7"
    assert validate_runninghub_model(
        site="ai",
        stage=stage,
        model="anthropic/claude-sonnet-5",
    ) == "anthropic/claude-sonnet-5"


def test_stage_model_config_validates_runninghub_site_and_catalog():
    config = StageModelConfig(
        provider_mode="runninghub",
        runninghub_site="ai",
        model="google/gemini-3.5-flash",
    )

    assert config.base_url == "https://llm.runninghub.ai/v1"
    assert config.api_key_env == "RUNNINGHUB_AI_SHARED_API_KEY"
    assert config.timeout_seconds == 300

    with pytest.raises(ValidationError, match="not available"):
        StageModelConfig(
            provider_mode="runninghub",
            runninghub_site="cn",
            model="google/gemini-3.5-flash",
        )


def test_runninghub_model_preserves_an_explicit_timeout_override():
    config = StageModelConfig(
        provider_mode="runninghub",
        runninghub_site="cn",
        model="qwen/qwen3.7-plus",
        timeout_seconds=420,
    )

    assert config.timeout_seconds == 420


def test_runninghub_image_keeps_consumer_task_api_key():
    config = GridImageConfig(
        provider="runninghub_image_task",
        runninghub_site="ai",
        model="rhart-image-g-2",
    )

    assert config.api_key_env == "RUNNINGHUB_AI_API_KEY"


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
    assert body["cn"]["snapshot_date"] == "2026-07-02"
    assert len(body["cn"]["models"]) == 20
    assert len(body["ai"]["models"]) == 42
    assert body["cn"]["recommended_by_stage"]["chief_screenwriter"] == [
        "qwen/qwen3.7-plus",
        "qwen/qwen3.7-max",
    ]
    assert body["ai"]["recommended_by_stage"]["chief_screenwriter"] == [
        "google/gemini-3.5-flash",
        "anthropic/claude-sonnet-5",
    ]
