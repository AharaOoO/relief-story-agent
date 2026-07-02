from __future__ import annotations

from typing import Literal


RunningHubSite = Literal["cn", "ai"]

RUNNINGHUB_BASE_URLS: dict[RunningHubSite, str] = {
    "cn": "https://llm.runninghub.cn/v1",
    "ai": "https://llm.runninghub.ai/v1",
}

RUNNINGHUB_TASK_API_KEY_ENVS: dict[RunningHubSite, str] = {
    "cn": "RUNNINGHUB_CN_API_KEY",
    "ai": "RUNNINGHUB_AI_API_KEY",
}

RUNNINGHUB_LLM_API_KEY_ENVS: dict[RunningHubSite, str] = {
    "cn": "RUNNINGHUB_CN_SHARED_API_KEY",
    "ai": "RUNNINGHUB_AI_SHARED_API_KEY",
}

RUNNINGHUB_WEB_BASE_URLS: dict[RunningHubSite, str] = {
    "cn": "https://www.runninghub.cn",
    "ai": "https://www.runninghub.ai",
}

RUNNINGHUB_MODEL_SOURCE_URLS: dict[RunningHubSite, str] = {
    "cn": "https://www.runninghub.cn/call-api/llm/models",
    "ai": "https://www.runninghub.ai/call-api/llm/models",
}

RUNNINGHUB_MODEL_SNAPSHOT_DATE = "2026-07-02"

RUNNINGHUB_MODELS: dict[RunningHubSite, tuple[str, ...]] = {
    "cn": (
        "glm-5.2",
        "glm-5.1",
        "glm-5-turbo",
        "glm-5",
        "qwen/qwen3.7-max",
        "glm-5v-turbo",
        "qwen/qwen3.7-plus",
        "deepseek/deepseek-v4-pro",
        "qwen/qwen3.6-plus",
        "bytedance/doubao-seed-evolving",
        "bytedance/doubao-seed-2.1-pro",
        "bytedance/doubao-seed-2.1-turbo",
        "bytedance/doubao-seed-2.0-pro",
        "bytedance/doubao-seed-2.0-code",
        "deepseek/deepseek-v4-flash",
        "qwen/qwen3.6-flash",
        "bytedance/doubao-seed-2.0-lite",
        "bytedance/doubao-seed-2.0-mini",
        "minimax/minimax-m2.7",
        "qwen/qwen3.6-max-preview",
    ),
    "ai": (
        "google/gemini-3.1-flash-lite-preview",
        "google/gemini-3.5-flash",
        "openai/gpt-5.5",
        "openai/gpt-5.5-pro",
        "openai/gpt-5.4-pro",
        "anthropic/claude-opus-4.8",
        "anthropic/claude-opus-4.7",
        "glm-5.2",
        "anthropic/claude-opus-4.6",
        "openai/gpt-5.4",
        "openai/gpt-5.3-codex",
        "glm-5.1",
        "glm-5-turbo",
        "anthropic/claude-sonnet-4.6",
        "glm-5",
        "anthropic/claude-sonnet-5",
        "qwen/qwen3.7-max",
        "glm-5v-turbo",
        "qwen/qwen3.7-plus",
        "deepseek/deepseek-v4-pro",
        "xai/grok-4.3",
        "qwen/qwen3.6-plus",
        "google/gemini-3.1-pro-preview",
        "bytedance/doubao-seed-evolving",
        "bytedance/doubao-seed-2.1-pro",
        "anthropic/claude-sonnet-4.5",
        "bytedance/doubao-seed-2.1-turbo",
        "anthropic/claude-opus-4.5",
        "bytedance/doubao-seed-2.0-pro",
        "bytedance/doubao-seed-2.0-code",
        "deepseek/deepseek-v4-flash",
        "qwen/qwen3.6-flash",
        "openai/gpt-5.4-mini",
        "openai/gpt-5.4-nano",
        "google/gemini-3-flash-preview",
        "google/gemini-2.5-flash",
        "bytedance/doubao-seed-2.0-lite",
        "bytedance/doubao-seed-2.0-mini",
        "minimax/minimax-m2.7",
        "anthropic/claude-haiku-4.5",
        "qwen/qwen3.6-max-preview",
        "google/gemini-2.5-pro",
    ),
}

RUNNINGHUB_RECOMMENDED_MODELS: dict[
    RunningHubSite, dict[str, tuple[str, ...]]
] = {
    "cn": {
        "chief_screenwriter": ("qwen/qwen3.7-plus", "qwen/qwen3.7-max"),
        "deepseek_polish": (
            "deepseek/deepseek-v4-pro",
            "deepseek/deepseek-v4-flash",
        ),
        "quality_gate": (
            "deepseek/deepseek-v4-flash",
            "deepseek/deepseek-v4-pro",
        ),
        "gpt_prompt_writer": ("qwen/qwen3.7-max", "qwen/qwen3.7-plus"),
        "gpt_prompt_audit": (
            "deepseek/deepseek-v4-pro",
            "deepseek/deepseek-v4-flash",
        ),
        "gpt_prompt_reviser": ("qwen/qwen3.7-plus", "qwen/qwen3.7-max"),
    },
    "ai": {
        "chief_screenwriter": (
            "google/gemini-3.5-flash",
            "anthropic/claude-sonnet-5",
        ),
        "deepseek_polish": (
            "deepseek/deepseek-v4-pro",
            "anthropic/claude-sonnet-5",
        ),
        "quality_gate": ("deepseek/deepseek-v4-flash", "openai/gpt-5.5"),
        "gpt_prompt_writer": ("openai/gpt-5.5", "google/gemini-3.5-flash"),
        "gpt_prompt_audit": (
            "openai/gpt-5.4-mini",
            "deepseek/deepseek-v4-pro",
        ),
        "gpt_prompt_reviser": ("openai/gpt-5.4-mini", "openai/gpt-5.5"),
    },
}


def get_available_models(site: RunningHubSite) -> tuple[str, ...]:
    try:
        return RUNNINGHUB_MODELS[site]
    except KeyError as exc:
        raise ValueError(f"Unsupported RunningHub site: {site}") from exc


def get_recommended_models(
    site: RunningHubSite,
    stage: str,
) -> tuple[str, ...]:
    try:
        site_catalog = RUNNINGHUB_RECOMMENDED_MODELS[site]
    except KeyError as exc:
        raise ValueError(f"Unsupported RunningHub site: {site}") from exc
    try:
        return site_catalog[stage]
    except KeyError as exc:
        raise ValueError(f"Unsupported model stage: {stage}") from exc


def validate_runninghub_model(
    *,
    site: RunningHubSite,
    model: str,
    stage: str | None = None,
) -> str:
    if stage is not None:
        get_recommended_models(site, stage)
    allowed = get_available_models(site)
    if model not in allowed:
        scope = f" for stage {stage}" if stage else ""
        raise ValueError(
            f"RunningHub model {model!r} is not available on site {site!r}{scope}"
        )
    return model


def build_provider_catalog() -> dict:
    return {
        "runninghub": {
            site: {
                "base_url": RUNNINGHUB_BASE_URLS[site],
                "api_key_env": RUNNINGHUB_LLM_API_KEY_ENVS[site],
                "source_url": RUNNINGHUB_MODEL_SOURCE_URLS[site],
                "snapshot_date": RUNNINGHUB_MODEL_SNAPSHOT_DATE,
                "models": list(get_available_models(site)),
                "recommended_by_stage": {
                    stage: list(models)
                    for stage, models in RUNNINGHUB_RECOMMENDED_MODELS[site].items()
                },
            }
            for site in RUNNINGHUB_MODELS
        }
    }
