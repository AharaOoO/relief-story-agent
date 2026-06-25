from __future__ import annotations

from relief_story_agent.models import RunRequest
from relief_story_agent.orchestrator import InMemoryRunStore, StoryRunOrchestrator
from relief_story_agent.providers import FakeModelProvider


def test_stage_registry_declares_fixed_order_and_side_effect_boundaries():
    from relief_story_agent.pipeline import CANONICAL_STAGE_ORDER, get_stage_spec, stage_ids_for_run

    assert CANONICAL_STAGE_ORDER == (
        "chief_screenwriter",
        "deepseek_polish",
        "quality_gate",
        "gpt_prompt_writer",
        "gpt_prompt_audit",
        "gpt_prompt_reviser",
        "final_prompts",
        "four_grid_asset",
        "artifacts",
        "comfyui",
    )
    assert get_stage_spec("chief_screenwriter").side_effects == ("model_call",)
    assert get_stage_spec("four_grid_asset").side_effects == (
        "image_generation",
        "comfyui_upload",
    )
    assert get_stage_spec("comfyui").side_effects == ("comfyui_prompt",)
    assert stage_ids_for_run(
        requires_grid_asset=True,
        writes_artifacts=True,
        comfyui_enabled=True,
    ) == [
        "chief_screenwriter",
        "deepseek_polish",
        "quality_gate",
        "gpt_prompt_writer",
        "gpt_prompt_audit",
        "final_prompts",
        "four_grid_asset",
        "artifacts",
        "comfyui",
    ]


def test_auto_run_records_final_prompts_checkpoint_before_completion():
    provider = FakeModelProvider.minimal_success()
    store = InMemoryRunStore()
    orchestrator = StoryRunOrchestrator(provider=provider, store=store)

    run = orchestrator.create_run(RunRequest(idea="quiet checkpoint", approval_mode="auto"))

    completed = [
        event.stage for event in run.events if event.event_type == "stage_completed"
    ]
    assert "final_prompts" in completed
    assert completed.index("gpt_prompt_audit") < completed.index("final_prompts")
    assert run.last_completed_stage == "final_prompts"
