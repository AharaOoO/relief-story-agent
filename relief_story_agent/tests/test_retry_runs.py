from __future__ import annotations

from fastapi.testclient import TestClient

from relief_story_agent.api import create_app
from relief_story_agent.models import RunRequest, RunRetryRequest
from relief_story_agent.orchestrator import InMemoryRunStore, StoryRunOrchestrator
from relief_story_agent.providers import FakeModelProvider


def test_retry_failed_run_resumes_from_failed_stage_without_rerunning_prior_stages():
    provider = FakeModelProvider.minimal_success()
    provider.responses.pop("gpt_prompt_audit")
    store = InMemoryRunStore()
    orchestrator = StoryRunOrchestrator(provider=provider, store=store)

    failed = orchestrator.create_run(RunRequest(idea="重试便利店", approval_mode="auto"))

    assert failed.status == "failed"
    assert failed.failed_stage == "gpt_prompt_audit"
    assert provider.calls == [
        "chief_screenwriter",
        "deepseek_polish",
        "quality_gate",
        "gpt_prompt_writer",
        "gpt_prompt_audit",
    ]

    provider.responses["gpt_prompt_audit"] = {
        "passed": True,
        "issues": [],
        "revision_instructions": [],
        "scores": {},
    }
    retried = orchestrator.retry(failed.run_id)

    assert retried.status == "completed"
    assert retried.failed_stage == ""
    assert retried.retry_count == 1
    assert retried.model_usage_summary.total_requests == 5
    assert retried.model_usage_summary.total_attempts == 6
    assert provider.calls == [
        "chief_screenwriter",
        "deepseek_polish",
        "quality_gate",
        "gpt_prompt_writer",
        "gpt_prompt_audit",
        "gpt_prompt_audit",
    ]


def test_retry_can_restart_from_explicit_stage_when_requested():
    provider = FakeModelProvider.minimal_success()
    provider.responses.pop("gpt_prompt_audit")
    orchestrator = StoryRunOrchestrator(provider=provider, store=InMemoryRunStore())

    failed = orchestrator.create_run(RunRequest(idea="显式重跑提示词", approval_mode="auto"))
    provider.responses["gpt_prompt_audit"] = {
        "passed": True,
        "issues": [],
        "revision_instructions": [],
        "scores": {},
    }
    provider.calls.clear()

    retried = orchestrator.retry(
        failed.run_id,
        RunRetryRequest(from_stage="gpt_prompt_writer"),
    )

    assert retried.status == "completed"
    assert provider.calls == ["gpt_prompt_writer", "gpt_prompt_audit"]


def test_api_retries_failed_run():
    provider = FakeModelProvider.minimal_success()
    provider.responses.pop("gpt_prompt_audit")
    store = InMemoryRunStore()
    app = create_app(StoryRunOrchestrator(provider=provider, store=store))
    client = TestClient(app)

    create = client.post("/api/runs", json={"idea": "API 重试", "approval_mode": "auto"})
    assert create.status_code == 200
    assert create.json()["status"] == "failed"
    run_id = create.json()["run_id"]
    provider.responses["gpt_prompt_audit"] = {
        "passed": True,
        "issues": [],
        "revision_instructions": [],
        "scores": {},
    }

    retry = client.post(f"/api/runs/{run_id}/retry")

    assert retry.status_code == 200
    assert retry.json()["status"] == "completed"
    assert retry.json()["retry_count"] == 1
