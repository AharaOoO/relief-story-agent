from __future__ import annotations

import json
import threading
import time
from datetime import datetime, timedelta, timezone

import httpx
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw

from relief_story_agent.api import create_app
from relief_story_agent.models import (
    BatchRunRequest,
    ComfyUIRunConfig,
    RunRequest,
    RunState,
)
from relief_story_agent.orchestrator import InMemoryRunStore, StoryRunOrchestrator
from relief_story_agent.providers import FakeModelProvider
from relief_story_agent.resource_limits import ExecutionResourceLimits
from relief_story_agent.scheduler import PersistentRunScheduler
from relief_story_agent.storage import JsonFileRunStore
from relief_story_agent.tests.fixtures.ltx23_workflow_factory import build_sanitized_ltx23_workflow


HTTPX_CLIENT = httpx.Client


def _grid_bytes(tmp_path):
    path = tmp_path / "scheduler_grid.png"
    image = Image.new("RGB", (1024, 1024), "white")
    draw = ImageDraw.Draw(image)
    for index, color in enumerate(["red", "green", "blue", "yellow"]):
        left = (index % 2) * 512
        top = (index // 2) * 512
        image.paste(color, (left, top, left + 512, top + 512))
        draw.line((left + 20, top + 20, left + 492, top + 492), fill="black", width=8)
    image.save(path)
    return path.read_bytes()


def _automatic_grid_request(tmp_path, index):
    workflow_path = tmp_path / f"scheduler_ltx23_{index}.json"
    workflow_path.write_text(
        json.dumps(build_sanitized_ltx23_workflow(), ensure_ascii=False),
        encoding="utf-8",
    )
    return RunRequest(
        idea=f"automatic grid {index}",
        approval_mode="auto",
        output_root=str(tmp_path / "runs"),
        comfyui=ComfyUIRunConfig(
            enabled=True,
            workflow_api_path=str(workflow_path),
        ),
    )


class BlockingGridProvider:
    def __init__(self, image_bytes):
        self.image_bytes = image_bytes
        self.release = threading.Event()
        self.started = threading.Event()
        self.lock = threading.Lock()
        self.active = 0
        self.max_active = 0

    def generate(self, *, prompt, config):
        from relief_story_agent.grid_image import GeneratedImage

        with self.lock:
            self.active += 1
            self.max_active = max(self.max_active, self.active)
            self.started.set()
        try:
            assert self.release.wait(timeout=5)
            return GeneratedImage(
                content=self.image_bytes,
                mime_type="image/png",
                provider="fake",
                model=config.model,
            )
        finally:
            with self.lock:
                self.active -= 1


def test_image_generation_concurrency_is_independent_from_worker_count(
    tmp_path,
    monkeypatch,
):
    provider = BlockingGridProvider(_grid_bytes(tmp_path))
    monkeypatch.setattr(
        "relief_story_agent.orchestrator.upload_grid_image",
        lambda *args, **kwargs: "scheduler_grid.png",
    )
    monkeypatch.setattr(
        "relief_story_agent.orchestrator.submit_storyboard",
        lambda *args, **kwargs: [],
    )
    limits = ExecutionResourceLimits(
        image_generation_concurrency=1,
        comfyui_submission_concurrency=1,
    )
    orchestrator = StoryRunOrchestrator(
        provider=FakeModelProvider.minimal_success(),
        store=InMemoryRunStore(),
        grid_image_provider=provider,
        resource_limits=limits,
    )
    scheduler = PersistentRunScheduler(orchestrator, max_workers=3)

    for index in range(3):
        scheduler.create_run(_automatic_grid_request(tmp_path, index))
    assert provider.started.wait(timeout=2)
    time.sleep(0.05)
    assert provider.max_active == 1
    provider.release.set()
    assert scheduler.wait_for_idle(timeout=5)
    scheduler.shutdown()


class BlockingFakeProvider(FakeModelProvider):
    def __init__(self):
        base = FakeModelProvider.minimal_success()
        super().__init__(base.responses)
        self.release = threading.Event()
        self.started = threading.Event()
        self._lock = threading.Lock()
        self.active = 0
        self.max_active = 0

    def generate_json(self, stage, prompt, config=None):
        with self._lock:
            self.active += 1
            self.max_active = max(self.max_active, self.active)
            self.started.set()
        try:
            if stage == "chief_screenwriter":
                assert self.release.wait(timeout=5)
            return super().generate_json(stage, prompt, config)
        finally:
            with self._lock:
                self.active -= 1


class OneTimeAuditFailureProvider(FakeModelProvider):
    def __init__(self):
        base = FakeModelProvider.minimal_success()
        super().__init__(base.responses)
        self.failed_once = False

    def generate_json(self, stage, prompt, config=None):
        if stage == "gpt_prompt_audit" and not self.failed_once:
            self.calls.append(stage)
            self.failed_once = True
            request = httpx.Request("POST", "https://model.invalid/v1/chat/completions")
            raise httpx.HTTPStatusError(
                "transient audit failure",
                request=request,
                response=httpx.Response(503, request=request),
            )
        return super().generate_json(stage, prompt, config)


class AlwaysFailAuditProvider(FakeModelProvider):
    def __init__(self):
        base = FakeModelProvider.minimal_success()
        super().__init__(base.responses)

    def generate_json(self, stage, prompt, config=None):
        if stage == "gpt_prompt_audit":
            self.calls.append(stage)
            raise RuntimeError("permanent audit failure")
        return super().generate_json(stage, prompt, config)


class PriorityRecordingProvider(FakeModelProvider):
    def __init__(self):
        base = FakeModelProvider.minimal_success()
        super().__init__(base.responses)
        self.release_first = threading.Event()
        self.first_started = threading.Event()
        self.chief_order: list[str] = []

    def generate_json(self, stage, prompt, config=None):
        if stage == "chief_screenwriter":
            for marker in ("low priority", "medium priority", "high priority"):
                if marker in prompt:
                    self.chief_order.append(marker)
                    break
            if len(self.chief_order) == 1:
                self.first_started.set()
                assert self.release_first.wait(timeout=5)
        return super().generate_json(stage, prompt, config)


def _wait_for_status(store, run_id, statuses, timeout=5):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        run = store.get(run_id)
        if run.status in statuses:
            return run
        time.sleep(0.01)
    raise AssertionError(
        f"run {run_id} did not reach {statuses}; current={store.get(run_id).status}"
    )


def test_scheduler_enforces_worker_concurrency_and_completes_queued_runs():
    provider = BlockingFakeProvider()
    store = InMemoryRunStore()
    orchestrator = StoryRunOrchestrator(provider=provider, store=store)
    scheduler = PersistentRunScheduler(orchestrator, max_workers=2)
    runs = [
        scheduler.create_run(RunRequest(idea=f"任务 {index}", approval_mode="auto"))
        for index in range(3)
    ]

    assert all(run.status == "queued" for run in runs)
    assert provider.started.wait(timeout=2)
    time.sleep(0.05)
    assert provider.max_active == 2

    provider.release.set()
    assert scheduler.wait_for_idle(timeout=5)

    assert all(store.get(run.run_id).status == "completed" for run in runs)
    scheduler.shutdown()


def test_scheduler_runs_higher_priority_queued_items_first():
    provider = PriorityRecordingProvider()
    store = InMemoryRunStore()
    orchestrator = StoryRunOrchestrator(provider=provider, store=store)
    scheduler = PersistentRunScheduler(orchestrator, max_workers=1)

    low = scheduler.create_run(
        RunRequest(idea="low priority", approval_mode="auto", queue_priority=0)
    )
    assert provider.first_started.wait(timeout=2)
    medium = scheduler.create_run(
        RunRequest(idea="medium priority", approval_mode="auto", queue_priority=5)
    )
    high = scheduler.create_run(
        RunRequest(idea="high priority", approval_mode="auto", queue_priority=10)
    )

    provider.release_first.set()
    assert scheduler.wait_for_idle(timeout=5)

    assert provider.chief_order == ["low priority", "high priority", "medium priority"]
    assert store.get(low.run_id).queue_priority == 0
    assert store.get(medium.run_id).queue_priority == 5
    assert store.get(high.run_id).queue_priority == 10
    scheduler.shutdown()


def test_async_api_scheduler_status_lists_active_and_priority_ordered_queue():
    provider = PriorityRecordingProvider()
    store = InMemoryRunStore()
    orchestrator = StoryRunOrchestrator(provider=provider, store=store)
    scheduler = PersistentRunScheduler(orchestrator, max_workers=1)
    app = create_app(orchestrator, scheduler=scheduler)

    with TestClient(app) as client:
        low = client.post(
            "/api/runs",
            json={"idea": "low priority", "approval_mode": "auto", "queue_priority": 0},
        ).json()
        assert provider.first_started.wait(timeout=2)
        medium = client.post(
            "/api/runs",
            json={"idea": "medium priority", "approval_mode": "auto", "queue_priority": 5},
        ).json()
        high = client.post(
            "/api/runs",
            json={"idea": "high priority", "approval_mode": "auto", "queue_priority": 10},
        ).json()

        response = client.get("/api/scheduler")

        assert response.status_code == 200
        body = response.json()
        assert body["active"] == 1
        assert body["queued"] == 2
        assert body["active_items"][0]["run_id"] == low["run_id"]
        assert body["active_items"][0]["idea"] == "low priority"
        assert [item["run_id"] for item in body["queued_items"]] == [
            high["run_id"],
            medium["run_id"],
        ]
        assert [item["queue_priority"] for item in body["queued_items"]] == [10, 5]
        assert [item["position"] for item in body["queued_items"]] == [1, 2]
        provider.release_first.set()
        assert scheduler.wait_for_idle(timeout=5)


def test_scheduler_recovers_queued_and_expired_running_from_last_checkpoint(tmp_path):
    store = JsonFileRunStore(tmp_path / "state")
    provider = FakeModelProvider.minimal_success()
    orchestrator = StoryRunOrchestrator(provider=provider, store=store)
    queued = orchestrator.prepare_run(
        RunRequest(idea="排队恢复", approval_mode="auto")
    )
    expired = RunState(
        run_id="run_expired",
        request=RunRequest(idea="租约恢复", approval_mode="auto"),
        status="running",
        current_stage="gpt_prompt_writer",
        last_completed_stage="quality_gate",
        lease_owner="dead-worker",
        lease_expires_at=(
            datetime.now(timezone.utc) - timedelta(seconds=1)
        ).isoformat(),
        script=provider.responses["deepseek_polish"]["polished_script"],
        selected_core=provider.responses["chief_screenwriter"]["core_candidates"][0],
    )
    store.save(expired)
    provider.calls.clear()

    restarted = PersistentRunScheduler(orchestrator, max_workers=1)
    restarted.start()
    assert restarted.wait_for_idle(timeout=5)

    assert store.get(queued.run_id).status == "completed"
    recovered = store.get(expired.run_id)
    assert recovered.status == "completed"
    expired_calls = [
        item.stage
        for item in recovered.model_attempts
    ]
    assert expired_calls == ["gpt_prompt_writer", "gpt_prompt_audit"]
    restarted.shutdown()


def test_recovery_skips_stage_when_its_completion_checkpoint_was_saved(tmp_path):
    store = JsonFileRunStore(tmp_path / "state")
    provider = FakeModelProvider.minimal_success()
    expired = RunState(
        run_id="run_checkpointed_writer",
        request=RunRequest(idea="跳过已完成提示词", approval_mode="auto"),
        status="running",
        current_stage="gpt_prompt_writer",
        last_completed_stage="gpt_prompt_writer",
        lease_owner="dead-worker",
        lease_expires_at=(
            datetime.now(timezone.utc) - timedelta(seconds=1)
        ).isoformat(),
        script=provider.responses["deepseek_polish"]["polished_script"],
        storyboard=provider.responses["gpt_prompt_writer"]["shots"],
    )
    store.save(expired)
    orchestrator = StoryRunOrchestrator(provider=provider, store=store)
    provider.calls.clear()

    scheduler = PersistentRunScheduler(orchestrator, max_workers=1)
    scheduler.start()
    assert scheduler.wait_for_idle(timeout=5)

    recovered = store.get(expired.run_id)
    assert recovered.status == "completed"
    assert provider.calls == ["gpt_prompt_audit"]
    scheduler.shutdown()


def test_scheduler_periodically_recovers_running_task_after_lease_expires(tmp_path):
    store = JsonFileRunStore(tmp_path / "state")
    provider = FakeModelProvider.minimal_success()
    expiring = RunState(
        run_id="run_expiring_lease",
        request=RunRequest(idea="lease expires soon", approval_mode="auto"),
        status="running",
        current_stage="gpt_prompt_writer",
        last_completed_stage="quality_gate",
        lease_owner="dead-worker",
        lease_expires_at=(
            datetime.now(timezone.utc) + timedelta(seconds=0.15)
        ).isoformat(),
        script=provider.responses["deepseek_polish"]["polished_script"],
        selected_core=provider.responses["chief_screenwriter"]["core_candidates"][0],
    )
    store.save(expiring)
    orchestrator = StoryRunOrchestrator(provider=provider, store=store)
    provider.calls.clear()

    scheduler = PersistentRunScheduler(
        orchestrator,
        max_workers=1,
        recovery_poll_seconds=0.02,
    )
    scheduler.start()
    recovered = _wait_for_status(store, expiring.run_id, {"completed"}, timeout=5)

    assert recovered.status == "completed"
    assert [item.stage for item in recovered.model_attempts] == [
        "gpt_prompt_writer",
        "gpt_prompt_audit",
    ]
    assert scheduler.status()["recovery_poll_seconds"] == 0.02
    scheduler.shutdown()


def test_recovery_finishes_without_rerunning_when_final_checkpoint_exists(tmp_path):
    store = JsonFileRunStore(tmp_path / "state")
    provider = FakeModelProvider.minimal_success()
    storyboard = provider.responses["gpt_prompt_writer"]["shots"]
    expired = RunState(
        run_id="run_final_checkpoint",
        request=RunRequest(idea="最终检查点", approval_mode="auto"),
        status="running",
        current_stage="gpt_prompt_audit",
        last_completed_stage="gpt_prompt_audit",
        lease_owner="dead-worker",
        lease_expires_at=(
            datetime.now(timezone.utc) - timedelta(seconds=1)
        ).isoformat(),
        script=provider.responses["deepseek_polish"]["polished_script"],
        storyboard=storyboard,
        final_storyboard=storyboard,
        prompt_audit=provider.responses["gpt_prompt_audit"],
    )
    store.save(expired)
    orchestrator = StoryRunOrchestrator(provider=provider, store=store)
    provider.calls.clear()

    scheduler = PersistentRunScheduler(orchestrator, max_workers=1)
    scheduler.start()
    assert scheduler.wait_for_idle(timeout=5)

    recovered = store.get(expired.run_id)
    assert recovered.status == "completed"
    assert provider.calls == []
    scheduler.shutdown()


def test_cancel_running_run_is_observed_before_next_stage():
    provider = BlockingFakeProvider()
    store = InMemoryRunStore()
    orchestrator = StoryRunOrchestrator(provider=provider, store=store)
    scheduler = PersistentRunScheduler(orchestrator, max_workers=1)
    run = scheduler.create_run(
        RunRequest(idea="取消测试", approval_mode="auto")
    )
    assert provider.started.wait(timeout=2)

    cancelled = scheduler.cancel(run.run_id)

    assert cancelled.cancel_requested is True
    assert cancelled.status == "running"
    provider.release.set()
    final = _wait_for_status(store, run.run_id, {"cancelled"})

    assert final.current_stage == "cancelled"
    assert provider.calls == ["chief_screenwriter"]
    scheduler.shutdown()


def test_cancel_running_comfyui_wait_cancels_exact_remote_jobs(tmp_path, monkeypatch):
    workflow_path = tmp_path / "workflow_api.json"
    workflow_path.write_text(
        json.dumps({"1": {"class_type": "PromptNode", "inputs": {"text": "old"}}}),
        encoding="utf-8",
    )
    history_started = threading.Event()
    requests: list[tuple[str, str]] = []
    prompt_id = ""

    def handler(request: httpx.Request):
        nonlocal prompt_id
        requests.append((request.method, request.url.path))
        if request.url.path == "/prompt":
            payload = json.loads(request.content)
            prompt_id = payload["prompt_id"]
            return httpx.Response(200, json={"prompt_id": prompt_id})
        if request.url.path == f"/history/{prompt_id}":
            history_started.set()
            return httpx.Response(200, json={prompt_id: {"outputs": {}}})
        if request.url.path == f"/api/jobs/{prompt_id}/cancel":
            return httpx.Response(200, json={"cancelled": True})
        if request.url.path == "/queue":
            return httpx.Response(200, json={"queue_running": [], "queue_pending": []})
        raise AssertionError(f"unexpected request: {request.url}")

    monkeypatch.setattr(
        "relief_story_agent.comfyui.httpx.Client",
        lambda **kwargs: HTTPX_CLIENT(transport=httpx.MockTransport(handler)),
    )
    store = InMemoryRunStore()
    orchestrator = StoryRunOrchestrator(
        provider=FakeModelProvider.minimal_success(),
        store=store,
    )
    scheduler = PersistentRunScheduler(orchestrator, max_workers=1)
    try:
        run = scheduler.create_run(
            RunRequest(
                idea="cancel ComfyUI wait",
                approval_mode="auto",
                comfyui=ComfyUIRunConfig(
                    enabled=True,
                    endpoint="http://comfy.local",
                    workflow_api_path=str(workflow_path),
                    wait_for_completion=True,
                    download_outputs=False,
                    output_timeout_seconds=0.2,
                    output_poll_interval_seconds=0.05,
                    placeholder_map={
                        "positive": {
                            "node": "1",
                            "input": "text",
                            "source": "image_prompt",
                        }
                    },
                ),
            )
        )
        assert history_started.wait(timeout=2), {
            "status": store.get(run.run_id).status,
            "current_stage": store.get(run.run_id).current_stage,
            "error": store.get(run.run_id).error,
            "logs": [item.model_dump() for item in store.get(run.run_id).logs],
        }

        requested = scheduler.cancel(run.run_id)
        assert requested.cancel_requested is True
        final = _wait_for_status(store, run.run_id, {"cancelled"}, timeout=3)

        assert final.comfyui_prompt_ids == [prompt_id]
        assert len(final.comfyui_cancellations) == 1
        assert final.comfyui_cancellations[0].prompt_id == prompt_id
        assert final.comfyui_cancellations[0].strategy == "job_api"
        assert final.comfyui_cancellations[0].cancelled is True
        assert ("POST", f"/api/jobs/{prompt_id}/cancel") in requests
        assert all(path != "/interrupt" for _, path in requests)
    finally:
        scheduler.shutdown()


def test_scheduler_cancel_batch_requests_running_and_queued_children():
    provider = BlockingFakeProvider()
    store = InMemoryRunStore()
    orchestrator = StoryRunOrchestrator(provider=provider, store=store)
    scheduler = PersistentRunScheduler(orchestrator, max_workers=1)
    batch = scheduler.create_batch(
        BatchRunRequest(
            items=[
                RunRequest(idea="running child", approval_mode="auto"),
                RunRequest(idea="queued child", approval_mode="auto"),
            ]
        )
    )
    assert provider.started.wait(timeout=2)

    requested = scheduler.cancel_batch(batch.batch_id)

    assert requested.summary["cancelled"] == 1
    assert requested.summary["running"] == 1
    provider.release.set()
    assert scheduler.wait_for_idle(timeout=5)
    final = orchestrator.refresh_batch(batch.batch_id)

    assert final.status == "cancelled"
    assert final.summary["cancelled"] == 2
    assert all(store.get(item.run_id).status == "cancelled" for item in final.items)
    assert provider.calls == ["chief_screenwriter"]
    scheduler.shutdown()


def test_async_api_can_pause_and_resume_batch_queue():
    provider = BlockingFakeProvider()
    store = InMemoryRunStore()
    orchestrator = StoryRunOrchestrator(provider=provider, store=store)
    scheduler = PersistentRunScheduler(orchestrator, max_workers=1)
    app = create_app(orchestrator, scheduler=scheduler)

    with TestClient(app) as client:
        created = client.post(
            "/api/batches",
            json={
                "items": [
                    {"idea": "running child", "approval_mode": "auto"},
                    {"idea": "paused child", "approval_mode": "auto"},
                ]
            },
        )
        assert created.status_code == 202
        batch_id = created.json()["batch_id"]
        assert provider.started.wait(timeout=2)

        pause = client.post(f"/api/batches/{batch_id}/pause")

        assert pause.status_code == 200
        paused_body = pause.json()
        assert paused_body["paused"] is True
        assert paused_body["summary"]["paused"] == 1
        assert paused_body["summary"]["running"] == 1

        provider.release.set()
        assert scheduler.wait_for_idle(timeout=5)
        held = client.get(f"/api/batches/{batch_id}").json()
        assert held["status"] == "paused"
        assert held["summary"]["completed"] == 1
        assert held["summary"]["paused"] == 1

        resume = client.post(f"/api/batches/{batch_id}/resume")

        assert resume.status_code == 200
        assert resume.json()["paused"] is False
        assert scheduler.wait_for_idle(timeout=5)
        final = client.get(f"/api/batches/{batch_id}").json()
        assert final["status"] == "completed"
        assert final["summary"]["completed"] == 2


def test_async_api_returns_accepted_before_background_work_finishes():
    provider = BlockingFakeProvider()
    store = InMemoryRunStore()
    orchestrator = StoryRunOrchestrator(provider=provider, store=store)
    scheduler = PersistentRunScheduler(orchestrator, max_workers=1)
    app = create_app(orchestrator, scheduler=scheduler)

    with TestClient(app) as client:
        response = client.post(
            "/api/runs",
            json={"idea": "真正异步", "approval_mode": "auto"},
        )

        assert response.status_code == 202
        body = response.json()
        assert body["status"] in {"queued", "running"}
        assert body["status"] != "completed"

        provider.release.set()
        final = _wait_for_status(store, body["run_id"], {"completed"})
        assert final.script["title"]


def test_async_api_run_idempotency_key_does_not_queue_duplicate_work():
    provider = BlockingFakeProvider()
    store = InMemoryRunStore()
    orchestrator = StoryRunOrchestrator(provider=provider, store=store)
    scheduler = PersistentRunScheduler(orchestrator, max_workers=1)
    app = create_app(orchestrator, scheduler=scheduler)
    payload = {
        "idempotency_key": "async-run-same-click",
        "idea": "async same",
        "approval_mode": "auto",
    }

    with TestClient(app) as client:
        first = client.post("/api/runs", json=payload)
        second = client.post("/api/runs", json=payload)

        assert first.status_code == 202
        assert second.status_code == 202
        assert second.json()["run_id"] == first.json()["run_id"]
        provider.release.set()
        final = _wait_for_status(store, first.json()["run_id"], {"completed"})
        assert final.status == "completed"
        assert provider.calls == [
            "chief_screenwriter",
            "deepseek_polish",
            "gpt_prompt_writer",
            "gpt_prompt_audit",
        ]


def test_manual_async_run_waits_for_approval_then_continues_in_background():
    provider = FakeModelProvider.minimal_success()
    store = InMemoryRunStore()
    orchestrator = StoryRunOrchestrator(provider=provider, store=store)
    scheduler = PersistentRunScheduler(orchestrator, max_workers=1)
    app = create_app(orchestrator, scheduler=scheduler)

    with TestClient(app) as client:
        created = client.post(
            "/api/runs",
            json={"idea": "人工确认", "approval_mode": "manual"},
        )
        run_id = created.json()["run_id"]
        waiting = _wait_for_status(store, run_id, {"awaiting_approval"})

        assert waiting.current_stage == "core_selection"
        assert provider.calls == ["chief_screenwriter"]

        approved = client.post(
            f"/api/runs/{run_id}/approve",
            json={"selected_core_index": 0},
        )
        assert approved.status_code == 200
        assert approved.json()["status"] in {"queued", "running", "completed"}
        final = _wait_for_status(store, run_id, {"completed"})

        assert final.last_completed_stage == "final_prompts"
        assert provider.calls == [
            "chief_screenwriter",
            "deepseek_polish",
            "gpt_prompt_writer",
            "gpt_prompt_audit",
        ]


def test_batch_summary_refreshes_as_background_runs_finish():
    provider = FakeModelProvider.minimal_success()
    store = InMemoryRunStore()
    orchestrator = StoryRunOrchestrator(provider=provider, store=store)
    scheduler = PersistentRunScheduler(orchestrator, max_workers=2)

    batch = scheduler.create_batch(
        BatchRunRequest(
            items=[
                RunRequest(idea="批次一", approval_mode="auto"),
                RunRequest(idea="批次二", approval_mode="auto"),
            ]
        )
    )

    assert batch.status in {"queued", "running"}
    assert scheduler.wait_for_idle(timeout=5)
    saved = store.get_batch(batch.batch_id)
    assert saved.status == "completed"
    assert saved.summary["completed"] == 2
    assert all(item.status == "completed" for item in saved.items)
    scheduler.shutdown()


def test_batch_failure_policy_auto_retries_failed_child_once():
    provider = OneTimeAuditFailureProvider()
    store = InMemoryRunStore()
    orchestrator = StoryRunOrchestrator(provider=provider, store=store)
    scheduler = PersistentRunScheduler(orchestrator, max_workers=1)

    batch = scheduler.create_batch(
        BatchRunRequest(
            failure_policy={"auto_retry_failed_items": 1},
            items=[
                RunRequest(
                    idea="retry this failed item",
                    approval_mode="auto",
                    model_configs={"gpt_prompt_audit": {"max_attempts": 1}},
                ),
            ],
        )
    )
    assert scheduler.wait_for_idle(timeout=5)
    final = orchestrator.refresh_batch(batch.batch_id)
    run = store.get(final.items[0].run_id)

    assert final.status == "completed"
    assert final.summary["completed"] == 1
    assert run.status == "completed"
    assert run.retry_count == 1
    assert provider.calls.count("gpt_prompt_audit") == 2
    scheduler.shutdown()


def test_batch_failure_policy_does_not_auto_retry_unknown_failure():
    provider = AlwaysFailAuditProvider()
    store = InMemoryRunStore()
    orchestrator = StoryRunOrchestrator(provider=provider, store=store)
    scheduler = PersistentRunScheduler(orchestrator, max_workers=1)

    batch = scheduler.create_batch(
        BatchRunRequest(
            failure_policy={"auto_retry_failed_items": 1},
            items=[
                RunRequest(idea="hold unknown failure", approval_mode="auto"),
            ],
        )
    )
    assert scheduler.wait_for_idle(timeout=5)
    final = orchestrator.refresh_batch(batch.batch_id)
    run = store.get(final.items[0].run_id)

    assert final.status == "failed"
    assert final.summary["failed"] == 1
    assert run.status == "failed"
    assert run.retry_count == 0
    assert run.last_failure is not None
    assert run.last_failure.category == "unknown"
    assert run.last_failure.retryable is False
    assert provider.calls.count("gpt_prompt_audit") == 1
    scheduler.shutdown()


def test_batch_failure_policy_pauses_remaining_queue_after_failure_threshold():
    provider = AlwaysFailAuditProvider()
    store = InMemoryRunStore()
    orchestrator = StoryRunOrchestrator(provider=provider, store=store)
    scheduler = PersistentRunScheduler(orchestrator, max_workers=1)

    batch = scheduler.create_batch(
        BatchRunRequest(
            failure_policy={"pause_on_failure_count": 1},
            items=[
                RunRequest(idea="first failure", approval_mode="auto"),
                RunRequest(idea="held after threshold", approval_mode="auto"),
            ],
        )
    )
    assert scheduler.wait_for_idle(timeout=5)
    final = orchestrator.refresh_batch(batch.batch_id)

    assert final.paused is True
    assert final.status == "paused"
    assert final.summary["failed"] == 1
    assert final.summary["paused"] == 1
    assert store.get(final.items[0].run_id).status == "failed"
    assert store.get(final.items[1].run_id).status == "paused"
    assert provider.calls.count("gpt_prompt_audit") == 1
    scheduler.shutdown()


def test_batch_failure_policy_can_pause_by_failure_rate():
    provider = AlwaysFailAuditProvider()
    store = InMemoryRunStore()
    orchestrator = StoryRunOrchestrator(provider=provider, store=store)
    scheduler = PersistentRunScheduler(orchestrator, max_workers=1)

    batch = scheduler.create_batch(
        BatchRunRequest(
            failure_policy={"pause_on_failure_rate": 0.25},
            items=[
                RunRequest(idea="one failure reaches rate", approval_mode="auto"),
                RunRequest(idea="held two", approval_mode="auto"),
                RunRequest(idea="held three", approval_mode="auto"),
                RunRequest(idea="held four", approval_mode="auto"),
            ],
        )
    )
    assert scheduler.wait_for_idle(timeout=5)
    final = orchestrator.refresh_batch(batch.batch_id)

    assert final.paused is True
    assert final.status == "paused"
    assert final.summary["failed"] == 1
    assert final.summary["paused"] == 3
    assert provider.calls.count("gpt_prompt_audit") == 1
    scheduler.shutdown()
