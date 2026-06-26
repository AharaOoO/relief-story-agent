from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from relief_story_agent.api import create_app
from relief_story_agent.artifacts import write_run_artifacts
from relief_story_agent.models import (
    BatchRetryRequest,
    BatchRunItem,
    BatchRunRequest,
    BatchRunState,
    ComfyUIOutput,
    RunRequest,
    RunState,
)
from relief_story_agent.orchestrator import InMemoryRunStore, StoryRunOrchestrator
from relief_story_agent.providers import FakeModelProvider


MINIMAL_MP4_BYTES = b"\x00\x00\x00\x18ftypisom\x00\x00\x02\x00isomiso2"


def test_run_idempotency_key_reuses_existing_run_without_duplicate_model_calls():
    provider = FakeModelProvider.minimal_success()
    store = InMemoryRunStore()
    orchestrator = StoryRunOrchestrator(provider=provider, store=store)
    request = RunRequest(
        idempotency_key="single-same-click",
        idea="single run",
        approval_mode="auto",
    )

    first = orchestrator.create_run(request)
    calls_after_first = list(provider.calls)
    second = orchestrator.create_run(request)

    assert second.run_id == first.run_id
    assert second.status == "completed"
    assert provider.calls == calls_after_first
    assert len(store.list_runs()) == 1


def test_orchestrator_creates_batch_with_independent_runs_and_summary():
    provider = FakeModelProvider.minimal_success()
    store = InMemoryRunStore()
    orchestrator = StoryRunOrchestrator(provider=provider, store=store)

    batch = orchestrator.create_batch(
        BatchRunRequest(
            items=[
                RunRequest(idea="便利店夜晚", approval_mode="auto"),
                RunRequest(idea="压力小怪物", approval_mode="auto"),
            ]
        )
    )

    saved = store.get_batch(batch.batch_id)
    assert saved.status == "completed"
    assert saved.summary == {
        "total": 2,
        "paused": 0,
        "completed": 2,
        "failed": 0,
        "cancelled": 0,
        "awaiting_approval": 0,
        "running": 0,
    }
    assert len(saved.items) == 2
    assert saved.items[0].run_id != saved.items[1].run_id
    assert store.get(saved.items[0].run_id).request.idea == "便利店夜晚"
    assert store.get(saved.items[1].run_id).request.idea == "压力小怪物"

def test_batch_defaults_are_inherited_and_item_values_can_override(tmp_path):
    provider = FakeModelProvider.minimal_success()
    store = InMemoryRunStore()
    orchestrator = StoryRunOrchestrator(provider=provider, store=store)
    workflow_path = tmp_path / "workflow_api.json"
    writer_path = tmp_path / "writer.md"

    batch = orchestrator.create_batch(
        BatchRunRequest(
            defaults={
                "approval_mode": "auto",
                "output_root": str(tmp_path / "runs"),
                "preferred_style": "realistic",
                "queue_priority": 4,
                "template_paths": {"prompt_writer_template_path": str(writer_path)},
                "comfyui": {
                    "enabled": True,
                    "endpoint": "http://comfy.local",
                    "workflow_api_path": str(workflow_path),
                },
            },
            items=[
                RunRequest(idea="inherits defaults"),
                RunRequest(idea="overrides style", preferred_style="q version"),
                RunRequest(
                    idea="overrides comfy endpoint",
                    comfyui={"endpoint": "http://item-comfy.local"},
                ),
            ],
        )
    )

    first = store.get(batch.items[0].run_id).request
    second = store.get(batch.items[1].run_id).request
    third = store.get(batch.items[2].run_id).request
    assert first.approval_mode == "auto"
    assert first.queue_priority == 4
    assert first.output_root == str(tmp_path / "runs")
    assert first.preferred_style == "realistic"
    assert first.template_paths.prompt_writer_template_path == str(writer_path)
    assert first.comfyui is not None
    assert first.comfyui.endpoint == "http://comfy.local"
    assert first.comfyui.workflow_api_path == str(workflow_path)
    assert second.preferred_style == "q version"
    assert second.queue_priority == 4
    assert second.output_root == str(tmp_path / "runs")
    assert third.comfyui is not None
    assert third.comfyui.enabled is True
    assert third.comfyui.endpoint == "http://item-comfy.local"
    assert third.comfyui.workflow_api_path == str(workflow_path)


def test_batch_idempotency_key_reuses_existing_batch_without_duplicate_runs():
    provider = FakeModelProvider.minimal_success()
    store = InMemoryRunStore()
    orchestrator = StoryRunOrchestrator(provider=provider, store=store)
    request = BatchRunRequest(
        idempotency_key="same-click",
        items=[
            RunRequest(idea="one click", approval_mode="auto"),
            RunRequest(idea="second item", approval_mode="auto"),
        ],
    )

    first = orchestrator.create_batch(request)
    calls_after_first = list(provider.calls)
    second = orchestrator.create_batch(request)

    assert second.batch_id == first.batch_id
    assert [item.run_id for item in second.items] == [item.run_id for item in first.items]
    assert provider.calls == calls_after_first
    assert len(store.list_batches()) == 1


def test_batch_idempotency_key_rejects_different_payload():
    provider = FakeModelProvider.minimal_success()
    store = InMemoryRunStore()
    orchestrator = StoryRunOrchestrator(provider=provider, store=store)

    orchestrator.create_batch(
        BatchRunRequest(
            idempotency_key="conflict-key",
            items=[RunRequest(idea="first", approval_mode="auto")],
        )
    )

    try:
        orchestrator.create_batch(
            BatchRunRequest(
                idempotency_key="conflict-key",
                items=[RunRequest(idea="changed", approval_mode="auto")],
            )
        )
    except ValueError as exc:
        assert "different request payload" in str(exc)
    else:
        raise AssertionError("expected idempotency conflict")


def test_batch_keeps_failed_item_isolated_from_other_runs():
    provider = FakeModelProvider.minimal_success()
    store = InMemoryRunStore()
    orchestrator = StoryRunOrchestrator(provider=provider, store=store)
    provider.responses.pop("gpt_prompt_audit")

    batch = orchestrator.create_batch(
        BatchRunRequest(
            items=[
                RunRequest(idea="会失败的任务", approval_mode="auto"),
                RunRequest(idea="也会失败但有独立状态", approval_mode="manual"),
            ]
        )
    )

    assert batch.status == "partial_failed"
    assert batch.summary["failed"] == 1
    assert batch.summary["awaiting_approval"] == 1
    assert batch.items[0].status == "failed"
    assert batch.items[1].status == "awaiting_approval"


def test_api_creates_and_fetches_batch_runs():
    provider = FakeModelProvider.minimal_success()
    store = InMemoryRunStore()
    app = create_app(StoryRunOrchestrator(provider=provider, store=store))
    client = TestClient(app)

    response = client.post(
        "/api/batches",
        json={
            "items": [
                {"idea": "便利店夜晚", "approval_mode": "auto"},
                {"idea": "未完成事务所", "approval_mode": "auto"},
            ]
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed"
    assert body["summary"]["completed"] == 2
    detail = client.get(f"/api/batches/{body['batch_id']}")
    assert detail.status_code == 200
    assert detail.json()["batch_id"] == body["batch_id"]


def test_api_lists_batches_with_status_filter_and_limit():
    provider = FakeModelProvider.minimal_success()
    store = InMemoryRunStore()
    app = create_app(StoryRunOrchestrator(provider=provider, store=store))
    client = TestClient(app)

    first = client.post(
        "/api/batches",
        json={
            "items": [
                {"idea": "first batch", "approval_mode": "auto"},
            ]
        },
    ).json()
    second = client.post(
        "/api/batches",
        json={
            "items": [
                {"idea": "second batch", "approval_mode": "auto"},
            ]
        },
    ).json()
    client.post(
        "/api/batches",
        json={
            "items": [
                {"idea": "manual batch", "approval_mode": "manual"},
            ]
        },
    )

    response = client.get("/api/batches", params={"status": "completed", "limit": 1})

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    assert body["limit"] == 1
    assert len(body["items"]) == 1
    assert body["items"][0]["batch_id"] == second["batch_id"]
    assert body["items"][0]["status"] == "completed"
    assert body["items"][0]["summary"]["completed"] == 1
    assert body["items"][0]["item_count"] == 1


def test_api_batch_list_exposes_paused_flag():
    provider = FakeModelProvider.minimal_success()
    store = InMemoryRunStore()
    orchestrator = StoryRunOrchestrator(provider=provider, store=store)
    batch = orchestrator.prepare_batch(
        BatchRunRequest(
            items=[
                RunRequest(idea="paused list item", approval_mode="auto"),
            ]
        )
    )
    orchestrator.pause_batch(batch.batch_id)
    client = TestClient(create_app(orchestrator))

    response = client.get("/api/batches")

    assert response.status_code == 200
    body = response.json()
    assert body["items"][0]["batch_id"] == batch.batch_id
    assert body["items"][0]["paused"] is True
    assert body["items"][0]["status"] == "paused"


def test_api_batch_list_exposes_failure_policy():
    provider = FakeModelProvider.minimal_success()
    store = InMemoryRunStore()
    app = create_app(StoryRunOrchestrator(provider=provider, store=store))
    client = TestClient(app)

    created = client.post(
        "/api/batches",
        json={
            "failure_policy": {
                "auto_retry_failed_items": 2,
                "pause_on_failure_rate": 0.5,
            },
            "items": [
                {"idea": "policy visible", "approval_mode": "manual"},
            ],
        },
    )
    response = client.get("/api/batches")

    assert created.status_code == 200
    assert response.status_code == 200
    policy = response.json()["items"][0]["failure_policy"]
    assert policy["auto_retry_failed_items"] == 2
    assert policy["pause_on_failure_rate"] == 0.5


def test_api_batch_plan_resolves_items_without_enqueueing_state():
    provider = FakeModelProvider.minimal_success()
    store = InMemoryRunStore()
    app = create_app(StoryRunOrchestrator(provider=provider, store=store))
    client = TestClient(app)

    response = client.post(
        "/api/batches/plan",
        json={
            "failure_policy": {
                "auto_retry_failed_items": 1,
                "pause_on_failure_count": 2,
            },
            "defaults": {
                "approval_mode": "auto",
                "queue_priority": 3,
                "preferred_style": "realistic",
                "comfyui": {
                    "enabled": False,
                    "workflow_api_path": "D:/ComfyUI/workflows/api.json",
                    "placeholder_map_path": "D:/relief_story_templates/placeholder_map.json",
                },
            },
            "items": [
                {"idea": "normal priority"},
                {"idea": "smoke test first", "queue_priority": 10},
            ],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["will_enqueue"] is False
    assert body["item_count"] == 2
    assert body["failure_policy"]["auto_retry_failed_items"] == 1
    assert body["items"][0]["idea"] == "normal priority"
    assert body["items"][0]["queue_priority"] == 3
    assert body["items"][0]["preferred_style"] == "realistic"
    assert body["items"][0]["placeholder_map_path"] == "D:/relief_story_templates/placeholder_map.json"
    assert body["items"][1]["queue_priority"] == 10
    assert [item["idea"] for item in body["execution_order"]] == [
        "smoke test first",
        "normal priority",
    ]
    assert body["validation"]["passed"] is True
    assert store.list_batches() == []
    assert store.list_runs() == []


def test_api_batch_plan_reports_validation_failures(tmp_path):
    provider = FakeModelProvider.minimal_success()
    store = InMemoryRunStore()
    app = create_app(StoryRunOrchestrator(provider=provider, store=store))
    client = TestClient(app)

    response = client.post(
        "/api/batches/plan",
        json={
            "items": [
                {
                    "idea": "invalid plan item",
                    "template_paths": {
                        "prompt_writer_template_path": str(tmp_path / "missing_writer.md"),
                    },
                    "comfyui": {
                        "enabled": True,
                        "workflow_api_path": str(tmp_path / "missing_workflow.json"),
                    },
                },
            ],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["validation"]["passed"] is False
    failed = {
        check["name"]
        for check in body["validation"]["items"][0]["checks"]
        if check["status"] == "failed"
    }
    assert "prompt_writer_template" in failed
    assert "comfyui_workflow" in failed
    assert store.list_batches() == []
    assert store.list_runs() == []


def test_api_lists_runs_for_one_batch():
    provider = FakeModelProvider.minimal_success()
    store = InMemoryRunStore()
    app = create_app(StoryRunOrchestrator(provider=provider, store=store))
    client = TestClient(app)

    batch = client.post(
        "/api/batches",
        json={
            "items": [
                {"idea": "batch item one", "approval_mode": "auto"},
                {"idea": "batch item two", "approval_mode": "auto"},
            ]
        },
    ).json()
    client.post(
        "/api/runs",
        json={"idea": "standalone", "approval_mode": "auto"},
    )

    response = client.get(
        "/api/runs",
        params={"parent_batch_id": batch["batch_id"]},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    assert {item["parent_batch_id"] for item in body["items"]} == {batch["batch_id"]}
    assert {item["idea"] for item in body["items"]} == {"batch item one", "batch item two"}


def test_api_run_and_batch_lists_expose_queue_priority():
    provider = FakeModelProvider.minimal_success()
    store = InMemoryRunStore()
    app = create_app(StoryRunOrchestrator(provider=provider, store=store))
    client = TestClient(app)

    run = client.post(
        "/api/runs",
        json={
            "idea": "priority standalone",
            "approval_mode": "manual",
            "queue_priority": 7,
        },
    ).json()
    batch = client.post(
        "/api/batches",
        json={
            "defaults": {"approval_mode": "manual", "queue_priority": 3},
            "items": [
                {"idea": "priority batch item"},
            ],
        },
    ).json()

    runs = client.get("/api/runs").json()
    batches = client.get("/api/batches").json()

    run_summary = next(item for item in runs["items"] if item["run_id"] == run["run_id"])
    batch_summary = next(item for item in batches["items"] if item["batch_id"] == batch["batch_id"])
    assert run_summary["queue_priority"] == 7
    assert batch_summary["items"][0]["queue_priority"] == 3


def test_api_batch_request_can_use_shared_defaults(tmp_path):
    provider = FakeModelProvider.minimal_success()
    store = InMemoryRunStore()
    app = create_app(StoryRunOrchestrator(provider=provider, store=store))
    client = TestClient(app)

    response = client.post(
        "/api/batches",
        json={
            "defaults": {
                "approval_mode": "auto",
                "output_root": str(tmp_path / "runs"),
                "preferred_style": "realistic",
            },
            "items": [
                {"idea": "inherits defaults"},
                {"idea": "overrides style", "preferred_style": "q version"},
            ],
        },
    )

    assert response.status_code == 200
    body = response.json()
    first = store.get(body["items"][0]["run_id"]).request
    second = store.get(body["items"][1]["run_id"]).request
    assert first.approval_mode == "auto"
    assert first.output_root == str(tmp_path / "runs")
    assert first.preferred_style == "realistic"
    assert second.preferred_style == "q version"


def test_api_batch_idempotency_key_returns_existing_batch():
    provider = FakeModelProvider.minimal_success()
    store = InMemoryRunStore()
    app = create_app(StoryRunOrchestrator(provider=provider, store=store))
    client = TestClient(app)
    payload = {
        "idempotency_key": "api-same-click",
        "items": [{"idea": "same", "approval_mode": "auto"}],
    }

    first = client.post("/api/batches", json=payload)
    calls_after_first = list(provider.calls)
    second = client.post("/api/batches", json=payload)

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["batch_id"] == first.json()["batch_id"]
    assert provider.calls == calls_after_first


def test_api_batch_idempotency_conflict_returns_409():
    provider = FakeModelProvider.minimal_success()
    store = InMemoryRunStore()
    app = create_app(StoryRunOrchestrator(provider=provider, store=store))
    client = TestClient(app)

    first = client.post(
        "/api/batches",
        json={
            "idempotency_key": "api-conflict",
            "items": [{"idea": "first", "approval_mode": "auto"}],
        },
    )
    second = client.post(
        "/api/batches",
        json={
            "idempotency_key": "api-conflict",
            "items": [{"idea": "changed", "approval_mode": "auto"}],
        },
    )

    assert first.status_code == 200
    assert second.status_code == 409
    assert "different request payload" in second.json()["detail"]


def test_batch_retry_only_retries_failed_items_and_refreshes_summary():
    provider = FakeModelProvider.minimal_success()
    provider.responses.pop("gpt_prompt_audit")
    store = InMemoryRunStore()
    orchestrator = StoryRunOrchestrator(provider=provider, store=store)
    batch = orchestrator.create_batch(
        BatchRunRequest(
            items=[
                RunRequest(idea="失败后重试", approval_mode="auto"),
                RunRequest(idea="等待人工确认", approval_mode="manual"),
            ]
        )
    )
    failed_run_id = batch.items[0].run_id
    manual_run_id = batch.items[1].run_id
    provider.responses["gpt_prompt_audit"] = {
        "passed": True,
        "issues": [],
        "revision_instructions": [],
        "scores": {},
    }
    provider.calls.clear()

    retried = orchestrator.retry_batch(
        batch.batch_id,
        BatchRetryRequest(from_stage="gpt_prompt_writer"),
    )

    assert retried.status == "awaiting_approval"
    assert retried.summary["completed"] == 1
    assert retried.summary["failed"] == 0
    assert retried.summary["awaiting_approval"] == 1
    assert retried.items[0].status == "completed"
    assert retried.items[1].status == "awaiting_approval"
    assert store.get(failed_run_id).retry_count == 1
    assert store.get(manual_run_id).retry_count == 0
    assert provider.calls == ["gpt_prompt_writer", "gpt_prompt_audit"]


def test_batch_cancel_stops_unfinished_items_and_preserves_completed_runs():
    provider = FakeModelProvider.minimal_success()
    store = InMemoryRunStore()
    orchestrator = StoryRunOrchestrator(provider=provider, store=store)
    batch = orchestrator.create_batch(
        BatchRunRequest(
            items=[
                RunRequest(idea="already done", approval_mode="auto"),
                RunRequest(idea="waiting for approval", approval_mode="manual"),
            ]
        )
    )
    completed_run_id = batch.items[0].run_id
    waiting_run_id = batch.items[1].run_id

    cancelled = orchestrator.cancel_batch(batch.batch_id)

    assert store.get(completed_run_id).status == "completed"
    assert store.get(waiting_run_id).status == "cancelled"
    assert cancelled.status == "partial_failed"
    assert cancelled.summary["completed"] == 1
    assert cancelled.summary["cancelled"] == 1
    assert cancelled.items[0].status == "completed"
    assert cancelled.items[1].status == "cancelled"


def test_batch_pause_and_resume_holds_queued_items_without_losing_state():
    provider = FakeModelProvider.minimal_success()
    store = InMemoryRunStore()
    orchestrator = StoryRunOrchestrator(provider=provider, store=store)
    batch = orchestrator.prepare_batch(
        BatchRunRequest(
            items=[
                RunRequest(idea="queued one", approval_mode="auto"),
                RunRequest(idea="queued two", approval_mode="auto"),
            ]
        )
    )

    paused = orchestrator.pause_batch(batch.batch_id)

    assert paused.paused is True
    assert paused.status == "paused"
    assert paused.summary["paused"] == 2
    assert all(store.get(item.run_id).status == "paused" for item in paused.items)

    resumed = orchestrator.resume_batch(batch.batch_id)

    assert resumed.paused is False
    assert resumed.status == "running"
    assert resumed.summary["running"] == 2
    assert all(store.get(item.run_id).status == "queued" for item in resumed.items)


def test_api_retries_only_failed_batch_items():
    provider = FakeModelProvider.minimal_success()
    provider.responses.pop("gpt_prompt_audit")
    store = InMemoryRunStore()
    app = create_app(StoryRunOrchestrator(provider=provider, store=store))
    client = TestClient(app)
    created = client.post(
        "/api/batches",
        json={
            "items": [
                {"idea": "失败项", "approval_mode": "auto"},
                {"idea": "待确认项", "approval_mode": "manual"},
            ]
        },
    ).json()
    provider.responses["gpt_prompt_audit"] = {
        "passed": True,
        "issues": [],
        "revision_instructions": [],
        "scores": {},
    }

    response = client.post(f"/api/batches/{created['batch_id']}/retry")

    assert response.status_code == 200
    body = response.json()
    assert body["summary"]["completed"] == 1
    assert body["summary"]["failed"] == 0
    assert body["summary"]["awaiting_approval"] == 1


def test_api_cancels_batch_unfinished_items():
    provider = FakeModelProvider.minimal_success()
    store = InMemoryRunStore()
    app = create_app(StoryRunOrchestrator(provider=provider, store=store))
    client = TestClient(app)
    created = client.post(
        "/api/batches",
        json={
            "items": [
                {"idea": "already done", "approval_mode": "auto"},
                {"idea": "waiting for approval", "approval_mode": "manual"},
            ]
        },
    ).json()

    response = client.post(f"/api/batches/{created['batch_id']}/cancel")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "partial_failed"
    assert body["summary"]["completed"] == 1
    assert body["summary"]["cancelled"] == 1
    assert body["items"][0]["status"] == "completed"
    assert body["items"][1]["status"] == "cancelled"


def test_api_returns_batch_artifact_index_for_publishing(tmp_path):
    store = InMemoryRunStore()
    completed = RunState(
        run_id="run_done",
        request=RunRequest(idea="done", output_root=str(tmp_path)),
        status="completed",
        current_stage="completed",
        script={
            "title": "多放了一双筷子",
            "core_sentence": "有时候人只是需要被看见。",
        },
        prompt_audit={"scores": {"empathy": 9, "visual_generation": 8}},
        comfyui_outputs=[
            ComfyUIOutput(
                prompt_id="prompt_1",
                node_id="12",
                filename="done.mp4",
                media_type="video",
                local_path=str(tmp_path / "run_done" / "comfyui_outputs" / "done.mp4"),
            )
        ],
    )
    failed = RunState(
        run_id="run_failed",
        request=RunRequest(idea="failed", output_root=str(tmp_path)),
        status="failed",
        current_stage="failed",
        error="quality gate failed",
    )
    write_run_artifacts(completed)
    store.save(completed)
    store.save(failed)
    store.save_batch(
        BatchRunState(
            batch_id="batch_publish",
            status="partial_failed",
            summary={"total": 2, "completed": 1, "failed": 1},
            items=[
                BatchRunItem(
                    index=0,
                    run_id="run_done",
                    idea="done",
                    status="completed",
                    current_stage="completed",
                ),
                BatchRunItem(
                    index=1,
                    run_id="run_failed",
                    idea="failed",
                    status="failed",
                    current_stage="failed",
                    error="quality gate failed",
                ),
            ],
        )
    )
    client = TestClient(
        create_app(
            StoryRunOrchestrator(
                provider=FakeModelProvider.minimal_success(),
                store=store,
            )
        )
    )

    response = client.get("/api/batches/batch_publish/artifacts")

    assert response.status_code == 200
    body = response.json()
    assert body["batch_id"] == "batch_publish"
    assert body["publish_ready_count"] == 1
    assert body["items"][0]["title"] == "多放了一双筷子"
    assert body["items"][0]["primary_video_path"].endswith("done.mp4")
    assert body["items"][0]["scores"]["empathy"] == 9
    assert body["items"][1]["error"] == "quality gate failed"
    assert body["audit_summary"]["total_items"] == 2
    assert body["audit_summary"]["failed_count"] == 1
    assert body["items"][1]["retryable"] is False
    assert body["items"][1]["recommended_action"]["code"] == "manual_review"


def test_api_exports_batch_artifacts_to_directory_and_zip(tmp_path):
    store = InMemoryRunStore()
    video_path = tmp_path / "run_done" / "comfyui_outputs" / "done.mp4"
    video_path.parent.mkdir(parents=True)
    video_path.write_bytes(MINIMAL_MP4_BYTES)
    completed = RunState(
        run_id="run_done",
        request=RunRequest(idea="done", output_root=str(tmp_path)),
        status="completed",
        current_stage="completed",
        script={"title": "Night Store", "core_sentence": "Seen softly."},
        final_storyboard=[{"shot_id": 1, "image_prompt": "soft night store"}],
        prompt_audit={"scores": {"empathy": 9}},
        comfyui_outputs=[
            ComfyUIOutput(
                prompt_id="prompt_1",
                node_id="12",
                filename="done.mp4",
                media_type="video",
                local_path=str(video_path),
            )
        ],
    )
    write_run_artifacts(completed)
    store.save(completed)
    store.save_batch(
        BatchRunState(
            batch_id="batch_export",
            status="completed",
            summary={"total": 1, "completed": 1},
            items=[
                BatchRunItem(
                    index=0,
                    run_id="run_done",
                    idea="done",
                    status="completed",
                    current_stage="completed",
                )
            ],
        )
    )
    client = TestClient(
        create_app(
            StoryRunOrchestrator(
                provider=FakeModelProvider.minimal_success(),
                store=store,
            )
        )
    )

    response = client.post(
        "/api/batches/batch_export/export",
        json={"export_root": str(tmp_path / "exports"), "include_zip": True},
    )

    assert response.status_code == 200
    body = response.json()
    export_dir = body["export_dir"]
    assert body["publish_ready_count"] == 1
    assert body["zip_path"].endswith("batch_export.zip")
    assert body["zip_package"]["path"].endswith("batch_export.zip")
    assert body["zip_package"]["size_bytes"] > 0
    assert len(body["zip_package"]["sha256"]) == 64
    assert body["zip_package"]["sha256_path"].endswith("batch_export.zip.sha256")
    assert (tmp_path / "exports" / "batch_export" / "batch_export_manifest.json").exists()
    assert (tmp_path / "exports" / "batch_export" / "000_Night_Store" / "video_done.mp4").read_bytes() == MINIMAL_MP4_BYTES
    assert (tmp_path / "exports" / "batch_export.zip").exists()
    assert (tmp_path / "exports" / "batch_export.zip.sha256").exists()
    assert body["items"][0]["exported_files"]["video"].endswith("video_done.mp4")
    assert body["items"][0]["export_dir"].startswith(export_dir)

    validate_zip = client.post(
        "/api/batches/batch_export/export/validate-zip",
        json={
            "zip_path": body["zip_path"],
            "expected_sha256": body["zip_package"]["sha256"],
            "expected_size_bytes": body["zip_package"]["size_bytes"],
        },
    )

    assert validate_zip.status_code == 200
    validation = validate_zip.json()
    assert validation["valid"] is True
    assert validation["zip_sha256"] == body["zip_package"]["sha256"]


def test_api_validates_batch_export_package(tmp_path):
    from relief_story_agent.artifacts import export_batch_artifact_package

    store = InMemoryRunStore()
    orchestrator = StoryRunOrchestrator(provider=FakeModelProvider.minimal_success(), store=store)
    video_path = tmp_path / "outputs" / "done.mp4"
    video_path.parent.mkdir(parents=True)
    video_path.write_bytes(MINIMAL_MP4_BYTES)
    run = RunState(
        run_id="run_export_validate",
        request=RunRequest(idea="export validate", output_root=str(tmp_path)),
        status="completed",
        current_stage="completed",
        script={"title": "Export Validate", "core_sentence": "soft"},
        comfyui_outputs=[
            ComfyUIOutput(
                prompt_id="prompt_done",
                filename="done.mp4",
                media_type="video",
                local_path=str(video_path),
            )
        ],
    )
    store.save(run)
    batch = BatchRunState(
        batch_id="batch_export_validate",
        status="completed",
        summary={"total": 1, "completed": 1},
        items=[
            BatchRunItem(index=0, run_id=run.run_id, idea=run.request.idea, status=run.status, current_stage=run.current_stage),
        ],
    )
    store.save_batch(batch)
    exported = export_batch_artifact_package(
        batch,
        [run],
        export_root=tmp_path / "exports",
        include_zip=False,
    )
    app = create_app(orchestrator)
    client = TestClient(app)

    response = client.post(
        "/api/batches/batch_export_validate/export/validate",
        json={"export_dir": exported["export_dir"], "save_report": True},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["valid"] is True
    assert body["summary"]["failed"] == 0
    assert body["report_path"].endswith("validation_report.json")
    report = json.loads(Path(body["report_path"]).read_text(encoding="utf-8"))
    assert report["valid"] is True
    assert report["export_dir"] == body["export_dir"]


def test_api_detects_export_zip_checksum_mismatch(tmp_path):
    from relief_story_agent.artifacts import export_batch_artifact_package

    store = InMemoryRunStore()
    orchestrator = StoryRunOrchestrator(provider=FakeModelProvider.minimal_success(), store=store)
    video_path = tmp_path / "outputs" / "done.mp4"
    video_path.parent.mkdir(parents=True)
    video_path.write_bytes(MINIMAL_MP4_BYTES)
    run = RunState(
        run_id="run_export_zip_validate",
        request=RunRequest(idea="export zip validate", output_root=str(tmp_path)),
        status="completed",
        current_stage="completed",
        script={"title": "Export Zip Validate", "core_sentence": "soft"},
        comfyui_outputs=[
            ComfyUIOutput(
                prompt_id="prompt_done",
                filename="done.mp4",
                media_type="video",
                local_path=str(video_path),
            )
        ],
    )
    store.save(run)
    batch = BatchRunState(
        batch_id="batch_export_zip_validate",
        status="completed",
        summary={"total": 1, "completed": 1},
        items=[
            BatchRunItem(index=0, run_id=run.run_id, idea=run.request.idea, status=run.status, current_stage=run.current_stage),
        ],
    )
    store.save_batch(batch)
    exported = export_batch_artifact_package(
        batch,
        [run],
        export_root=tmp_path / "exports",
        include_zip=True,
    )
    Path(exported["zip_path"]).write_bytes(b"not-a-real-zip")
    app = create_app(orchestrator)
    client = TestClient(app)

    response = client.post(
        "/api/batches/batch_export_zip_validate/export/validate-zip",
        json={
            "zip_path": exported["zip_path"],
            "expected_sha256": exported["zip_package"]["sha256"],
            "expected_size_bytes": exported["zip_package"]["size_bytes"],
            "save_report": True,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["valid"] is False
    failed = {check["name"]: check for check in body["checks"] if check["status"] == "failed"}
    assert "zip_integrity" in failed
    assert "zip_sha256" in failed
    assert "zip_size" in failed
    assert body["report_path"].endswith("batch_export_zip_validate.zip.validation.json")
    report = json.loads(Path(body["report_path"]).read_text(encoding="utf-8"))
    assert report["valid"] is False
    assert report["zip_path"] == body["zip_path"]
