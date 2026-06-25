from __future__ import annotations

import json
import threading
from types import SimpleNamespace

import httpx
import pytest

from relief_story_agent.model_runtime import ModelCallExecutor
from relief_story_agent.models import (
    ModelCallResult,
    ModelUsage,
    RunRequest,
    StageModelConfig,
)
from relief_story_agent.orchestrator import InMemoryRunStore, StoryRunOrchestrator
from relief_story_agent.providers import FakeModelProvider, OpenAICompatibleProvider


class SequenceProvider:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls = 0

    def generate_json(self, stage, prompt, config=None):
        self.calls += 1
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


class BlockingClock:
    def __init__(self):
        self.value = 0.0
        self.active_sleeps = 0
        self.max_active_sleeps = 0
        self.first_sleep_started = threading.Event()
        self.two_sleeps_started = threading.Event()
        self.release_sleeps = threading.Event()
        self._lock = threading.Lock()

    def monotonic(self):
        with self._lock:
            return self.value

    def sleep(self, seconds):
        with self._lock:
            self.active_sleeps += 1
            self.max_active_sleeps = max(
                self.max_active_sleeps,
                self.active_sleeps,
            )
            self.first_sleep_started.set()
            if self.active_sleeps >= 2:
                self.two_sleeps_started.set()
        self.release_sleeps.wait(timeout=2)
        with self._lock:
            self.value += seconds
            self.active_sleeps -= 1


def _capture_latest():
    latest = {}

    def capture(attempt):
        latest[attempt.attempt_id] = attempt.model_copy(deep=True)

    return latest, capture


def test_executor_retries_transient_connection_errors_with_exponential_backoff():
    request = httpx.Request("POST", "http://model.local/v1/chat/completions")
    provider = SequenceProvider(
        [
            httpx.ReadTimeout("slow", request=request),
            httpx.ConnectError("offline", request=request),
            {"ok": True},
        ]
    )
    sleeps = []
    latest, capture = _capture_latest()
    executor = ModelCallExecutor(
        provider,
        sleep_fn=sleeps.append,
        random_fn=lambda: 0.0,
    )
    config = StageModelConfig(
        model="test-model",
        max_attempts=3,
        initial_backoff_seconds=0.5,
        backoff_multiplier=2.0,
        max_backoff_seconds=10,
        retry_jitter_ratio=0,
    )

    result = executor.execute(
        stage="chief_screenwriter",
        prompt="写一个故事",
        config=config,
        record_attempt=capture,
    )

    assert result.payload == {"ok": True}
    assert provider.calls == 3
    assert sleeps == [0.5, 1.0]
    final_attempts = sorted(latest.values(), key=lambda item: item.attempt_number)
    assert [item.status for item in final_attempts] == [
        "retryable_failed",
        "retryable_failed",
        "succeeded",
    ]
    assert [item.retry_delay_seconds for item in final_attempts] == [0.5, 1.0, 0.0]


def test_executor_does_not_retry_permanent_configuration_errors():
    provider = SequenceProvider([ValueError("missing model")])
    sleeps = []
    latest, capture = _capture_latest()
    executor = ModelCallExecutor(provider, sleep_fn=sleeps.append)

    with pytest.raises(ValueError, match="missing model"):
        executor.execute(
            stage="gpt_prompt_writer",
            prompt="prompt",
            config=StageModelConfig(model=""),
            record_attempt=capture,
        )

    assert provider.calls == 1
    assert sleeps == []
    attempt = next(iter(latest.values()))
    assert attempt.status == "permanent_failed"
    assert attempt.retryable is False


def test_executor_uses_retry_after_for_rate_limit_responses():
    request = httpx.Request("POST", "http://model.local/v1/chat/completions")
    response = httpx.Response(429, request=request, headers={"retry-after": "3"})
    provider = SequenceProvider(
        [
            httpx.HTTPStatusError("rate limited", request=request, response=response),
            {"ok": True},
        ]
    )
    sleeps = []
    executor = ModelCallExecutor(
        provider,
        sleep_fn=sleeps.append,
        random_fn=lambda: 0.0,
    )

    executor.execute(
        stage="deepseek_polish",
        prompt="prompt",
        config=StageModelConfig(
            model="deepseek",
            max_attempts=2,
            initial_backoff_seconds=0.25,
            max_backoff_seconds=10,
            retry_jitter_ratio=0,
        ),
    )

    assert sleeps == [3.0]


def test_retry_jitter_never_exceeds_configured_maximum_backoff():
    request = httpx.Request("POST", "http://model.local/v1/chat/completions")
    provider = SequenceProvider(
        [
            httpx.ReadTimeout("slow", request=request),
            {"ok": True},
        ]
    )
    sleeps = []
    executor = ModelCallExecutor(
        provider,
        sleep_fn=sleeps.append,
        random_fn=lambda: 1.0,
    )

    executor.execute(
        stage="chief_screenwriter",
        prompt="prompt",
        config=StageModelConfig(
            model="test",
            max_attempts=2,
            initial_backoff_seconds=10,
            max_backoff_seconds=5,
            retry_jitter_ratio=1,
        ),
    )

    assert sleeps == [5.0]


def test_executor_records_usage_and_estimated_cost():
    provider = SequenceProvider(
        [
            ModelCallResult(
                payload={"ok": True},
                model="priced-model",
                request_id="req_123",
                usage=ModelUsage(
                    prompt_tokens=1000,
                    completion_tokens=500,
                    total_tokens=1500,
                ),
            )
        ]
    )
    latest, capture = _capture_latest()
    executor = ModelCallExecutor(provider)

    result = executor.execute(
        stage="gpt_prompt_audit",
        prompt="prompt",
        config=StageModelConfig(
            model="priced-model",
            input_cost_per_million=2.0,
            output_cost_per_million=8.0,
        ),
        record_attempt=capture,
    )

    attempt = next(iter(latest.values()))
    assert result.request_id == "req_123"
    assert attempt.prompt_tokens == 1000
    assert attempt.completion_tokens == 500
    assert attempt.total_tokens == 1500
    assert attempt.estimated_cost_usd == pytest.approx(0.006)


def test_executor_spaces_requests_for_the_same_endpoint_and_model():
    provider = SequenceProvider([{"ok": 1}, {"ok": 2}])
    clock = [100.0]
    sleeps = []

    def sleep_and_advance(seconds):
        sleeps.append(seconds)
        clock[0] += seconds

    executor = ModelCallExecutor(
        provider,
        sleep_fn=sleep_and_advance,
        monotonic_fn=lambda: clock[0],
    )
    config = StageModelConfig(
        model="shared-model",
        requests_per_minute=60,
    )

    executor.execute(stage="chief_screenwriter", prompt="one", config=config)
    executor.execute(stage="deepseek_polish", prompt="two", config=config)

    assert sleeps == [1.0]


def test_executor_serializes_rate_limit_waits_for_the_same_model_key():
    provider = SequenceProvider([{"ok": 1}, {"ok": 2}, {"ok": 3}])
    clock = BlockingClock()
    executor = ModelCallExecutor(
        provider,
        sleep_fn=clock.sleep,
        monotonic_fn=clock.monotonic,
    )
    config = StageModelConfig(
        base_url="http://shared-model.local/v1",
        model="shared-model",
        requests_per_minute=60,
    )
    errors = []

    executor.execute(stage="chief_screenwriter", prompt="prime", config=config)

    def execute(prompt):
        try:
            executor.execute(
                stage="chief_screenwriter",
                prompt=prompt,
                config=config,
            )
        except Exception as exc:
            errors.append(exc)

    first = threading.Thread(target=execute, args=("first",))
    second = threading.Thread(target=execute, args=("second",))
    first.start()
    assert clock.first_sleep_started.wait(timeout=1)
    second.start()
    concurrent_wait_observed = clock.two_sleeps_started.wait(timeout=0.2)
    clock.release_sleeps.set()
    first.join(timeout=2)
    second.join(timeout=2)

    assert errors == []
    assert not first.is_alive()
    assert not second.is_alive()
    assert concurrent_wait_observed is False
    assert clock.max_active_sleeps == 1


def test_executor_keeps_rate_limit_waits_independent_for_different_model_keys():
    provider = SequenceProvider(
        [{"ok": 1}, {"ok": 2}, {"ok": 3}, {"ok": 4}]
    )
    clock = BlockingClock()
    executor = ModelCallExecutor(
        provider,
        sleep_fn=clock.sleep,
        monotonic_fn=clock.monotonic,
    )
    first_config = StageModelConfig(
        base_url="http://models.local/v1",
        model="model-a",
        requests_per_minute=60,
    )
    second_config = StageModelConfig(
        base_url="http://models.local/v1",
        model="model-b",
        requests_per_minute=60,
    )

    executor.execute(
        stage="chief_screenwriter",
        prompt="prime-a",
        config=first_config,
    )
    executor.execute(
        stage="deepseek_polish",
        prompt="prime-b",
        config=second_config,
    )

    first = threading.Thread(
        target=executor.execute,
        kwargs={
            "stage": "chief_screenwriter",
            "prompt": "model-a",
            "config": first_config,
        },
    )
    second = threading.Thread(
        target=executor.execute,
        kwargs={
            "stage": "deepseek_polish",
            "prompt": "model-b",
            "config": second_config,
        },
    )
    first.start()
    assert clock.first_sleep_started.wait(timeout=1)
    second.start()
    independent_waits_observed = clock.two_sleeps_started.wait(timeout=1)
    clock.release_sleeps.set()
    first.join(timeout=2)
    second.join(timeout=2)

    assert not first.is_alive()
    assert not second.is_alive()
    assert independent_waits_observed is True
    assert clock.max_active_sleeps == 2


def test_openai_provider_disables_hidden_sdk_retries_and_returns_metadata(monkeypatch):
    captured = {}
    response = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps({"ok": True})))],
        usage=SimpleNamespace(prompt_tokens=12, completion_tokens=8, total_tokens=20),
        model="served-model",
        _request_id="req_provider",
    )

    class FakeCompletions:
        def create(self, **kwargs):
            captured["create"] = kwargs
            return response

    class FakeOpenAI:
        def __init__(self, **kwargs):
            captured["client"] = kwargs
            self.chat = SimpleNamespace(completions=FakeCompletions())

    monkeypatch.setattr("relief_story_agent.providers.OpenAI", FakeOpenAI)
    provider = OpenAICompatibleProvider()

    result = provider.generate_json(
        "chief_screenwriter",
        "prompt",
        StageModelConfig(model="configured-model"),
    )

    assert captured["client"]["max_retries"] == 0
    assert result.payload == {"ok": True}
    assert result.model == "served-model"
    assert result.request_id == "req_provider"
    assert result.usage.total_tokens == 20


def test_orchestrator_persists_model_attempts_and_usage_summary():
    provider = FakeModelProvider.minimal_success()
    store = InMemoryRunStore()
    orchestrator = StoryRunOrchestrator(provider=provider, store=store)

    run = orchestrator.create_run(
        RunRequest(idea="调用审计", approval_mode="auto")
    )

    assert run.status == "completed"
    assert [item.stage for item in run.model_attempts] == [
        "chief_screenwriter",
        "deepseek_polish",
        "gpt_prompt_writer",
        "gpt_prompt_audit",
    ]
    assert all(item.status == "succeeded" for item in run.model_attempts)
    assert run.model_usage_summary.total_requests == 4
