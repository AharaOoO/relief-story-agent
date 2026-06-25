import json

import httpx
import openai

from relief_story_agent.failure_policy import classify_failure


def test_classifier_marks_timeout_as_retryable():
    record = classify_failure(
        "gpt_prompt_writer",
        httpx.TimeoutException("read timeout"),
    )

    assert record.stage == "gpt_prompt_writer"
    assert record.category == "timeout"
    assert record.code == "timeout"
    assert record.retryable is True
    assert record.exception_type == "TimeoutException"


def test_classifier_marks_rate_limit_as_retryable_throttling():
    request = httpx.Request("POST", "http://model.local/v1/chat/completions")
    exc = httpx.HTTPStatusError(
        "rate limited",
        request=request,
        response=httpx.Response(429, request=request),
    )

    record = classify_failure("chief_screenwriter", exc)

    assert record.category == "throttled"
    assert record.code == "http_429"
    assert record.http_status == 429
    assert record.retryable is True


def test_classifier_keeps_unknown_errors_manual_by_default():
    record = classify_failure("deepseek_polish", RuntimeError("surprising failure"))

    assert record.category == "unknown"
    assert record.retryable is False
    assert record.code == "unknown_error"


def test_classifier_marks_quality_gate_as_validation():
    record = classify_failure(
        "quality_gate",
        ValueError("deepseek_polish quality gate failed: ['too intense']"),
    )

    assert record.category == "validation"
    assert record.retryable is False
    assert record.code == "quality_gate_failed"


def test_classifier_marks_json_decode_as_non_retryable_contract_response():
    exc = json.JSONDecodeError("bad json", "not-json", 0)

    record = classify_failure("gpt_prompt_audit", exc)

    assert record.category == "contract"
    assert record.code == "malformed_json"
    assert record.retryable is False


def test_classifier_marks_openai_connection_error_as_retryable_transient():
    request = httpx.Request("POST", "http://model.local/v1/chat/completions")

    record = classify_failure(
        "deepseek_polish",
        openai.APIConnectionError(request=request),
    )

    assert record.category == "transient"
    assert record.code == "api_connection_error"
    assert record.retryable is True


def test_classifier_marks_openai_timeout_as_retryable_timeout():
    request = httpx.Request("POST", "http://model.local/v1/chat/completions")

    record = classify_failure(
        "gpt_prompt_writer",
        openai.APITimeoutError(request),
    )

    assert record.category == "timeout"
    assert record.code == "api_timeout"
    assert record.retryable is True


def test_grid_image_validation_is_non_retryable():
    record = classify_failure(
        "four_grid_asset",
        ValueError("grid image quadrant 2 has no pixel variation"),
    )

    assert record.category == "validation"
    assert record.code == "grid_image_invalid"
    assert record.retryable is False
