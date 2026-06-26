from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .grid_image import GridImageProvider
from .image_providers import OpenAICompatibleGridImageProvider
from .model_config import ModelConfigRegistry
from .models import GridImageConfig, ModelCallResult, StageModelConfig
from .providers import ModelProvider, OpenAICompatibleProvider


MODEL_PROBE_PROMPT = (
    'Return JSON only: {"ok": true, "purpose": "relief_story_agent_model_probe"}. '
    "Do not include markdown."
)
IMAGE_PROBE_PROMPT = (
    "Create a simple 2x2 non-text color card for relief_story_agent_image_probe. "
    "No readable text, logos, watermark, or photoreal people."
)


def run_model_probe(
    registry: ModelConfigRegistry,
    *,
    provider: ModelProvider | None = None,
    image_provider: GridImageProvider | None = None,
    image_config: GridImageConfig | None = None,
    real_run: bool = False,
    profile_names: list[str] | None = None,
) -> dict[str, Any]:
    selected_names = list(profile_names or registry.profiles.keys())
    checks = []
    active_provider = provider or OpenAICompatibleProvider()
    for profile_name in selected_names:
        config = registry.profiles.get(profile_name)
        if config is None:
            checks.append(_missing_profile_check(profile_name))
            continue
        checks.append(
            _probe_profile(
                profile_name,
                config,
                registry=registry,
                provider=active_provider,
                real_run=real_run,
            )
        )
    if image_config is not None:
        checks.append(
            _probe_image_provider(
                image_config,
                registry=registry,
                provider=image_provider or OpenAICompatibleGridImageProvider(),
                real_run=real_run,
            )
        )
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "real_run": real_run,
        "ready": bool(checks) and all(check["status"] == "pass" for check in checks),
        "checks": checks,
    }


def _probe_profile(
    profile_name: str,
    config: StageModelConfig,
    *,
    registry: ModelConfigRegistry,
    provider: ModelProvider,
    real_run: bool,
) -> dict[str, Any]:
    base = {
        "profile": profile_name,
        "base_url": config.base_url,
        "model": config.model,
        "api_key_env": config.api_key_env,
        "secret_required": bool(config.api_key_env),
        "secret_configured": _secret_configured(config, registry),
        "real_run": real_run,
    }
    if not config.model:
        return {**base, "status": "fail", "message": "Missing model name."}
    if _has_placeholder_value(config.model) or _has_placeholder_value(config.base_url):
        return {
            **base,
            "status": "fail",
            "message": "Replace placeholder model/base_url values before probing.",
        }
    if config.api_key_env and not base["secret_configured"]:
        return {
            **base,
            "status": "fail",
            "message": f"Missing environment variable: {config.api_key_env}",
        }
    if not real_run:
        return {
            **base,
            "status": "pass",
            "message": "Configuration is ready for a real model probe.",
        }
    try:
        result = provider.generate_json(
            f"model_probe.{profile_name}",
            MODEL_PROBE_PROMPT,
            config,
        )
    except Exception as exc:  # noqa: BLE001 - report provider/runtime failures as probe evidence.
        return {
            **base,
            "status": "fail",
            "message": str(exc),
            "error_type": exc.__class__.__name__,
        }
    call_result = _normalize_model_result(result, config)
    return {
        **base,
        "status": "pass",
        "message": "Model JSON probe succeeded.",
        "request_id": call_result.request_id,
        "served_model": call_result.model,
        "usage": call_result.usage.model_dump(),
    }


def _probe_image_provider(
    config: GridImageConfig,
    *,
    registry: ModelConfigRegistry,
    provider: GridImageProvider,
    real_run: bool,
) -> dict[str, Any]:
    base = {
        "profile": "image_provider",
        "provider": config.provider,
        "base_url": config.base_url,
        "model": config.model,
        "api_key_env": config.api_key_env,
        "secret_required": bool(config.api_key_env),
        "secret_configured": _image_secret_configured(config, registry),
        "real_run": real_run,
        "mode": config.effective_mode(),
    }
    if config.effective_mode() == "manual_override":
        return {
            **base,
            "status": "pass",
            "message": "Manual grid image override configured; image provider probe not required.",
        }
    if not config.model:
        return {**base, "status": "fail", "message": "Missing image model name."}
    if _has_placeholder_value(config.model) or _has_placeholder_value(config.base_url):
        return {
            **base,
            "status": "fail",
            "message": "Replace placeholder image model/base_url values before probing.",
        }
    if config.api_key_env and not base["secret_configured"]:
        return {
            **base,
            "status": "fail",
            "message": f"Missing environment variable: {config.api_key_env}",
        }
    if not real_run:
        return {
            **base,
            "status": "pass",
            "message": "Image provider configuration is ready for a real probe.",
        }
    try:
        generated = provider.generate(prompt=IMAGE_PROBE_PROMPT, config=config)
    except Exception as exc:  # noqa: BLE001 - report provider/runtime failures as probe evidence.
        return {
            **base,
            "status": "fail",
            "message": str(exc),
            "error_type": exc.__class__.__name__,
        }
    if not generated.content:
        return {
            **base,
            "status": "fail",
            "message": "Image provider probe returned empty image bytes.",
        }
    return {
        **base,
        "status": "pass",
        "message": "Image provider probe succeeded.",
        "served_model": generated.model,
        "mime_type": generated.mime_type,
        "byte_size": len(generated.content),
    }


def _secret_configured(config: StageModelConfig, registry: ModelConfigRegistry) -> bool:
    if not config.api_key_env:
        return True
    return bool(registry.environ.get(config.api_key_env))


def _image_secret_configured(config: GridImageConfig, registry: ModelConfigRegistry) -> bool:
    if config.api_key:
        return True
    if not config.api_key_env:
        return True
    return bool(registry.environ.get(config.api_key_env))


def _has_placeholder_value(value: str) -> bool:
    normalized = value.strip().upper()
    return "YOUR_" in normalized or "REPLACE_ME" in normalized or normalized in {"TODO", "TBD"}


def _normalize_model_result(
    result: dict[str, Any] | ModelCallResult,
    config: StageModelConfig,
) -> ModelCallResult:
    if isinstance(result, ModelCallResult):
        return result
    return ModelCallResult(payload=dict(result), model=config.model)


def _missing_profile_check(profile_name: str) -> dict[str, Any]:
    return {
        "profile": profile_name,
        "base_url": "",
        "model": "",
        "api_key_env": "",
        "secret_required": False,
        "secret_configured": False,
        "real_run": False,
        "status": "fail",
        "message": f"Unknown model profile: {profile_name}",
    }
