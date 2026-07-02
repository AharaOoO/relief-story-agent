from __future__ import annotations

from fastapi.testclient import TestClient
from pydantic import ValidationError
import pytest

from relief_story_agent.api import create_app
from relief_story_agent.models import (
    ComfyUIRetryOverride,
    ComfyUIRunConfig,
    GridImageAsset,
    GridImageAttempt,
    GridImageConfig,
    GridImageRetryOverride,
    RunRequest,
    RunRetryRequest,
    SegmentRenderState,
    StageModelConfig,
)
from relief_story_agent.orchestrator import (
    InMemoryRunStore,
    RetryConfigurationConflict,
    StoryRunOrchestrator,
)
from relief_story_agent.providers import FakeModelProvider


def test_retry_request_accepts_only_public_grid_image_override_fields():
    request = RunRetryRequest.model_validate(
        {
            "from_stage": "four_grid_asset",
            "grid_image_override": {
                "runninghub_site": "cn",
                "aspect_ratio": "9:16",
                "resolution": "2k",
            },
        }
    )

    assert request.grid_image_override is not None
    assert request.grid_image_override.runninghub_site == "cn"
    assert request.grid_image_override.aspect_ratio == "9:16"
    assert "api_key" not in request.grid_image_override.model_dump()


def test_retry_request_rejects_secret_or_provider_override_fields():
    with pytest.raises(ValidationError):
        RunRetryRequest.model_validate(
            {
                "from_stage": "four_grid_asset",
                "grid_image_override": {
                    "runninghub_site": "cn",
                    "aspect_ratio": "16:9",
                    "resolution": "2k",
                    "api_key": "must-not-enter-run-state",
                },
            }
        )


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


def _failed_quality_gate_run(orchestrator: StoryRunOrchestrator):
    run = orchestrator.prepare_run(
        RunRequest(
            idea="恢复质量门禁",
            approval_mode="auto",
            comfyui=ComfyUIRunConfig(
                enabled=True,
                endpoint="http://127.0.0.1:8188",
                workflow_api_path="D:/workflows/original.json",
                grid_image=GridImageConfig(
                    provider="runninghub_image_task",
                    runninghub_site="ai",
                    model="rhart-image-g-2",
                    aspect_ratio="16:9",
                    resolution="2k",
                ),
            ),
        )
    )
    run.status = "failed"
    run.current_stage = "failed"
    run.failed_stage = "quality_gate"
    run.script = {"title": "保留已完成剧本", "duration_seconds": 150}
    run.add_event("stage_completed", stage="chief_screenwriter")
    run.add_event("stage_completed", stage="deepseek_polish")
    orchestrator.store.save(run)
    return run


def test_queue_retry_applies_model_and_prompt_overrides_to_unfinished_stages():
    orchestrator = StoryRunOrchestrator(
        provider=FakeModelProvider.minimal_success(),
        store=InMemoryRunStore(),
    )
    failed = _failed_quality_gate_run(orchestrator)

    queued = orchestrator.queue_retry(
        failed.run_id,
        RunRetryRequest(
            from_stage="quality_gate",
            model_config_overrides={
                "quality_gate": StageModelConfig(
                    provider_mode="runninghub",
                    runninghub_site="cn",
                    model="glm-5.2",
                ),
                "gpt_prompt_writer": StageModelConfig(
                    provider_mode="runninghub",
                    runninghub_site="ai",
                    model="anthropic/claude-sonnet-5",
                ),
            },
            prompt_overrides={
                "quality_gate": "新的质量门禁提示词",
                "gpt_prompt_writer": "新的分镜提示词",
            },
        ),
    )

    assert queued.status == "queued"
    assert queued.resume_stage == "quality_gate"
    assert queued.request.model_configs["quality_gate"].model == "glm-5.2"
    assert (
        queued.request.model_configs["gpt_prompt_writer"].model
        == "anthropic/claude-sonnet-5"
    )
    assert queued.prompt_snapshot["quality_gate"] == "新的质量门禁提示词"
    assert queued.prompt_snapshot["gpt_prompt_writer"] == "新的分镜提示词"
    assert queued.script == {"title": "保留已完成剧本", "duration_seconds": 150}
    assert {item["stage"] for item in queued.retry_configuration_history} >= {
        "quality_gate",
        "gpt_prompt_writer",
    }


def test_queue_retry_rejects_override_for_a_completed_stage_without_mutation():
    orchestrator = StoryRunOrchestrator(
        provider=FakeModelProvider.minimal_success(),
        store=InMemoryRunStore(),
    )
    failed = _failed_quality_gate_run(orchestrator)

    with pytest.raises(RetryConfigurationConflict, match="completed successfully"):
        orchestrator.queue_retry(
            failed.run_id,
            RunRetryRequest(
                from_stage="quality_gate",
                model_config_overrides={
                    "deepseek_polish": StageModelConfig(
                        provider_mode="runninghub",
                        runninghub_site="cn",
                        model="deepseek/deepseek-v4-pro",
                    )
                },
            ),
        )

    persisted = orchestrator.store.get(failed.run_id)
    assert persisted.status == "failed"
    assert "deepseek_polish" not in persisted.request.model_configs
    assert persisted.retry_configuration_history == []


def test_queue_retry_can_update_future_grid_and_comfyui_configuration():
    orchestrator = StoryRunOrchestrator(
        provider=FakeModelProvider.minimal_success(),
        store=InMemoryRunStore(),
    )
    failed = _failed_quality_gate_run(orchestrator)

    queued = orchestrator.queue_retry(
        failed.run_id,
        RunRetryRequest(
            from_stage="quality_gate",
            grid_image_override=GridImageRetryOverride(
                runninghub_site="cn",
                aspect_ratio="9:16",
                resolution="1k",
            ),
            comfyui_override=ComfyUIRetryOverride(
                endpoint="http://127.0.0.1:8288",
                workflow_api_path="D:/workflows/recovered.json",
                output_timeout_seconds=1200,
            ),
        ),
    )

    assert queued.request.comfyui is not None
    assert queued.request.comfyui.grid_image.runninghub_site == "cn"
    assert queued.request.comfyui.grid_image.aspect_ratio == "9:16"
    assert queued.request.comfyui.endpoint == "http://127.0.0.1:8288"
    assert queued.request.comfyui.workflow_api_path == "D:/workflows/recovered.json"
    assert queued.request.comfyui.output_timeout_seconds == 1200


def _failed_grid_run(orchestrator: StoryRunOrchestrator):
    run = orchestrator.prepare_run(
        RunRequest(
            idea="恢复四宫格",
            approval_mode="auto",
            comfyui=ComfyUIRunConfig(
                enabled=True,
                grid_image=GridImageConfig(
                    provider="runninghub_image_task",
                    runninghub_site="ai",
                    model="rhart-image-g-2",
                    aspect_ratio="16:9",
                    resolution="2k",
                ),
            ),
        )
    )
    run.status = "failed"
    run.current_stage = "failed"
    run.failed_stage = "four_grid_asset"
    run.script = {"title": "保留前序剧本"}
    run.grid_image_asset = GridImageAsset(
        source="generated",
        local_path="D:/runs/old-grid.png",
        sha256="a" * 64,
        mime_type="image/png",
        width=2048,
        height=1152,
        byte_size=1024,
    )
    run.grid_image_attempts = [GridImageAttempt(attempt_number=1, status="failed")]
    run.grid_image_checkpoint = "image_validated"
    run.grid_image_replacements = [{"node": "196", "input": "image"}]
    orchestrator.store.save(run)
    return run


def test_queue_retry_applies_grid_override_and_clears_only_grid_checkpoint_state():
    orchestrator = StoryRunOrchestrator(
        provider=FakeModelProvider.minimal_success(),
        store=InMemoryRunStore(),
    )
    failed = _failed_grid_run(orchestrator)

    queued = orchestrator.queue_retry(
        failed.run_id,
        RunRetryRequest(
            from_stage="four_grid_asset",
            grid_image_override=GridImageRetryOverride(
                runninghub_site="cn",
                aspect_ratio="9:16",
                resolution="1k",
            ),
        ),
    )

    assert queued.request.comfyui is not None
    assert queued.request.comfyui.grid_image.runninghub_site == "cn"
    assert queued.request.comfyui.grid_image.aspect_ratio == "9:16"
    assert queued.request.comfyui.grid_image.resolution == "1k"
    assert queued.request.creation_spec.video_aspect_ratio == "9:16"
    assert queued.request.creation_spec.image_resolution == "1k"
    assert queued.grid_image_asset is None
    assert queued.grid_image_attempts == []
    assert queued.grid_image_checkpoint == ""
    assert queued.grid_image_replacements == []
    assert queued.script == {"title": "保留前序剧本"}
    assert queued.retry_configuration_history[-1]["before"]["runninghub_site"] == "ai"
    assert queued.retry_configuration_history[-1]["after"]["runninghub_site"] == "cn"
    assert any(event.event_type == "retry_configuration_updated" for event in queued.events)


def test_queue_retry_with_segment_id_clears_only_target_segment():
    orchestrator = StoryRunOrchestrator(
        provider=FakeModelProvider.minimal_success(),
        store=InMemoryRunStore(),
    )
    failed = _failed_grid_run(orchestrator)
    failed.segment_renders = [
        SegmentRenderState(
            segment_id=f"segment-{index}",
            shot_id=str(index),
            order=index,
            authored_time_range=f"{index - 1}-{index}s",
            render_time_range=f"{index - 1}-{index}s",
            duration_seconds=1,
            frame_count=24,
            local_frame_indices=[0, 8, 15, 23],
            positive_prompt=f"prompt {index}",
            grid_panel_prompts=[f"panel {panel}" for panel in range(4)],
            grid_image_asset=GridImageAsset(
                source="generated",
                local_path=f"D:/runs/segment-{index}.png",
                sha256=str(index) * 64,
                mime_type="image/png",
                width=2048,
                height=1152,
                byte_size=1024,
            ),
            grid_image_checkpoint="workflow_patched",
            status="image_ready" if index == 1 else "failed",
            error="image request failed" if index == 2 else "",
        )
        for index in (1, 2)
    ]
    orchestrator.store.save(failed)

    queued = orchestrator.queue_retry(
        failed.run_id,
        RunRetryRequest(
            from_stage="four_grid_asset",
            grid_image_override=GridImageRetryOverride(
                segment_id="segment-2",
                runninghub_site="cn",
                aspect_ratio="9:16",
                resolution="1k",
            ),
        ),
    )

    first, second = queued.segment_renders
    assert first.status == "image_ready"
    assert first.grid_image_asset is not None
    assert first.grid_image_checkpoint == "workflow_patched"
    assert second.status == "planned"
    assert second.grid_image_asset is None
    assert second.grid_image_attempts == []
    assert second.grid_image_checkpoint == ""
    assert second.submission is None
    assert second.outputs == []
    assert second.error == ""


@pytest.mark.parametrize(
    ("status", "failed_stage", "from_stage"),
    [
        ("completed", "four_grid_asset", "four_grid_asset"),
        ("failed", "gpt_prompt_audit", "four_grid_asset"),
        ("failed", "four_grid_asset", "comfyui"),
    ],
)
def test_grid_override_rejects_incompatible_run_state(status, failed_stage, from_stage):
    orchestrator = StoryRunOrchestrator(
        provider=FakeModelProvider.minimal_success(),
        store=InMemoryRunStore(),
    )
    run = _failed_grid_run(orchestrator)
    run.status = status
    run.failed_stage = failed_stage
    orchestrator.store.save(run)

    with pytest.raises(ValueError, match="grid image retry override"):
        orchestrator.queue_retry(
            run.run_id,
            RunRetryRequest(
                from_stage=from_stage,
                grid_image_override=GridImageRetryOverride(
                    runninghub_site="cn",
                    aspect_ratio="16:9",
                    resolution="2k",
                ),
            ),
        )


def test_api_returns_conflict_when_grid_override_targets_a_stale_run_state():
    orchestrator = StoryRunOrchestrator(
        provider=FakeModelProvider.minimal_success(),
        store=InMemoryRunStore(),
    )
    run = _failed_grid_run(orchestrator)
    run.status = "completed"
    orchestrator.store.save(run)
    client = TestClient(create_app(orchestrator))

    response = client.post(
        f"/api/runs/{run.run_id}/retry",
        json={
            "from_stage": "four_grid_asset",
            "grid_image_override": {
                "runninghub_site": "cn",
                "aspect_ratio": "16:9",
                "resolution": "2k",
            },
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "retry_configuration_conflict"
