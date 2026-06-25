import json
from pathlib import Path

import httpx
from PIL import Image, ImageDraw

from relief_story_agent.grid_image import acquire_generated_grid_image
from relief_story_agent.models import ComfyUIRunConfig, GridImageConfig, RunRequest, RunRetryRequest
from relief_story_agent.orchestrator import InMemoryRunStore, StoryRunOrchestrator
from relief_story_agent.providers import FakeModelProvider
from relief_story_agent.storage import JsonFileRunStore
from relief_story_agent.tests.fixtures.ltx23_workflow_factory import build_sanitized_ltx23_workflow


class FakeGeneratedGridProvider:
    def __init__(self, image_bytes):
        self.image_bytes = image_bytes
        self.calls = 0

    def generate(self, *, prompt, config):
        from relief_story_agent.grid_image import GeneratedImage

        self.calls += 1
        return GeneratedImage(
            content=self.image_bytes,
            mime_type="image/png",
            provider="fake",
            model=config.model,
        )


def _grid_png_bytes(tmp_path):
    path = tmp_path / "fixture_grid.png"
    image = Image.new("RGB", (1024, 1024), "white")
    draw = ImageDraw.Draw(image)
    colors = ["red", "green", "blue", "yellow"]
    for index, color in enumerate(colors):
        left = (index % 2) * 512
        top = (index // 2) * 512
        image.paste(color, (left, top, left + 512, top + 512))
        draw.line((left + 20, top + 20, left + 492, top + 492), fill="black", width=8)
    image.save(path)
    return path.read_bytes()


def _write_grid_workflow(tmp_path):
    path = tmp_path / "workflow.json"
    path.write_text(
        json.dumps(build_sanitized_ltx23_workflow(), ensure_ascii=False),
        encoding="utf-8",
    )
    return path


def _grid_request(tmp_path, *, output_root=None):
    return RunRequest(
        idea="grid run",
        approval_mode="auto",
        output_root=str(output_root or (tmp_path / "runs")),
        comfyui=ComfyUIRunConfig(
            enabled=True,
            workflow_api_path=str(_write_grid_workflow(tmp_path)),
        ),
    )


def _prepare_grid_run(tmp_path, provider):
    store = InMemoryRunStore()
    orchestrator = StoryRunOrchestrator(
        provider=FakeModelProvider.minimal_success(),
        store=store,
        grid_image_provider=provider,
    )
    return orchestrator, orchestrator.prepare_run(_grid_request(tmp_path))


def test_four_grid_stage_runs_after_prompt_audit_before_artifacts_and_comfyui(
    tmp_path,
    monkeypatch,
):
    provider = FakeGeneratedGridProvider(_grid_png_bytes(tmp_path))
    workflow_path = _write_grid_workflow(tmp_path)
    submitted = []
    monkeypatch.setattr(
        "relief_story_agent.orchestrator.upload_grid_image",
        lambda *args, **kwargs: "run_grid.png",
    )
    monkeypatch.setattr(
        "relief_story_agent.orchestrator.submit_storyboard",
        lambda *args, **kwargs: submitted.append(kwargs["grid_image_asset"]) or [],
    )
    orchestrator = StoryRunOrchestrator(
        provider=FakeModelProvider.minimal_success(),
        store=InMemoryRunStore(),
        grid_image_provider=provider,
    )

    run = orchestrator.create_run(
        RunRequest(
            idea="grid stage",
            approval_mode="auto",
            output_root=str(tmp_path / "runs"),
            comfyui=ComfyUIRunConfig(
                enabled=True,
                workflow_api_path=str(workflow_path),
            ),
        )
    )

    completed = [
        event.stage for event in run.events if event.event_type == "stage_completed"
    ]
    assert completed.index("gpt_prompt_audit") < completed.index("four_grid_asset")
    assert completed.index("four_grid_asset") < completed.index("artifacts")
    assert completed.index("artifacts") < completed.index("comfyui")
    assert run.grid_image_checkpoint == "workflow_patched"
    assert run.grid_image_asset.upload_status == "accepted"
    assert submitted[0].comfyui_filename == "run_grid.png"


def test_retry_after_upload_failure_reuses_acquired_image(tmp_path, monkeypatch):
    provider = FakeGeneratedGridProvider(_grid_png_bytes(tmp_path))
    calls = 0

    def flaky_upload(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise httpx.ConnectError(
                "offline",
                request=httpx.Request("POST", "http://comfy.local/upload/image"),
            )
        return "reused.png"

    monkeypatch.setattr("relief_story_agent.orchestrator.upload_grid_image", flaky_upload)
    orchestrator, run = _prepare_grid_run(tmp_path, provider)
    first = orchestrator.execute_scheduled(run.run_id)
    assert first.status == "failed"
    assert first.grid_image_checkpoint == "image_validated"
    assert provider.calls == 1

    orchestrator.queue_retry(run.run_id, RunRetryRequest(from_stage="four_grid_asset"))
    second = orchestrator.execute_scheduled(run.run_id)

    assert second.grid_image_asset.upload_status == "accepted"
    assert provider.calls == 1


def test_persistent_restart_reuses_generated_asset_after_comfyui_failure(tmp_path, monkeypatch):
    state_dir = tmp_path / "state"
    output_root = tmp_path / "runs"
    provider = FakeGeneratedGridProvider(_grid_png_bytes(tmp_path))
    first = StoryRunOrchestrator(
        provider=FakeModelProvider.minimal_success(),
        store=JsonFileRunStore(state_dir),
        grid_image_provider=provider,
    )
    run = first.prepare_run(_grid_request(tmp_path, output_root=output_root))
    monkeypatch.setattr(
        "relief_story_agent.orchestrator.upload_grid_image",
        lambda *args, **kwargs: "persisted.png",
    )
    monkeypatch.setattr(
        "relief_story_agent.orchestrator.submit_storyboard",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("comfy failed")),
    )

    first.execute_scheduled(run.run_id)
    failed = JsonFileRunStore(state_dir).get(run.run_id)
    assert failed.failed_stage == "comfyui"
    assert failed.grid_image_asset.comfyui_filename == "persisted.png"
    assert provider.calls == 1

    restarted = StoryRunOrchestrator(
        provider=FakeModelProvider.minimal_success(),
        store=JsonFileRunStore(state_dir),
        grid_image_provider=provider,
    )
    monkeypatch.setattr(
        "relief_story_agent.orchestrator.submit_storyboard",
        lambda *args, **kwargs: [],
    )
    restarted.queue_retry(run.run_id, RunRetryRequest(from_stage="comfyui"))
    completed = restarted.execute_scheduled(run.run_id)

    assert completed.status == "completed"
    assert provider.calls == 1
    assert completed.grid_image_asset.comfyui_filename == "persisted.png"


class ProviderMustNotRun:
    def generate(self, *, prompt, config):
        raise AssertionError("manual override must not call the image provider")


def test_manual_override_never_calls_image_provider(tmp_path, monkeypatch):
    image_path = tmp_path / "manual.png"
    image_path.write_bytes(_grid_png_bytes(tmp_path))
    request = _grid_request(tmp_path)
    request.comfyui.grid_image = GridImageConfig(
        mode="manual_override",
        manual_image_path=str(image_path),
    )
    monkeypatch.setattr(
        "relief_story_agent.orchestrator.upload_grid_image",
        lambda *args, **kwargs: "manual.png",
    )
    monkeypatch.setattr(
        "relief_story_agent.orchestrator.submit_storyboard",
        lambda *args, **kwargs: [],
    )
    orchestrator = StoryRunOrchestrator(
        provider=FakeModelProvider.minimal_success(),
        store=InMemoryRunStore(),
        grid_image_provider=ProviderMustNotRun(),
    )

    run = orchestrator.create_run(request)

    assert run.status == "completed"
    assert run.grid_image_asset.source == "manual"


def test_accepted_upload_receipt_skips_upload_endpoint(tmp_path, monkeypatch):
    provider = FakeGeneratedGridProvider(_grid_png_bytes(tmp_path))
    orchestrator, run = _prepare_grid_run(tmp_path, provider)
    artifact_dir = Path(run.request.output_root) / run.run_id
    asset = acquire_generated_grid_image(
        provider,
        artifact_dir=artifact_dir,
        prompt="persisted prompt",
        config=run.request.comfyui.grid_image,
    )
    asset.comfyui_filename = "accepted.png"
    asset.upload_status = "accepted"
    run.grid_image_prompt = "persisted prompt"
    run.grid_image_asset = asset
    run.grid_image_checkpoint = "image_uploaded"
    orchestrator.store.save(run)
    monkeypatch.setattr(
        "relief_story_agent.orchestrator.upload_grid_image",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("accepted upload must not be repeated")
        ),
    )

    orchestrator._run_four_grid_asset(run)

    assert run.grid_image_asset.comfyui_filename == "accepted.png"


def test_invalid_manual_image_prevents_comfyui_submission(tmp_path, monkeypatch):
    invalid = tmp_path / "invalid.png"
    Image.new("RGB", (1024, 1024), "white").save(invalid)
    request = _grid_request(tmp_path)
    request.comfyui.grid_image = GridImageConfig(
        mode="manual_override",
        manual_image_path=str(invalid),
    )
    monkeypatch.setattr(
        "relief_story_agent.orchestrator.submit_storyboard",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("invalid image must stop before /prompt")
        ),
    )
    orchestrator = StoryRunOrchestrator(
        provider=FakeModelProvider.minimal_success(),
        store=InMemoryRunStore(),
        grid_image_provider=ProviderMustNotRun(),
    )

    run = orchestrator.create_run(request)

    assert run.status == "failed"
    assert run.failed_stage == "four_grid_asset"


def test_failed_run_records_structured_failure_for_unknown_error():
    provider = FakeModelProvider.minimal_success()
    provider.responses.pop("deepseek_polish")
    store = InMemoryRunStore()
    orchestrator = StoryRunOrchestrator(provider=provider, store=store)

    run = orchestrator.create_run(RunRequest(idea="unknown failure", approval_mode="auto"))
    saved = store.get(run.run_id)

    assert saved.status == "failed"
    assert saved.failed_stage == "deepseek_polish"
    assert saved.last_failure is not None
    assert saved.last_failure.stage == "deepseek_polish"
    assert saved.last_failure.category == "unknown"
    assert saved.last_failure.retryable is False
    assert saved.failure_records[-1] == saved.last_failure


def test_orchestrator_runs_multimodel_pipeline_without_comfyui(tmp_path):
    provider = FakeModelProvider(
        {
            "chief_screenwriter": {
                "core_candidates": [
                    {
                        "title": "未完成也能睡",
                        "core_type": "自我和解内核",
                        "core_sentence": "没做完的事不等于失败。",
                        "pressure_point": "深夜文件没做完",
                        "style": "Q版",
                        "series": "未完成事务所",
                        "logline": "文件夹小人给任务盖被子。",
                        "scores": {
                            "core_clarity": 9,
                            "low_stimulation": 9,
                            "empathy": 9,
                            "aftertaste": 8,
                            "visual_feasibility": 9,
                            "series_potential": 9,
                            "completion_hook": 8,
                        },
                    }
                ],
                "selected_core_index": 0,
                "draft_script": {
                    "title": "未完成也能睡",
                    "story_type": "Q版幻想",
                    "duration_seconds": 80,
                    "core_sentence": "没做完的事不等于失败。",
                    "characters": ["阿北", "文件夹小人"],
                    "setting": "深夜房间",
                    "beats": [
                        {"name": "压力入口", "time_range": "0-10s", "content": "阿北看着一堆未完成文件。"},
                        {"name": "轻微冲突", "time_range": "10-25s", "content": "他担心明天仍做不完。"},
                        {"name": "温柔异动", "time_range": "25-50s", "content": "文件夹小人给任务盖被子。"},
                        {"name": "情绪释放", "time_range": "50-70s", "content": "阿北合上电脑。"},
                        {"name": "余味结尾", "time_range": "70-80s", "content": "屏幕显示明天慢慢来。"},
                    ],
                    "closing_caption": "没完成，不代表你不够好。",
                },
            },
            "deepseek_polish": {
                "polished_script": {
                    "title": "未完成也能睡",
                    "story_type": "Q版幻想",
                    "duration_seconds": 80,
                    "core_sentence": "没做完的事不等于失败。",
                    "characters": ["阿北", "文件夹小人"],
                    "setting": "深夜房间",
                    "beats": [
                        {"name": "压力入口", "time_range": "0-10s", "content": "桌面文件排成小山。"},
                        {"name": "轻微冲突", "time_range": "10-25s", "content": "阿北小声说今天真的做不动。"},
                        {"name": "温柔异动", "time_range": "25-50s", "content": "文件夹小人把任务排队盖好被子。"},
                        {"name": "情绪释放", "time_range": "50-70s", "content": "他第一次没有责怪自己。"},
                        {"name": "余味结尾", "time_range": "70-80s", "content": "电脑自动整理成明天慢慢来。"},
                    ],
                    "closing_caption": "没完成，不代表你不够好。",
                }
            },
            "gpt_prompt_writer": {
                "shots": [
                    {
                        "shot_id": 1,
                        "time_range": "0-10s",
                        "description": "深夜电脑桌，文件图标堆满屏幕。",
                        "image_prompt": "Q版幻想，深夜电脑桌，柔和台灯",
                        "negative_prompt": "争吵，恐怖，压迫",
                        "scores": {
                            "core_clarity": 8,
                            "low_stimulation": 9,
                            "empathy": 8,
                            "aftertaste": 8,
                            "visual_feasibility": 9,
                            "series_potential": 9,
                            "completion_hook": 8,
                        },
                        "comfyui_inputs": {"positive": "Q版幻想，深夜电脑桌", "seed": 101},
                    }
                ]
            },
            "gpt_prompt_audit": {"passed": True, "issues": [], "revision_instructions": [], "scores": {}},
        }
    )
    store = InMemoryRunStore()
    orchestrator = StoryRunOrchestrator(provider=provider, store=store)

    run = orchestrator.create_run(
        RunRequest(
            idea="未完成文件夹",
            audience_pressure="上班族深夜内耗",
            preferred_style="Q版",
            duration_seconds=80,
            output_root=str(tmp_path),
            auto_select_core=True,
            approval_mode="auto",
        )
    )

    final = store.get(run.run_id)
    assert final.status == "completed"
    assert final.current_stage == "completed"
    assert final.selected_core["core_type"] == "自我和解内核"
    assert final.script["core_sentence"] == "没做完的事不等于失败。"
    assert final.storyboard[0]["time_range"] == "0-10s"
    assert final.final_storyboard == final.storyboard
    assert final.comfyui_prompt_ids == []
    assert any(event.event_type == "stage_started" for event in final.events)
    assert any(event.event_type == "stage_completed" for event in final.events)
    timeline_path = Path(final.artifact_dir) / "08_timeline.json"
    timeline = json.loads(timeline_path.read_text(encoding="utf-8"))
    assert timeline["summary"]["stage_event_counts"]["chief_screenwriter"] == 2
    assert timeline["summary"]["stage_event_counts"]["artifacts"] == 2
    assert provider.calls == ["chief_screenwriter", "deepseek_polish", "gpt_prompt_writer", "gpt_prompt_audit"]


def test_comfyui_workflow_replaces_only_declared_fields():
    from relief_story_agent.comfyui import apply_placeholder_map

    workflow = {
        "1": {"inputs": {"text": "old positive", "keep": "unchanged"}},
        "2": {"inputs": {"seed": 1}},
        "3": {"inputs": {"filename_prefix": "old"}},
    }
    shot = {
        "image_prompt": "新的画面提示词",
        "comfyui_inputs": {"seed": 42, "filename_prefix": "relief_001"},
    }
    placeholder_map = {
        "positive": {"node": "1", "input": "text", "source": "image_prompt"},
        "seed": {"node": "2", "input": "seed", "source": "comfyui_inputs.seed"},
        "filename_prefix": {
            "node": "3",
            "input": "filename_prefix",
            "source": "comfyui_inputs.filename_prefix",
        },
    }

    patched = apply_placeholder_map(workflow, shot, placeholder_map)

    assert patched["1"]["inputs"]["text"] == "新的画面提示词"
    assert patched["1"]["inputs"]["keep"] == "unchanged"
    assert patched["2"]["inputs"]["seed"] == 42
    assert patched["3"]["inputs"]["filename_prefix"] == "relief_001"
    assert workflow["1"]["inputs"]["text"] == "old positive"


def test_manual_run_records_model_failure_in_run_state():
    provider = FakeModelProvider({})
    store = InMemoryRunStore()
    orchestrator = StoryRunOrchestrator(provider=provider, store=store)

    run = orchestrator.create_run(
        RunRequest(
            idea="没有配置模型",
            audience_pressure="疲惫上班族",
            approval_mode="manual",
        )
    )

    saved = store.get(run.run_id)
    assert saved.status == "failed"
    assert saved.current_stage == "failed"
    assert "chief_screenwriter" in saved.error


def test_chief_screenwriter_output_contract_fails_at_chief_stage():
    provider = FakeModelProvider(
        {
            "chief_screenwriter": {
                "selected_core_index": 0,
                "draft_script": {"title": "missing core candidates"},
            },
            "deepseek_polish": {
                "polished_script": {
                    "title": "should not run",
                    "duration_seconds": 90,
                    "core_sentence": "x",
                    "beats": [],
                }
            },
        }
    )
    store = InMemoryRunStore()
    orchestrator = StoryRunOrchestrator(provider=provider, store=store)

    run = orchestrator.create_run(RunRequest(idea="bad chief", approval_mode="auto"))
    saved = store.get(run.run_id)

    assert saved.status == "failed"
    assert saved.failed_stage == "chief_screenwriter"
    assert "chief_screenwriter missing required field: core_candidates" in saved.error
    assert provider.calls == ["chief_screenwriter"]


def test_deepseek_output_contract_fails_at_deepseek_stage():
    provider = FakeModelProvider.minimal_success()
    provider.responses["deepseek_polish"] = {"notes": "missing polished script"}
    store = InMemoryRunStore()
    orchestrator = StoryRunOrchestrator(provider=provider, store=store)

    run = orchestrator.create_run(RunRequest(idea="bad deepseek", approval_mode="auto"))
    saved = store.get(run.run_id)

    assert saved.status == "failed"
    assert saved.failed_stage == "deepseek_polish"
    assert "deepseek_polish missing required field: polished_script" in saved.error
    assert provider.calls == ["chief_screenwriter", "deepseek_polish"]


def test_prompt_audit_output_contract_fails_at_audit_stage():
    provider = FakeModelProvider.minimal_success()
    provider.responses["gpt_prompt_audit"] = {"issues": []}
    store = InMemoryRunStore()
    orchestrator = StoryRunOrchestrator(provider=provider, store=store)

    run = orchestrator.create_run(RunRequest(idea="bad audit", approval_mode="auto"))
    saved = store.get(run.run_id)

    assert saved.status == "failed"
    assert saved.failed_stage == "gpt_prompt_audit"
    assert "gpt_prompt_audit missing required field: passed" in saved.error
    assert provider.calls == [
        "chief_screenwriter",
        "deepseek_polish",
        "gpt_prompt_writer",
        "gpt_prompt_audit",
    ]


def test_prompt_writer_output_contract_rejects_non_list_shots():
    provider = FakeModelProvider.minimal_success()
    provider.responses["gpt_prompt_writer"] = {"shots": {"shot_id": 1}}
    store = InMemoryRunStore()
    orchestrator = StoryRunOrchestrator(provider=provider, store=store)

    run = orchestrator.create_run(RunRequest(idea="bad writer", approval_mode="auto"))
    saved = store.get(run.run_id)

    assert saved.status == "failed"
    assert saved.failed_stage == "gpt_prompt_writer"
    assert "gpt_prompt_writer field shots must be a list" in saved.error
