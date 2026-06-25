from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Mapping

from .models import StageModelConfig


class ModelConfigRegistry:
    def __init__(
        self,
        *,
        profiles: dict[str, StageModelConfig] | None = None,
        stages: dict[str, str] | None = None,
        environ: Mapping[str, str] | None = None,
    ):
        self.profiles = profiles or {}
        self.stages = stages or {}
        self.environ = environ if environ is not None else os.environ
        self._validate_stage_bindings()

    @classmethod
    def from_file(
        cls,
        path: str | Path,
        *,
        environ: Mapping[str, str] | None = None,
    ) -> "ModelConfigRegistry":
        source = Path(path)
        payload = json.loads(source.read_text(encoding="utf-8"))
        raw_profiles = payload.get("profiles") or {}
        raw_stages = payload.get("stages") or {}
        if not isinstance(raw_profiles, dict) or not isinstance(raw_stages, dict):
            raise ValueError("Model config registry requires object-valued profiles and stages")

        profiles: dict[str, StageModelConfig] = {}
        for profile_name, raw_config in raw_profiles.items():
            if not isinstance(raw_config, dict):
                raise ValueError(f"Model profile {profile_name!r} must be an object")
            if "api_key" in raw_config:
                raise ValueError(
                    f"Model profile {profile_name!r} contains plaintext api_key; "
                    "use api_key_env instead"
                )
            profiles[str(profile_name)] = StageModelConfig.model_validate(raw_config)

        stages = {str(stage): str(profile) for stage, profile in raw_stages.items()}
        return cls(profiles=profiles, stages=stages, environ=environ)

    def resolve(
        self,
        stage: str,
        *,
        inline: StageModelConfig | None = None,
        profile_override: str | None = None,
    ) -> StageModelConfig | None:
        profile_name = profile_override or self.stages.get(stage)
        base: StageModelConfig | None = None
        if profile_name:
            try:
                base = self.profiles[profile_name].model_copy(deep=True)
            except KeyError as exc:
                raise ValueError(
                    f"Unknown model profile {profile_name!r} for stage {stage!r}"
                ) from exc
        if inline is None:
            return base
        if base is None:
            return inline.model_copy(deep=True)

        updates = {
            field_name: getattr(inline, field_name)
            for field_name in inline.model_fields_set
        }
        return base.model_copy(update=updates, deep=True)

    def status(self) -> dict:
        missing_environment_variables = sorted(
            {
                config.api_key_env
                for config in self.profiles.values()
                if config.api_key_env and not self.environ.get(config.api_key_env)
            }
        )
        return {
            "profiles": {
                name: {
                    "base_url": config.base_url,
                    "model": config.model,
                    "api_key_env": config.api_key_env,
                    "secret_required": bool(config.api_key_env),
                    "secret_configured": (
                        bool(self.environ.get(config.api_key_env))
                        if config.api_key_env
                        else True
                    ),
                }
                for name, config in sorted(self.profiles.items())
            },
            "stages": dict(sorted(self.stages.items())),
            "missing_environment_variables": missing_environment_variables,
        }

    def _validate_stage_bindings(self) -> None:
        for stage, profile_name in self.stages.items():
            if profile_name not in self.profiles:
                raise ValueError(
                    f"Stage {stage!r} references unknown model profile {profile_name!r}"
                )
