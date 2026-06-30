from __future__ import annotations

from typing import Literal


RunningHubSite = Literal["cn", "ai"]

RUNNINGHUB_BASE_URLS: dict[RunningHubSite, str] = {
    "cn": "https://llm.runninghub.cn/v1",
    "ai": "https://llm.runninghub.ai/v1",
}

RUNNINGHUB_API_KEY_ENVS: dict[RunningHubSite, str] = {
    "cn": "RUNNINGHUB_CN_API_KEY",
    "ai": "RUNNINGHUB_AI_API_KEY",
}

_CURATED_MODELS: dict[RunningHubSite, dict[str, tuple[str, ...]]] = {
    "cn": {
        "chief_screenwriter": ("qwen/qwen3.7-plus", "qwen/qwen3.7-max"),
        "deepseek_polish": (
            "deepseek/deepseek-v4-flash",
            "deepseek/deepseek-v4-pro",
        ),
        "quality_gate": (
            "deepseek/deepseek-v4-pro",
            "deepseek/deepseek-v4-flash",
        ),
        "gpt_prompt_writer": ("qwen/qwen3.7-max", "qwen/qwen3.7-plus"),
        "gpt_prompt_audit": (
            "deepseek/deepseek-v4-pro",
            "deepseek/deepseek-v4-flash",
        ),
        "gpt_prompt_reviser": ("qwen/qwen3.7-plus", "qwen/qwen3.7-max"),
    },
    "ai": {
        "chief_screenwriter": ("google/gemini-3.5-flash",),
        "deepseek_polish": ("deepseek/deepseek-v4-pro",),
        "quality_gate": ("deepseek/deepseek-v4-pro", "openai/gpt-5.5"),
        "gpt_prompt_writer": ("openai/gpt-5.5",),
        "gpt_prompt_audit": ("openai/gpt-5.4-mini", "openai/gpt-5.5"),
        "gpt_prompt_reviser": ("openai/gpt-5.4-mini", "openai/gpt-5.5"),
    },
}


def get_curated_models(site: RunningHubSite, stage: str) -> tuple[str, ...]:
    try:
        site_catalog = _CURATED_MODELS[site]
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
        allowed = get_curated_models(site, stage)
    else:
        try:
            stage_catalog = _CURATED_MODELS[site]
        except KeyError as exc:
            raise ValueError(f"Unsupported RunningHub site: {site}") from exc
        allowed = tuple(
            dict.fromkeys(
                model_name
                for stage_models in stage_catalog.values()
                for model_name in stage_models
            )
        )
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
                "api_key_env": RUNNINGHUB_API_KEY_ENVS[site],
                "stages": {
                    stage: list(models)
                    for stage, models in stage_catalog.items()
                },
            }
            for site, stage_catalog in _CURATED_MODELS.items()
        }
    }

