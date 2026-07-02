from __future__ import annotations

import json
import os
from typing import Any

from openai import OpenAI

from .models import ModelCallResult, ModelUsage, StageModelConfig
from .provider_catalog import validate_runninghub_model


class RunningHubLLMProvider:
    """OpenAI-compatible RunningHub LLM transport with site catalog validation."""

    def generate_json(
        self,
        stage: str,
        prompt: str,
        config: StageModelConfig | None = None,
    ) -> ModelCallResult:
        if config is None or config.provider_mode != "runninghub":
            raise ValueError("RunningHub LLM provider requires runninghub model config")
        if config.runninghub_site is None:
            raise ValueError("RunningHub LLM provider requires runninghub_site")
        validate_runninghub_model(
            site=config.runninghub_site,
            stage=stage,
            model=config.model,
        )
        api_key = os.environ.get(config.api_key_env, "")
        if not api_key:
            raise ValueError(
                f"Missing environment variable for RunningHub API key: {config.api_key_env}"
            )
        client = OpenAI(
            base_url=config.base_url,
            api_key=api_key,
            max_retries=0,
            timeout=config.timeout_seconds,
        )
        try:
            response = client.chat.completions.create(
                model=config.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=config.temperature,
            )
        except Exception as exc:
            if _is_enterprise_shared_key_error(exc):
                raise ValueError(
                    "RunningHub LLM 模型接口需要企业共享 API Key"
                    f"（SHARED / enterprise key）。当前 {config.api_key_env} "
                    "看起来是普通 OpenAPI key；请在 RunningHub 后台填入企业共享 key，"
                    "或把前 6 道工序切换到“普通模型 API”。"
                ) from exc
            raise
        content = response.choices[0].message.content or ""
        usage = getattr(response, "usage", None)
        return ModelCallResult(
            payload=self._parse_json(content),
            model=str(getattr(response, "model", "") or config.model),
            request_id=str(getattr(response, "_request_id", "") or ""),
            usage=ModelUsage(
                prompt_tokens=int(getattr(usage, "prompt_tokens", 0) or 0),
                completion_tokens=int(getattr(usage, "completion_tokens", 0) or 0),
                total_tokens=int(getattr(usage, "total_tokens", 0) or 0),
            ),
        )

    @staticmethod
    def _parse_json(content: str) -> dict[str, Any]:
        stripped = content.strip()
        if stripped.startswith("```"):
            first_newline = stripped.find("\n")
            last_fence = stripped.rfind("```")
            if first_newline >= 0 and last_fence > first_newline:
                stripped = stripped[first_newline + 1 : last_fence].strip()
        try:
            payload = json.loads(stripped)
        except json.JSONDecodeError:
            start = stripped.find("{")
            end = stripped.rfind("}")
            if start < 0 or end <= start:
                raise
            payload = json.loads(stripped[start : end + 1])
        if not isinstance(payload, dict):
            raise ValueError("RunningHub LLM response must be a JSON object")
        return payload


def _is_enterprise_shared_key_error(exc: Exception) -> bool:
    body = getattr(exc, "body", None)
    if isinstance(body, dict):
        error = body.get("error")
        candidates = [body, error] if isinstance(error, dict) else [body]
        for candidate in candidates:
            code = str(candidate.get("code", ""))
            message = str(candidate.get("message", ""))
            if "auth_apikey_type_forbidden" in code or "only SHARED" in message:
                return True
    response = getattr(exc, "response", None)
    if response is not None:
        try:
            payload = response.json()
        except Exception:
            payload = None
        if isinstance(payload, dict):
            error = payload.get("error")
            candidates = [payload, error] if isinstance(error, dict) else [payload]
            for candidate in candidates:
                code = str(candidate.get("code", ""))
                message = str(candidate.get("message", ""))
                if "auth_apikey_type_forbidden" in code or "only SHARED" in message:
                    return True
    text = str(exc)
    return (
        "auth_apikey_type_forbidden" in text
        or "only SHARED (enterprise) api keys are accepted" in text
    )
