from __future__ import annotations

import json
from typing import Any

from relief_story_agent.models import ComfyUIRunConfig, RunRequest, StageModelConfig, TemplatePaths
from relief_story_agent.orchestrator import InMemoryRunStore, StoryRunOrchestrator


class CapturingProvider:
    def __init__(self, responses: dict[str, dict[str, Any]]):
        self.responses = responses
        self.calls: list[str] = []
        self.prompts: dict[str, str] = {}

    def generate_json(self, stage: str, prompt: str, config: StageModelConfig | None = None) -> dict[str, Any]:
        self.calls.append(stage)
        self.prompts[stage] = prompt
        return self.responses[stage]


def _chief_response(duration: int = 30) -> dict[str, Any]:
    return {
        "core_candidates": [
            {
                "title": "draft",
                "core_type": "自我和解内核",
                "core_sentence": "没做完的事不等于失败。",
                "pressure_point": "late work",
                "style": "Q版",
                "series": "未完成事务所",
                "logline": "folder helper",
                "scores": {
                    "core_clarity": 8,
                    "low_stimulation": 8,
                    "empathy": 8,
                    "aftertaste": 8,
                    "visual_feasibility": 8,
                    "series_potential": 8,
                    "completion_hook": 8,
                },
            }
        ],
        "selected_core_index": 0,
        "draft_script": {
            "title": "draft can be rough",
            "duration_seconds": duration,
            "core_sentence": "",
            "beats": [],
        },
    }


def _polished_script() -> dict[str, Any]:
    return {
        "title": "未完成也能睡",
        "story_type": "Q版幻想",
        "duration_seconds": 80,
        "core_sentence": "没做完的事不等于失败。",
        "characters": ["阿北", "文件夹小人"],
        "setting": "深夜房间",
        "beats": [
            {"name": "压力入口", "time_range": "0-10s", "content": "文件堆满屏幕。"},
            {"name": "轻微冲突", "time_range": "10-25s", "content": "阿北担心明天仍做不完。"},
            {"name": "温柔异动", "time_range": "25-50s", "content": "文件夹小人给任务盖被子。"},
            {"name": "情绪释放", "time_range": "50-70s", "content": "阿北合上电脑。"},
            {"name": "余味结尾", "time_range": "70-80s", "content": "屏幕显示明天慢慢来。"},
        ],
        "closing_caption": "没完成，不代表你不够好。",
    }


def _shot(prompt: str = "Q版深夜电脑桌，文件夹小人给任务盖被子，柔和台灯，四宫格关键帧") -> dict[str, Any]:
    return {
        "shot_id": 1,
        "time_range": "0-10s",
        "description": "深夜电脑桌，文件夹小人出现。",
        "image_prompt": prompt,
        "negative_prompt": "争吵，恐怖，字幕，水印",
        "scores": {
            "core_clarity": 8,
            "low_stimulation": 9,
            "empathy": 8,
            "aftertaste": 8,
            "visual_feasibility": 9,
            "series_potential": 8,
            "completion_hook": 8,
        },
        "comfyui_inputs": {"positive": prompt, "seed": 101, "strength": 0.72},
    }


def _ltx_workflow_file(tmp_path):
    path = tmp_path / "ltx_litegraph.json"
    path.write_text(
        json.dumps(
            {
                "version": 0.4,
                "nodes": [
                    {
                        "id": 202,
                        "type": "JWString",
                        "inputs": [{"name": "text", "type": "STRING", "widget": {"name": "text"}}],
                        "widgets_values": [
                            json.dumps(
                                {
                                    "prompt": "old prompt",
                                    "negative_prompt": "old negative",
                                    "frame_indices": "0,24,48,72",
                                    "strengths": "0.7,0.7,0.8,0.8",
                                    "duration_seconds": 4,
                                }
                            )
                        ],
                    },
                    {
                        "id": 37,
                        "type": "RandomNoise",
                        "inputs": [{"name": "noise_seed", "type": "INT", "widget": {"name": "noise_seed"}}],
                        "widgets_values": [123],
                    },
                    {
                        "id": 79,
                        "type": "VHS_VideoCombine",
                        "inputs": [
                            {"name": "filename_prefix", "type": "STRING", "widget": {"name": "filename_prefix"}}
                        ],
                        "widgets_values": {"filename_prefix": "old_prefix"},
                    },
                ],
                "links": [],
            }
        ),
        encoding="utf-8",
    )
    return path


def test_quality_gate_runs_after_deepseek_not_on_rough_chief_draft():
    provider = CapturingProvider(
        {
            "chief_screenwriter": _chief_response(duration=30),
            "deepseek_polish": {"polished_script": _polished_script()},
            "gpt_prompt_writer": {"shots": [_shot()]},
            "gpt_prompt_audit": {"passed": True, "issues": [], "revision_instructions": [], "scores": {}},
        }
    )
    orchestrator = StoryRunOrchestrator(provider=provider, store=InMemoryRunStore())

    run = orchestrator.create_run(RunRequest(idea="unfinished folder", approval_mode="auto"))

    assert run.status == "completed"
    assert provider.calls == ["chief_screenwriter", "deepseek_polish", "gpt_prompt_writer", "gpt_prompt_audit"]
    assert run.final_storyboard == run.storyboard
    assert run.prompt_revision_count == 0


def test_prompt_writer_blocked_by_quality_gate():
    import pytest
    from relief_story_agent.quality import QualityGate
    from relief_story_agent.models import RunState
    
    provider = CapturingProvider(
        {"gpt_prompt_writer": {"shots": [{"id": 1, "time_range": "0-5", "description": "foo", "negative_prompt": "bar", "image_prompt": "This contains blood and gore", "comfyui_inputs": {}}]}}
    )
    orchestrator = StoryRunOrchestrator(provider=provider, store=InMemoryRunStore())
    
    run = orchestrator.create_run(RunRequest(idea="test", comfyui=None))
    run.script = {"duration_seconds": 90, "core_sentence": "test", "beats": [{"name": b} for b in QualityGate.required_beats]}


    with pytest.raises(ValueError, match="gpt_prompt_writer quality gate failed"):
        orchestrator._run_prompt_writer(run)
def test_custom_writer_template_is_used_by_prompt_writer_stage(tmp_path):
    writer_template = tmp_path / "writer.md"
    writer_template.write_text("CUSTOM TEMPLATE {{script_json}} {{workflow_context}}", encoding="utf-8")
    provider = CapturingProvider(
        {
            "chief_screenwriter": _chief_response(),
            "deepseek_polish": {"polished_script": _polished_script()},
            "gpt_prompt_writer": {"shots": [_shot()]},
            "gpt_prompt_audit": {"passed": True, "issues": [], "revision_instructions": [], "scores": {}},
        }
    )
    orchestrator = StoryRunOrchestrator(provider=provider, store=InMemoryRunStore())

    run = orchestrator.create_run(
        RunRequest(
            idea="template",
            approval_mode="auto",
            template_paths=TemplatePaths(prompt_writer_template_path=str(writer_template)),
        )
    )

    assert run.status == "completed"
    assert provider.prompts["gpt_prompt_writer"].startswith("CUSTOM TEMPLATE")
    assert '"title": "未完成也能睡"' in provider.prompts["gpt_prompt_writer"]


def test_prompt_writer_workflow_context_includes_ltx_analysis(tmp_path):
    writer_template = tmp_path / "writer.md"
    writer_template.write_text("WORKFLOW {{workflow_context}}\nSCRIPT {{script_json}}", encoding="utf-8")
    provider = CapturingProvider(
        {
            "chief_screenwriter": _chief_response(),
            "deepseek_polish": {"polished_script": _polished_script()},
            "gpt_prompt_writer": {"shots": [_shot()]},
            "gpt_prompt_audit": {"passed": True, "issues": [], "revision_instructions": [], "scores": {}},
        }
    )
    orchestrator = StoryRunOrchestrator(provider=provider, store=InMemoryRunStore())

    run = orchestrator.create_run(
        RunRequest(
            idea="ltx context",
            approval_mode="auto",
            comfyui=ComfyUIRunConfig(
                enabled=False,
                workflow_api_path=str(_ltx_workflow_file(tmp_path)),
            ),
            template_paths=TemplatePaths(prompt_writer_template_path=str(writer_template)),
        )
    )

    context_prompt = provider.prompts["gpt_prompt_writer"]
    assert run.status == "completed"
    assert "adapter_mode=litegraph_ltx_auto_injection" in context_prompt
    assert "workflow_format=litegraph" in context_prompt
    assert "ltx_json_node=202" in context_prompt
    assert "seed_node=37" in context_prompt
    assert "filename_prefix_node=79" in context_prompt
    assert "placeholder_map_required=false" in context_prompt


def test_prompt_audit_and_reviser_receive_ltx_workflow_context(tmp_path):
    revised = _shot("Q版深夜电脑桌，阿北在左侧，文件夹小人在右侧，柔和台灯，低刺激四宫格关键帧")
    provider = CapturingProvider(
        {
            "chief_screenwriter": _chief_response(),
            "deepseek_polish": {"polished_script": _polished_script()},
            "gpt_prompt_writer": {"shots": [_shot("角色位置混乱的提示词")]},
            "gpt_prompt_audit": {
                "passed": False,
                "issues": [{"code": "axis_confusion", "message": "角色左右关系不稳定"}],
                "revision_instructions": ["固定阿北在画面左侧，文件夹小人在右侧"],
                "scores": {"spatial_logic": 4},
            },
            "gpt_prompt_reviser": {"shots": [revised]},
        }
    )
    orchestrator = StoryRunOrchestrator(provider=provider, store=InMemoryRunStore())

    run = orchestrator.create_run(
        RunRequest(
            idea="audit context",
            approval_mode="auto",
            comfyui=ComfyUIRunConfig(
                enabled=False,
                workflow_api_path=str(_ltx_workflow_file(tmp_path)),
            ),
        )
    )

    assert run.status == "completed"
    assert "adapter_mode=litegraph_ltx_auto_injection" in provider.prompts["gpt_prompt_audit"]
    assert "ltx_json_node=202" in provider.prompts["gpt_prompt_audit"]
    assert "adapter_mode=litegraph_ltx_auto_injection" in provider.prompts["gpt_prompt_reviser"]
    assert "filename_prefix_node=79" in provider.prompts["gpt_prompt_reviser"]


def test_failed_prompt_audit_triggers_exactly_one_revision_and_uses_revised_prompts():
    revised = _shot("Q版深夜电脑桌，阿北左侧坐着，文件夹小人右侧盖被子，镜头不过轴，柔和台灯")
    provider = CapturingProvider(
        {
            "chief_screenwriter": _chief_response(),
            "deepseek_polish": {"polished_script": _polished_script()},
            "gpt_prompt_writer": {"shots": [_shot("角色位置混乱的长提示词")]},
            "gpt_prompt_audit": {
                "passed": False,
                "issues": [{"code": "axis_confusion", "message": "角色左右关系不稳定"}],
                "revision_instructions": ["固定阿北在画面左侧，文件夹小人在右侧；不要越轴。"],
                "scores": {"spatial_logic": 4},
            },
            "gpt_prompt_reviser": {"shots": [revised]},
        }
    )
    orchestrator = StoryRunOrchestrator(provider=provider, store=InMemoryRunStore())

    run = orchestrator.create_run(RunRequest(idea="revise once", approval_mode="auto"))

    assert run.status == "completed"
    assert provider.calls == [
        "chief_screenwriter",
        "deepseek_polish",
        "gpt_prompt_writer",
        "gpt_prompt_audit",
        "gpt_prompt_reviser",
    ]
    assert run.prompt_revision_count == 1
    assert run.final_storyboard == [revised]
    assert run.storyboard[0]["image_prompt"] == "角色位置混乱的长提示词"


def test_prompt_writer_outputs_are_compacted_for_gpt_image2_four_grid():
    long_prompt = "柔和台灯下的深夜电脑桌，文件夹小人给任务盖被子，保持低刺激，" * 20
    provider = CapturingProvider(
        {
            "chief_screenwriter": _chief_response(),
            "deepseek_polish": {"polished_script": _polished_script()},
            "gpt_prompt_writer": {"shots": [_shot(long_prompt)]},
            "gpt_prompt_audit": {"passed": True, "issues": [], "revision_instructions": [], "scores": {}},
        }
    )
    orchestrator = StoryRunOrchestrator(provider=provider, store=InMemoryRunStore())

    run = orchestrator.create_run(RunRequest(idea="compact prompt", approval_mode="auto"))

    assert run.status == "completed"
    assert len(run.final_storyboard[0]["image_prompt"]) <= 220


def test_prompt_writer_shot_contract_rejects_missing_image_prompt():
    bad_shot = _shot()
    bad_shot.pop("image_prompt")
    provider = CapturingProvider(
        {
            "chief_screenwriter": _chief_response(),
            "deepseek_polish": {"polished_script": _polished_script()},
            "gpt_prompt_writer": {"shots": [bad_shot]},
            "gpt_prompt_audit": {"passed": True, "issues": [], "revision_instructions": [], "scores": {}},
        }
    )
    store = InMemoryRunStore()
    orchestrator = StoryRunOrchestrator(provider=provider, store=store)

    run = orchestrator.create_run(RunRequest(idea="missing prompt", approval_mode="auto"))
    saved = store.get(run.run_id)

    assert saved.status == "failed"
    assert saved.failed_stage == "gpt_prompt_writer"
    assert "gpt_prompt_writer shots[0] missing required field: image_prompt" in saved.error
    assert provider.calls == ["chief_screenwriter", "deepseek_polish", "gpt_prompt_writer"]


def test_prompt_reviser_shot_contract_rejects_missing_comfyui_inputs():
    bad_revised_shot = _shot("revised prompt")
    bad_revised_shot.pop("comfyui_inputs")
    provider = CapturingProvider(
        {
            "chief_screenwriter": _chief_response(),
            "deepseek_polish": {"polished_script": _polished_script()},
            "gpt_prompt_writer": {"shots": [_shot()]},
            "gpt_prompt_audit": {
                "passed": False,
                "issues": [{"code": "spatial_logic", "message": "missing stable positions"}],
                "revision_instructions": ["Keep left/right positions stable."],
                "scores": {"spatial_logic": 4},
            },
            "gpt_prompt_reviser": {"shots": [bad_revised_shot]},
        }
    )
    store = InMemoryRunStore()
    orchestrator = StoryRunOrchestrator(provider=provider, store=store)

    run = orchestrator.create_run(RunRequest(idea="bad revised shot", approval_mode="auto"))
    saved = store.get(run.run_id)

    assert saved.status == "failed"
    assert saved.failed_stage == "gpt_prompt_reviser"
    assert "gpt_prompt_reviser shots[0] missing required field: comfyui_inputs" in saved.error
    assert provider.calls == [
        "chief_screenwriter",
        "deepseek_polish",
        "gpt_prompt_writer",
        "gpt_prompt_audit",
        "gpt_prompt_reviser",
    ]
