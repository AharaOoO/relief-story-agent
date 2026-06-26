import json
from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image, ImageDraw

from relief_story_agent.api import create_app
from relief_story_agent.artifacts import (
    export_batch_artifact_package,
    read_batch_artifact_index,
    read_run_artifact_index,
    validate_batch_export_package,
    write_run_artifacts,
)
from relief_story_agent.grid_image import validate_grid_image
from relief_story_agent.models import (
    BatchRunItem,
    BatchRunState,
    ComfyUICancellation,
    ComfyUIOutput,
    ComfyUIRunConfig,
    FailureRecord,
    GridImageAsset,
    ModelAttempt,
    ModelUsageSummary,
    RunRequest,
    RunState,
    TemplatePaths,
)


def _completed_run_with_grid_asset(tmp_path):
    image_path = tmp_path / "source.png"
    image = Image.new("RGB", (1024, 1024), "white")
    draw = ImageDraw.Draw(image)
    for index, color in enumerate(["red", "green", "blue", "yellow"]):
        left = (index % 2) * 512
        top = (index // 2) * 512
        image.paste(color, (left, top, left + 512, top + 512))
        draw.line((left + 20, top + 20, left + 492, top + 492), fill="black", width=8)
    image.save(image_path)
    validated = validate_grid_image(
        image_path,
        min_dimension=512,
        max_bytes=10_000_000,
    )
    return RunState(
        run_id="run_grid_artifacts",
        request=RunRequest(
            idea="artifact grid",
            output_root=str(tmp_path / "runs"),
        ),
        status="completed",
        script={"duration_seconds": 4},
        storyboard=[
            {
                "shot_id": 1,
                "time_range": "0-4s",
                "description": "frame",
                "image_prompt": "frame",
                "negative_prompt": "",
                "comfyui_inputs": {"seed": 7},
            }
        ],
        final_storyboard=[
            {
                "shot_id": 1,
                "time_range": "0-4s",
                "description": "frame",
                "image_prompt": "frame",
                "negative_prompt": "",
                "comfyui_inputs": {"seed": 7},
            }
        ],
        grid_image_prompt="compiled prompt",
        grid_image_asset=GridImageAsset(
            source="manual",
            local_path=str(image_path),
            sha256=validated.sha256,
            mime_type="image/png",
            width=validated.width,
            height=validated.height,
            byte_size=validated.byte_size,
            comfyui_filename="run_grid_artifacts_hash.png",
            upload_status="accepted",
        ),
        grid_image_checkpoint="workflow_patched",
    )


def test_grid_image_artifacts_use_09_to_11_without_overwriting_timeline(tmp_path):
    run = _completed_run_with_grid_asset(tmp_path)

    artifact_dir = write_run_artifacts(run)

    assert (artifact_dir / "08_timeline.json").exists()
    assert (artifact_dir / "09_four_grid_prompt.json").exists()
    assert (artifact_dir / "10_four_grid_image.png").exists()
    assert (artifact_dir / "11_comfyui_upload.json").exists()
    manifest = json.loads((artifact_dir / "00_manifest.json").read_text(encoding="utf-8"))
    assert manifest["grid_image_asset"]["sha256"] == run.grid_image_asset.sha256


def test_write_run_artifacts_creates_script_storyboard_and_ltx_payload(tmp_path):
    run = RunState(
        run_id="run_test",
        request=RunRequest(idea="便利店夜晚", output_root=str(tmp_path)),
        script={
            "title": "多放了一双筷子",
            "duration_seconds": 90,
            "core_sentence": "有时候人只是需要被看见。",
        },
        storyboard=[
            {
                "shot_id": 1,
                "time_range": "0-10s",
                "description": "雨后便利店。",
                "image_prompt": "雨后便利店，疲惫上班族",
                "negative_prompt": "争吵",
                "comfyui_inputs": {"strength": 0.72},
            }
        ],
        final_storyboard=[
            {
                "shot_id": 1,
                "time_range": "0-10s",
                "description": "final prompt",
                "image_prompt": "final prompt for ltx",
                "negative_prompt": "争吵",
                "comfyui_inputs": {"strength": 0.72},
            }
        ],
        prompt_audit={"passed": True, "issues": []},
        model_attempts=[
            ModelAttempt(
                attempt_id="attempt_1",
                stage="gpt_prompt_writer",
                attempt_number=1,
                max_attempts=3,
                status="succeeded",
                prompt_tokens=100,
                completion_tokens=50,
                total_tokens=150,
                estimated_cost_usd=0.001,
            )
        ],
        model_usage_summary=ModelUsageSummary(
            total_requests=1,
            total_attempts=1,
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
            estimated_cost_usd=0.001,
        ),
    )
    run.add_event("stage_started", stage="chief_screenwriter", message="Chief screenwriter started.")
    run.add_event("stage_completed", stage="chief_screenwriter", message="Chief screenwriter completed.")

    artifact_dir = write_run_artifacts(run)

    assert artifact_dir.name == "run_test"
    assert (artifact_dir / "01_script.json").exists()
    assert (artifact_dir / "02_storyboard.json").exists()
    assert (artifact_dir / "03_ltx_payload.json").exists()
    assert (artifact_dir / "04_prompt_audit.json").exists()
    assert (artifact_dir / "05_final_prompts.json").exists()
    assert (artifact_dir / "06_model_execution.json").exists()
    assert (artifact_dir / "08_timeline.json").exists()
    assert (artifact_dir / "00_manifest.json").exists()
    assert "final prompt for ltx" in (artifact_dir / "03_ltx_payload.json").read_text(encoding="utf-8")
    assert '"total_tokens": 150' in (
        artifact_dir / "06_model_execution.json"
    ).read_text(encoding="utf-8")
    manifest = json.loads((artifact_dir / "00_manifest.json").read_text(encoding="utf-8"))
    artifact_names = [item["name"] for item in manifest["artifacts"]]
    assert artifact_names == [
        "script",
        "storyboard",
        "ltx_payload",
        "prompt_audit",
        "final_prompts",
        "model_execution",
        "comfyui_preview",
        "timeline",
    ]
    timeline = json.loads((artifact_dir / "08_timeline.json").read_text(encoding="utf-8"))
    assert timeline["summary"]["event_count"] == 2
    assert timeline["summary"]["stage_event_counts"]["chief_screenwriter"] == 2
    assert timeline["events"][0]["event_type"] == "stage_started"
    assert timeline["events"][1]["event_type"] == "stage_completed"
    assert manifest["timeline_summary"]["event_count"] == 2
    assert manifest["comfyui_prompt_ids"] == []
    assert manifest["comfyui_preview"]["enabled"] is False
    assert manifest["final_prompt_summary"]["shot_count"] == 1
    assert run.artifact_dir == str(artifact_dir)


def test_run_artifact_manifest_includes_final_prompt_and_comfyui_preview_trace(tmp_path):
    workflow_path = tmp_path / "workflow_api.json"
    workflow_path.write_text(
        json.dumps(
            {
                "1": {"class_type": "PromptNode", "inputs": {"text": "old"}},
                "2": {"class_type": "SeedNode", "inputs": {"seed": 0}},
            }
        ),
        encoding="utf-8",
    )
    run = RunState(
        run_id="run_trace",
        request=RunRequest(
            idea="trace",
            output_root=str(tmp_path),
            comfyui=ComfyUIRunConfig(
                enabled=True,
                endpoint="http://comfy.local",
                workflow_api_path=str(workflow_path),
                placeholder_map={
                    "positive": {
                        "node": "1",
                        "input": "text",
                        "source": "comfyui_inputs.positive",
                    },
                    "seed": {
                        "node": "2",
                        "input": "seed",
                        "source": "comfyui_inputs.seed",
                    },
                },
            ),
        ),
        script={"duration_seconds": 90},
        storyboard=[],
        final_storyboard=[
            {
                "shot_id": 1,
                "time_range": "0-10s",
                "description": "quiet shop",
                "image_prompt": "soft convenience store keyframe",
                "negative_prompt": "shouting, horror",
                "comfyui_inputs": {
                    "positive": "soft convenience store keyframe",
                    "seed": 2026,
                    "strength": 0.72,
                },
            }
        ],
    )

    artifact_dir = write_run_artifacts(run)
    manifest = json.loads((artifact_dir / "00_manifest.json").read_text(encoding="utf-8"))

    assert (artifact_dir / "07_comfyui_preview.json").exists()
    assert manifest["final_prompt_summary"]["shot_count"] == 1
    assert manifest["final_prompt_summary"]["shots"][0]["image_prompt"] == "soft convenience store keyframe"
    assert manifest["comfyui_preview"]["will_enqueue"] is False
    assert manifest["comfyui_preview"]["planned_count"] == 1
    preview_item = manifest["comfyui_preview"]["items"][0]
    assert preview_item["submission_key"] == "shot:1"
    assert preview_item["content_fingerprint"]
    assert preview_item["replacements"][0]["value_preview"] == "soft convenience store keyframe"


def test_run_artifact_manifest_includes_configuration_provenance(tmp_path):
    writer = tmp_path / "writer.md"
    writer.write_text("writer {{script_json}}", encoding="utf-8")
    audit = tmp_path / "audit.md"
    audit.write_text("audit {{script_json}} {{storyboard_json}}", encoding="utf-8")
    workflow_path = tmp_path / "workflow_api.json"
    workflow_path.write_text(
        json.dumps(
            {
                "1": {"class_type": "PromptNode", "inputs": {"text": "old"}},
                "2": {"class_type": "SeedNode", "inputs": {"seed": 0}},
            }
        ),
        encoding="utf-8",
    )
    placeholder_map_path = tmp_path / "placeholder_map.json"
    placeholder_map_path.write_text(
        json.dumps(
            {
                "positive": {"node": "1", "input": "text", "source": "image_prompt"},
                "seed": {"node": "2", "input": "seed", "source": "comfyui_inputs.seed"},
            }
        ),
        encoding="utf-8",
    )
    run = RunState(
        run_id="run_provenance",
        request=RunRequest(
            idea="provenance",
            output_root=str(tmp_path),
            template_paths=TemplatePaths(
                prompt_writer_template_path=str(writer),
                prompt_audit_template_path=str(audit),
            ),
            comfyui=ComfyUIRunConfig(
                enabled=True,
                workflow_api_path=str(workflow_path),
                placeholder_map_path=str(placeholder_map_path),
            ),
        ),
        script={"duration_seconds": 90},
        final_storyboard=[
            {
                "shot_id": 1,
                "time_range": "0-10s",
                "description": "quiet shop",
                "image_prompt": "soft convenience store keyframe",
                "negative_prompt": "shouting, horror",
                "comfyui_inputs": {"seed": 2026},
            }
        ],
    )

    artifact_dir = write_run_artifacts(run)
    manifest = json.loads((artifact_dir / "00_manifest.json").read_text(encoding="utf-8"))

    provenance = manifest["configuration_provenance"]
    files = provenance["files"]
    assert files["prompt_writer_template"]["path"] == str(writer)
    assert files["prompt_writer_template"]["exists"] is True
    assert files["prompt_writer_template"]["size_bytes"] > 0
    assert len(files["prompt_writer_template"]["sha256"]) == 64
    assert files["prompt_audit_template"]["path"] == str(audit)
    assert files["comfyui_workflow"]["path"] == str(workflow_path)
    assert files["placeholder_map"]["path"] == str(placeholder_map_path)
    assert len(provenance["fingerprint"]) == 64


def test_read_run_artifact_index_includes_existing_files_and_future_video_slots(tmp_path):
    run = RunState(
        run_id="run_index",
        request=RunRequest(idea="索引", output_root=str(tmp_path)),
        script={"duration_seconds": 90},
        storyboard=[{"shot_id": 1, "image_prompt": "雨后便利店"}],
        final_storyboard=[{"shot_id": 1, "image_prompt": "雨后便利店"}],
        prompt_audit={"passed": True},
        comfyui_prompt_ids=["prompt_1"],
    )
    write_run_artifacts(run)

    index = read_run_artifact_index(run)

    assert index["run_id"] == "run_index"
    assert index["comfyui_prompt_ids"] == ["prompt_1"]
    assert index["artifacts"][0]["exists"] is True
    assert index["expected_outputs"][0]["type"] == "video"


def test_run_artifacts_include_comfyui_cancellation_audit(tmp_path):
    run = RunState(
        run_id="run_cancel_audit",
        request=RunRequest(idea="cancel audit", output_root=str(tmp_path)),
        script={"duration_seconds": 90},
        comfyui_prompt_ids=["prompt_1"],
        comfyui_cancellations=[
            ComfyUICancellation(
                prompt_id="prompt_1",
                strategy="job_api",
                cancelled=True,
                remote_status="cancelled",
            )
        ],
    )

    artifact_dir = write_run_artifacts(run)
    manifest = json.loads((artifact_dir / "00_manifest.json").read_text(encoding="utf-8"))
    index = read_run_artifact_index(run)

    assert manifest["comfyui_cancellations"][0]["prompt_id"] == "prompt_1"
    assert manifest["comfyui_cancellations"][0]["strategy"] == "job_api"
    assert manifest["comfyui_cancellations"][0]["cancelled"] is True
    assert index["comfyui_cancellations"] == manifest["comfyui_cancellations"]


def test_api_returns_run_artifact_index(tmp_path):
    from relief_story_agent.orchestrator import InMemoryRunStore, StoryRunOrchestrator
    from relief_story_agent.providers import FakeModelProvider

    store = InMemoryRunStore()
    orchestrator = StoryRunOrchestrator(provider=FakeModelProvider.minimal_success(), store=store)
    run = orchestrator.create_run(
        RunRequest(idea="API 产物", approval_mode="auto", output_root=str(tmp_path))
    )
    client = TestClient(create_app(orchestrator))

    response = client.get(f"/api/runs/{run.run_id}/artifacts")

    assert response.status_code == 200
    body = response.json()
    assert body["run_id"] == run.run_id
    assert any(item["name"] == "final_prompts" for item in body["artifacts"])


def test_read_batch_artifact_index_summarizes_publishable_runs(tmp_path):
    run = RunState(
        run_id="run_publish",
        request=RunRequest(idea="publish", output_root=str(tmp_path)),
        status="completed",
        current_stage="completed",
        script={"title": "便利店的夜晚", "core_sentence": "人只是需要被看见。"},
        prompt_audit={"scores": {"empathy": 9}},
        comfyui_outputs=[
            ComfyUIOutput(
                prompt_id="prompt_1",
                filename="publish.mp4",
                media_type="video",
                local_path=str(tmp_path / "publish.mp4"),
            )
        ],
    )
    batch = BatchRunState(
        batch_id="batch_artifacts",
        status="partial_failed",
        summary={"total": 2, "completed": 1, "failed": 1},
        items=[
            BatchRunItem(
                index=0,
                run_id=run.run_id,
                idea="publish",
                status="completed",
                current_stage="completed",
            ),
            BatchRunItem(
                index=1,
                run_id="missing",
                idea="missing",
                status="failed",
                current_stage="failed",
            ),
        ],
    )

    index = read_batch_artifact_index(batch, [run])

    assert index["publish_ready_count"] == 1
    assert index["items"][0]["publish_ready"] is True
    assert index["items"][0]["primary_video_path"].endswith("publish.mp4")
    assert index["items"][0]["scores"]["empathy"] == 9
    assert index["items"][1]["publish_ready"] is False
    assert index["items"][1]["error"] == "run not found"


def test_read_batch_artifact_index_includes_audit_summary_usage_and_retryability(tmp_path):
    completed = RunState(
        run_id="run_completed_audit",
        request=RunRequest(idea="completed", output_root=str(tmp_path)),
        status="completed",
        current_stage="completed",
        script={"title": "Done", "core_sentence": "soft"},
        model_usage_summary=ModelUsageSummary(
            total_requests=3,
            total_attempts=4,
            retry_count=1,
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
            estimated_cost_usd=0.012,
        ),
        comfyui_outputs=[
            ComfyUIOutput(
                prompt_id="prompt_done",
                filename="done.mp4",
                media_type="video",
                local_path=str(tmp_path / "done.mp4"),
            )
        ],
    )
    failed = RunState(
        run_id="run_failed_audit",
        request=RunRequest(idea="failed", output_root=str(tmp_path)),
        status="failed",
        current_stage="failed",
        failed_stage="gpt_prompt_audit",
        error="axis issue",
        model_usage_summary=ModelUsageSummary(
            total_requests=2,
            total_attempts=2,
            prompt_tokens=40,
            completion_tokens=20,
            total_tokens=60,
            estimated_cost_usd=0.004,
        ),
    )
    batch = BatchRunState(
        batch_id="batch_audit",
        status="partial_failed",
        summary={"total": 2, "completed": 1, "failed": 1},
        items=[
            BatchRunItem(
                index=0,
                run_id=completed.run_id,
                idea="completed",
                status="completed",
                current_stage="completed",
            ),
            BatchRunItem(
                index=1,
                run_id=failed.run_id,
                idea="failed",
                status="failed",
                current_stage="failed",
                error="axis issue",
            ),
        ],
    )

    index = read_batch_artifact_index(batch, [completed, failed])

    assert index["audit_summary"]["total_items"] == 2
    assert index["audit_summary"]["publish_ready_count"] == 1
    assert index["audit_summary"]["failed_count"] == 1
    assert index["audit_summary"]["retryable_count"] == 1
    assert index["audit_summary"]["by_status"] == {"completed": 1, "failed": 1}
    assert index["audit_summary"]["by_failed_stage"] == {"gpt_prompt_audit": 1}
    assert index["audit_summary"]["usage"]["total_tokens"] == 210
    assert index["audit_summary"]["usage"]["estimated_cost_usd"] == 0.016
    assert index["items"][0]["retryable"] is False
    assert index["items"][1]["retryable"] is True
    assert index["items"][1]["retry_from_stage"] == "gpt_prompt_audit"
    assert index["items"][1]["failed_stage"] == "gpt_prompt_audit"
    assert index["items"][1]["model_usage_summary"]["total_tokens"] == 60


def test_batch_artifact_index_recommends_recovery_actions(tmp_path):
    completed = RunState(
        run_id="run_publish_action",
        request=RunRequest(idea="publish", output_root=str(tmp_path)),
        status="completed",
        current_stage="completed",
        comfyui_outputs=[
            ComfyUIOutput(
                prompt_id="prompt_done",
                filename="done.mp4",
                media_type="video",
                local_path=str(tmp_path / "done.mp4"),
            )
        ],
    )
    template_failed = RunState(
        run_id="run_template_action",
        request=RunRequest(idea="template", output_root=str(tmp_path)),
        status="failed",
        current_stage="failed",
        failed_stage="gpt_prompt_writer",
        error="Template missing required placeholder(s): script_json",
    )
    mapping_failed = RunState(
        run_id="run_mapping_action",
        request=RunRequest(idea="mapping", output_root=str(tmp_path)),
        status="failed",
        current_stage="failed",
        failed_stage="comfyui",
        error="placeholder_map 'positive' source 'comfyui_inputs.positive' was not found in shot",
    )
    audit_failed = RunState(
        run_id="run_audit_action",
        request=RunRequest(idea="audit", output_root=str(tmp_path)),
        status="failed",
        current_stage="failed",
        failed_stage="gpt_prompt_audit",
        error="axis issue",
    )
    generic_failed = RunState(
        run_id="run_retry_action",
        request=RunRequest(idea="retry", output_root=str(tmp_path)),
        status="failed",
        current_stage="failed",
        failed_stage="deepseek_polish",
        error="temporary model timeout",
    )
    batch = BatchRunState(
        batch_id="batch_actions",
        status="partial_failed",
        summary={"total": 5, "completed": 1, "failed": 4},
        items=[
            BatchRunItem(index=0, run_id=completed.run_id, idea="publish", status="completed", current_stage="completed"),
            BatchRunItem(index=1, run_id=template_failed.run_id, idea="template", status="failed", current_stage="failed"),
            BatchRunItem(index=2, run_id=mapping_failed.run_id, idea="mapping", status="failed", current_stage="failed"),
            BatchRunItem(index=3, run_id=audit_failed.run_id, idea="audit", status="failed", current_stage="failed"),
            BatchRunItem(index=4, run_id=generic_failed.run_id, idea="retry", status="failed", current_stage="failed"),
        ],
    )

    index = read_batch_artifact_index(
        batch,
        [completed, template_failed, mapping_failed, audit_failed, generic_failed],
    )
    actions = {item["run_id"]: item["recommended_action"] for item in index["items"]}

    assert actions["run_publish_action"]["code"] == "publish"
    assert actions["run_template_action"]["code"] == "fix_template"
    assert actions["run_mapping_action"]["code"] == "check_comfyui_mapping"
    assert actions["run_audit_action"]["code"] == "manual_review_prompt_audit"
    assert actions["run_retry_action"]["code"] == "retry_from_stage"
    assert actions["run_retry_action"]["retry_from_stage"] == "deepseek_polish"
    assert index["audit_summary"]["recommended_actions"]["publish"] == 1
    assert index["audit_summary"]["recommended_actions"]["fix_template"] == 1
    assert index["audit_summary"]["recommended_actions"]["check_comfyui_mapping"] == 1
    assert index["audit_summary"]["recommended_actions"]["manual_review_prompt_audit"] == 1
    assert index["audit_summary"]["recommended_actions"]["retry_from_stage"] == 1


def test_batch_artifact_index_does_not_auto_retry_unknown_structured_failure(tmp_path):
    run = RunState(
        run_id="run_unknown_failure",
        request=RunRequest(idea="unknown", output_root=str(tmp_path)),
        status="failed",
        current_stage="failed",
        failed_stage="deepseek_polish",
        error="surprising failure",
        last_failure=FailureRecord(
            stage="deepseek_polish",
            category="unknown",
            code="unknown_error",
            retryable=False,
            message="surprising failure",
        ),
    )
    batch = BatchRunState(
        batch_id="batch_unknown",
        items=[
            BatchRunItem(
                index=0,
                run_id=run.run_id,
                idea="unknown",
                status="failed",
                current_stage="failed",
            )
        ],
    )

    index = read_batch_artifact_index(batch, [run])
    item = index["items"][0]

    assert item["retryable"] is False
    assert item["recommended_action"]["code"] == "manual_review"
    assert item["last_failure"]["category"] == "unknown"


def test_batch_artifact_index_retries_structured_timeout(tmp_path):
    run = RunState(
        run_id="run_timeout_failure",
        request=RunRequest(idea="timeout", output_root=str(tmp_path)),
        status="failed",
        current_stage="failed",
        failed_stage="gpt_prompt_writer",
        error="read timeout",
        last_failure=FailureRecord(
            stage="gpt_prompt_writer",
            category="timeout",
            code="timeout",
            retryable=True,
            message="read timeout",
        ),
    )
    batch = BatchRunState(
        batch_id="batch_timeout",
        items=[
            BatchRunItem(
                index=0,
                run_id=run.run_id,
                idea="timeout",
                status="failed",
                current_stage="failed",
            )
        ],
    )

    index = read_batch_artifact_index(batch, [run])
    item = index["items"][0]

    assert item["retryable"] is True
    assert item["retry_from_stage"] == "gpt_prompt_writer"
    assert item["recommended_action"]["code"] == "retry_from_stage"


def test_export_batch_artifact_package_copies_publish_files(tmp_path):
    video_path = tmp_path / "run_export" / "comfyui_outputs" / "export.mp4"
    video_path.parent.mkdir(parents=True)
    video_path.write_bytes(b"video")
    run = RunState(
        run_id="run_export",
        request=RunRequest(idea="export", output_root=str(tmp_path)),
        status="completed",
        current_stage="completed",
        script={"title": "Export Story", "core_sentence": "soft"},
        final_storyboard=[{"shot_id": 1, "image_prompt": "soft"}],
        prompt_audit={"scores": {"empathy": 8}},
        comfyui_outputs=[
            ComfyUIOutput(
                prompt_id="prompt_1",
                filename="export.mp4",
                media_type="video",
                local_path=str(video_path),
            )
        ],
    )
    write_run_artifacts(run)
    batch = BatchRunState(
        batch_id="batch_export_fn",
        status="completed",
        summary={"total": 1, "completed": 1},
        items=[
            BatchRunItem(
                index=0,
                run_id=run.run_id,
                idea="export",
                status="completed",
                current_stage="completed",
            )
        ],
    )

    exported = export_batch_artifact_package(
        batch,
        [run],
        export_root=tmp_path / "exports",
        include_zip=False,
    )

    item = exported["items"][0]
    assert exported["zip_path"] == ""
    assert item["exported_files"]["video"].endswith("video_export.mp4")
    assert Path(item["exported_files"]["video"]).read_bytes() == b"video"
    assert any(path.endswith("05_final_prompts.json") for path in item["exported_files"]["run_artifacts"])


def test_export_batch_artifact_package_writes_publish_index_json_and_csv(tmp_path):
    ready_video = tmp_path / "run_ready" / "comfyui_outputs" / "ready.mp4"
    ready_video.parent.mkdir(parents=True)
    ready_video.write_bytes(b"ready-video")
    ready = RunState(
        run_id="run_ready",
        request=RunRequest(idea="ready idea", output_root=str(tmp_path)),
        status="completed",
        current_stage="completed",
        script={"title": "Ready Story", "core_sentence": "soft core"},
        prompt_audit={"scores": {"empathy": 9, "visual_generability": 8}},
        comfyui_outputs=[
            ComfyUIOutput(
                prompt_id="prompt_ready",
                filename="ready.mp4",
                media_type="video",
                local_path=str(ready_video),
            )
        ],
    )
    failed = RunState(
        run_id="run_failed",
        request=RunRequest(idea="failed idea", output_root=str(tmp_path)),
        status="failed",
        current_stage="failed",
        failed_stage="gpt_prompt_audit",
        error="axis issue",
    )
    batch = BatchRunState(
        batch_id="batch_publish_index",
        status="partial_failed",
        summary={"total": 2, "completed": 1, "failed": 1},
        items=[
            BatchRunItem(index=0, run_id=ready.run_id, idea=ready.request.idea, status=ready.status, current_stage=ready.current_stage),
            BatchRunItem(index=1, run_id=failed.run_id, idea=failed.request.idea, status=failed.status, current_stage=failed.current_stage),
        ],
    )

    exported = export_batch_artifact_package(
        batch,
        [ready, failed],
        export_root=tmp_path / "exports",
        include_zip=False,
    )

    publish_index_path = Path(exported["publish_index_files"]["json"])
    publish_csv_path = Path(exported["publish_index_files"]["csv"])
    assert publish_index_path.exists()
    assert publish_csv_path.exists()
    publish_index = json.loads(publish_index_path.read_text(encoding="utf-8"))
    assert publish_index["batch_id"] == "batch_publish_index"
    assert publish_index["publish_ready_count"] == 1
    assert len(publish_index["items"]) == 2
    ready_item = publish_index["items"][0]
    failed_item = publish_index["items"][1]
    assert ready_item["publish_ready"] is True
    assert ready_item["title"] == "Ready Story"
    assert ready_item["core_sentence"] == "soft core"
    assert ready_item["scores"]["empathy"] == 9
    assert ready_item["exported_video_path"].endswith("video_ready.mp4")
    assert ready_item["publish_video_path"].replace("\\", "/").endswith("publish_videos/000_Ready_Story.mp4")
    assert Path(ready_item["publish_video_path"]).read_bytes() == b"ready-video"
    assert failed_item["publish_ready"] is False
    assert failed_item["publish_video_path"] == ""
    assert failed_item["recommended_action_code"] == "manual_review_prompt_audit"
    publish_videos = sorted((Path(exported["export_dir"]) / "publish_videos").glob("*.mp4"))
    assert [path.name for path in publish_videos] == ["000_Ready_Story.mp4"]
    csv_text = publish_csv_path.read_text(encoding="utf-8-sig")
    assert "Ready Story" in csv_text
    assert "soft core" in csv_text
    assert "publish_videos/000_Ready_Story.mp4" in csv_text.replace("\\", "/")
    assert "manual_review_prompt_audit" in csv_text

    release_notes_path = Path(exported["release_notes_path"])
    assert release_notes_path.exists()
    release_notes = release_notes_path.read_text(encoding="utf-8")
    assert "Relief Story Batch Export" in release_notes
    assert "batch_publish_index" in release_notes
    assert "publish_index.csv" in release_notes
    assert "publish_videos/000_Ready_Story.mp4" in release_notes.replace("\\", "/")
    assert "manual_review_prompt_audit" in release_notes


def test_validate_batch_export_package_reports_missing_publish_video(tmp_path):
    ready_video = tmp_path / "run_ready" / "comfyui_outputs" / "ready.mp4"
    ready_video.parent.mkdir(parents=True)
    ready_video.write_bytes(b"ready-video")
    ready = RunState(
        run_id="run_ready_validate",
        request=RunRequest(idea="ready validate", output_root=str(tmp_path)),
        status="completed",
        current_stage="completed",
        script={"title": "Ready Validate", "core_sentence": "soft core"},
        comfyui_outputs=[
            ComfyUIOutput(
                prompt_id="prompt_ready",
                filename="ready.mp4",
                media_type="video",
                local_path=str(ready_video),
            )
        ],
    )
    batch = BatchRunState(
        batch_id="batch_validate_export",
        status="completed",
        summary={"total": 1, "completed": 1},
        items=[
            BatchRunItem(index=0, run_id=ready.run_id, idea=ready.request.idea, status=ready.status, current_stage=ready.current_stage),
        ],
    )
    exported = export_batch_artifact_package(
        batch,
        [ready],
        export_root=tmp_path / "exports",
        include_zip=False,
    )

    ok = validate_batch_export_package(exported["export_dir"])

    assert ok["valid"] is True
    assert ok["summary"]["failed"] == 0
    assert ok["summary"]["passed"] >= 1

    Path(ok["publish_items"][0]["publish_video_path"]).unlink()
    broken = validate_batch_export_package(exported["export_dir"])

    assert broken["valid"] is False
    assert broken["summary"]["failed"] == 1
    failed_checks = [check for check in broken["checks"] if check["status"] == "failed"]
    assert failed_checks[0]["name"] == "publish_video_exists"
    assert failed_checks[0]["details"]["run_id"] == "run_ready_validate"


def test_validate_batch_export_package_reports_publish_video_checksum_mismatch(tmp_path):
    ready_video = tmp_path / "run_ready" / "comfyui_outputs" / "ready.mp4"
    ready_video.parent.mkdir(parents=True)
    ready_video.write_bytes(b"original-video")
    ready = RunState(
        run_id="run_ready_checksum",
        request=RunRequest(idea="ready checksum", output_root=str(tmp_path)),
        status="completed",
        current_stage="completed",
        script={"title": "Checksum Story", "core_sentence": "soft core"},
        comfyui_outputs=[
            ComfyUIOutput(
                prompt_id="prompt_ready",
                filename="ready.mp4",
                media_type="video",
                local_path=str(ready_video),
            )
        ],
    )
    batch = BatchRunState(
        batch_id="batch_validate_checksum",
        status="completed",
        summary={"total": 1, "completed": 1},
        items=[
            BatchRunItem(index=0, run_id=ready.run_id, idea=ready.request.idea, status=ready.status, current_stage=ready.current_stage),
        ],
    )
    exported = export_batch_artifact_package(
        batch,
        [ready],
        export_root=tmp_path / "exports",
        include_zip=False,
    )
    ok = validate_batch_export_package(exported["export_dir"])
    publish_item = ok["publish_items"][0]

    assert ok["valid"] is True
    assert publish_item["publish_video_size_bytes"] == len(b"original-video")
    assert len(publish_item["publish_video_sha256"]) == 64

    Path(publish_item["publish_video_path"]).write_bytes(b"corrupted-video")
    broken = validate_batch_export_package(exported["export_dir"])

    assert broken["valid"] is False
    failed_checks = [check for check in broken["checks"] if check["status"] == "failed"]
    assert failed_checks[0]["name"] == "publish_video_checksum"
    assert failed_checks[0]["details"]["run_id"] == "run_ready_checksum"
    assert failed_checks[0]["details"]["expected_size_bytes"] == len(b"original-video")
    assert failed_checks[0]["details"]["actual_size_bytes"] == len(b"corrupted-video")


def test_validate_batch_export_package_reports_empty_publish_video(tmp_path):
    ready_video = tmp_path / "run_ready" / "comfyui_outputs" / "empty.mp4"
    ready_video.parent.mkdir(parents=True)
    ready_video.write_bytes(b"")
    ready = RunState(
        run_id="run_ready_empty_video",
        request=RunRequest(idea="ready empty", output_root=str(tmp_path)),
        status="completed",
        current_stage="completed",
        script={"title": "Empty Video Story", "core_sentence": "soft core"},
        comfyui_outputs=[
            ComfyUIOutput(
                prompt_id="prompt_ready",
                filename="empty.mp4",
                media_type="video",
                local_path=str(ready_video),
            )
        ],
    )
    batch = BatchRunState(
        batch_id="batch_validate_empty_video",
        status="completed",
        summary={"total": 1, "completed": 1},
        items=[
            BatchRunItem(index=0, run_id=ready.run_id, idea=ready.request.idea, status=ready.status, current_stage=ready.current_stage),
        ],
    )
    exported = export_batch_artifact_package(
        batch,
        [ready],
        export_root=tmp_path / "exports",
        include_zip=False,
    )
    broken = validate_batch_export_package(exported["export_dir"])

    assert broken["valid"] is False
    failed_checks = [check for check in broken["checks"] if check["status"] == "failed"]
    assert failed_checks[0]["name"] == "publish_video_non_empty"
    assert failed_checks[0]["details"]["run_id"] == "run_ready_empty_video"
    assert failed_checks[0]["details"]["size_bytes"] == 0
