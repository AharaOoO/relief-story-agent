from __future__ import annotations

import json
import random
import time
import uuid
from datetime import datetime, timezone
from threading import Lock
from typing import Callable

import httpx
import openai

from .models import ModelAttempt, ModelCallResult, ModelUsage, StageModelConfig
from .providers import ModelProvider


AttemptRecorder = Callable[[ModelAttempt], None]


class ModelCallExecutor:
    def __init__(
        self,
        provider: ModelProvider,
        *,
        runninghub_provider: ModelProvider | None = None,
        sleep_fn: Callable[[float], None] = time.sleep,
        monotonic_fn: Callable[[], float] = time.monotonic,
        random_fn: Callable[[], float] = random.random,
    ):
        self.provider = provider
        if runninghub_provider is None:
            from .runninghub_llm import RunningHubLLMProvider

            runninghub_provider = RunningHubLLMProvider()
        self.runninghub_provider = runninghub_provider
        self.sleep_fn = sleep_fn
        self.monotonic_fn = monotonic_fn
        self.random_fn = random_fn
        self._last_request_at: dict[str, float] = {}
        self._rate_limit_registry_lock = Lock()
        self._rate_limit_locks: dict[str, Lock] = {}

    def execute(
        self,
        *,
        stage: str,
        prompt: str,
        config: StageModelConfig | None = None,
        record_attempt: AttemptRecorder | None = None,
    ) -> ModelCallResult:
        policy = config or StageModelConfig()
        for attempt_number in range(1, policy.max_attempts + 1):
            self._apply_rate_limit(policy)
            attempt = ModelAttempt(
                attempt_id="attempt_" + uuid.uuid4().hex,
                stage=stage,
                attempt_number=attempt_number,
                max_attempts=policy.max_attempts,
                model=policy.model,
            )
            self._record(record_attempt, attempt)
            started = self.monotonic_fn()
            try:
                provider = (
                    self.runninghub_provider
                    if policy.provider_mode == "runninghub"
                    else self.provider
                )
                raw_result = provider.generate_json(stage, prompt, config)
                result = self._normalize_result(raw_result, policy)
            except Exception as exc:
                retryable = _is_retryable_error(exc)
                can_retry = retryable and attempt_number < policy.max_attempts
                delay = self._retry_delay(exc, policy, attempt_number) if can_retry else 0.0
                attempt.status = "retryable_failed" if can_retry else "permanent_failed"
                attempt.retryable = retryable
                attempt.retry_delay_seconds = delay
                attempt.error_type = type(exc).__name__
                attempt.error_message = str(exc)
                attempt.http_status = _status_code(exc)
                attempt.request_id = str(getattr(exc, "request_id", "") or "")
                self._finish_attempt(attempt, started)
                self._record(record_attempt, attempt)
                if not can_retry:
                    raise
                self.sleep_fn(delay)
                continue

            usage = result.usage
            attempt.status = "succeeded"
            attempt.model = result.model or policy.model
            attempt.request_id = result.request_id
            attempt.prompt_tokens = usage.prompt_tokens
            attempt.completion_tokens = usage.completion_tokens
            attempt.total_tokens = usage.total_tokens
            attempt.estimated_cost_usd = (
                usage.prompt_tokens * policy.input_cost_per_million
                + usage.completion_tokens * policy.output_cost_per_million
            ) / 1_000_000
            self._finish_attempt(attempt, started)
            self._record(record_attempt, attempt)
            return result
        raise RuntimeError("model execution exhausted without a terminal result")

    def _apply_rate_limit(self, config: StageModelConfig) -> None:
        if config.requests_per_minute <= 0:
            return
        key = f"{config.base_url}|{config.model}"
        with self._rate_limit_lock_for(key):
            minimum_interval = 60.0 / config.requests_per_minute
            now = self.monotonic_fn()
            previous = self._last_request_at.get(key)
            if previous is not None:
                wait = minimum_interval - (now - previous)
                if wait > 0:
                    self.sleep_fn(wait)
                    now = self.monotonic_fn()
            self._last_request_at[key] = now

    def _rate_limit_lock_for(self, key: str) -> Lock:
        with self._rate_limit_registry_lock:
            lock = self._rate_limit_locks.get(key)
            if lock is None:
                lock = Lock()
                self._rate_limit_locks[key] = lock
            return lock

    def _retry_delay(
        self,
        exc: Exception,
        config: StageModelConfig,
        attempt_number: int,
    ) -> float:
        base_delay = min(
            config.max_backoff_seconds,
            config.initial_backoff_seconds
            * (config.backoff_multiplier ** (attempt_number - 1)),
        )
        retry_after = _retry_after_seconds(exc)
        if retry_after is not None:
            base_delay = min(config.max_backoff_seconds, max(base_delay, retry_after))
        jitter = base_delay * config.retry_jitter_ratio * self.random_fn()
        return min(config.max_backoff_seconds, base_delay + jitter)

    @staticmethod
    def _normalize_result(
        result: dict | ModelCallResult,
        config: StageModelConfig,
    ) -> ModelCallResult:
        if isinstance(result, ModelCallResult):
            return result
        return ModelCallResult(payload=dict(result), model=config.model)

    def _finish_attempt(self, attempt: ModelAttempt, started: float) -> None:
        attempt.finished_at = datetime.now(timezone.utc).isoformat()
        attempt.duration_ms = max(0, (self.monotonic_fn() - started) * 1000)

    @staticmethod
    def _record(recorder: AttemptRecorder | None, attempt: ModelAttempt) -> None:
        if recorder:
            recorder(attempt.model_copy(deep=True))


def _is_retryable_error(exc: Exception) -> bool:
    if isinstance(exc, (openai.APIConnectionError, httpx.TransportError)):
        return True
    if isinstance(exc, json.JSONDecodeError):
        return True
    status = _status_code(exc)
    return status in {408, 409, 429} or bool(status and status >= 500)


def _status_code(exc: Exception) -> int | None:
    status = getattr(exc, "status_code", None)
    if isinstance(status, int):
        return status
    response = getattr(exc, "response", None)
    response_status = getattr(response, "status_code", None)
    return response_status if isinstance(response_status, int) else None


def _retry_after_seconds(exc: Exception) -> float | None:
    response = getattr(exc, "response", None)
    headers = getattr(response, "headers", None)
    if not headers:
        return None
    raw = headers.get("retry-after")
    if raw is None:
        return None
    try:
        return max(0.0, float(raw))
    except (TypeError, ValueError):
        return None
