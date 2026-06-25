from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .comfyui_endpoint import normalize_comfyui_endpoint


PROMPT_WRITER_TEMPLATE = """# gpt_prompt_writer template

You turn the polished script into 5-8 visual shots for GPT image and LTX/ComfyUI.

Requirements:
- Every shot must serve the story core, not decorative filler.
- Keep image_prompt concise and concrete.
- Preserve character positions, spatial relations, motion continuity, lighting, and emotional tone.
- Keep the short low-stimulation: no shouting, horror, violence, panic, or chaotic conflict.
- Each shot must include comfyui_inputs with positive, negative, seed, strength, and filename_prefix.

Script JSON:
{{script_json}}

Target duration seconds:
{{duration_seconds}}

Preferred style:
{{preferred_style}}

Workflow context:
{{workflow_context}}

Return JSON only:
{
  "shots": [
    {
      "shot_id": 1,
      "time_range": "0-10s",
      "description": "clear shot description",
      "image_prompt": "concise keyframe prompt",
      "negative_prompt": "shouting, horror, violence, chaos, text, watermark",
      "scores": {
        "core_clarity": 1,
        "low_stimulation": 1,
        "empathy": 1,
        "aftertaste": 1,
        "visual_feasibility": 1,
        "series_potential": 1,
        "completion_hook": 1
      },
      "comfyui_inputs": {
        "positive": "concise positive prompt",
        "negative": "shouting, horror, violence, chaos, text, watermark",
        "seed": 123,
        "strength": 0.72,
        "filename_prefix": "relief_story"
      }
    }
  ]
}
"""


PROMPT_AUDIT_TEMPLATE = """# gpt_prompt_audit template

Check the storyboard prompts for visual and narrative loopholes before they reach image/video generation.

Audit focus:
- character count, position, and left/right continuity
- spatial relation clarity
- axis continuity and camera direction
- motion logic between adjacent shots
- static frame logic: props, light, emotion, and setting consistency
- story meaning for every shot
- prompt concision for four-grid keyframes

Script JSON:
{{script_json}}

Storyboard JSON:
{{storyboard_json}}

Workflow context:
{{workflow_context}}

Return JSON only:
{
  "passed": true,
  "issues": [
    {"code": "spatial_confusion", "message": "...", "shot_id": 1}
  ],
  "revision_instructions": ["..."],
  "scores": {
    "spatial_logic": 1,
    "axis_continuity": 1,
    "motion_logic": 1,
    "static_logic": 1,
    "story_alignment": 1,
    "prompt_conciseness": 1
  }
}
"""


def write_local_config_bundle(
    output_dir: str | Path,
    *,
    workflow_path: str,
    comfyui_endpoint: str = "http://127.0.0.1:8188",
    output_root: str = "D:/relief_story_runs",
) -> dict[str, str]:
    comfyui_endpoint = normalize_comfyui_endpoint(comfyui_endpoint)
    target_dir = Path(output_dir)
    templates_dir = target_dir / "templates"
    target_dir.mkdir(parents=True, exist_ok=True)
    templates_dir.mkdir(parents=True, exist_ok=True)

    prompt_writer_template = templates_dir / "prompt_writer.default.md"
    prompt_audit_template = templates_dir / "prompt_audit.default.md"
    model_config = target_dir / "model_config.local.json"
    run_request = target_dir / "run_request.full-ltx.json"
    batch_request = target_dir / "batch_request.full-ltx.json"
    comfyui_connect = target_dir / "comfyui_connect.json"

    prompt_writer_template.write_text(PROMPT_WRITER_TEMPLATE, encoding="utf-8")
    prompt_audit_template.write_text(PROMPT_AUDIT_TEMPLATE, encoding="utf-8")
    _write_json(model_config, _model_config_payload())
    _write_json(
        comfyui_connect,
        {
            "endpoint": comfyui_endpoint,
            "workflow_api_path": workflow_path,
            "timeout_seconds": 5,
        },
    )
    _write_json(
        run_request,
        _run_request_payload(
            workflow_path=workflow_path,
            comfyui_endpoint=comfyui_endpoint,
            output_root=output_root,
            prompt_writer_template=prompt_writer_template,
            prompt_audit_template=prompt_audit_template,
        ),
    )
    _write_json(
        batch_request,
        _batch_request_payload(
            workflow_path=workflow_path,
            comfyui_endpoint=comfyui_endpoint,
            output_root=output_root,
            prompt_writer_template=prompt_writer_template,
            prompt_audit_template=prompt_audit_template,
        ),
    )

    paths = {
        "model_config": str(model_config),
        "run_request": str(run_request),
        "batch_request": str(batch_request),
        "comfyui_connect": str(comfyui_connect),
        "prompt_writer_template": str(prompt_writer_template),
        "prompt_audit_template": str(prompt_audit_template),
    }
    return {
        **paths,
        "files": _bundle_file_index(paths),
        "checks": _bundle_checks(
            workflow_path=workflow_path,
            comfyui_endpoint=comfyui_endpoint,
            output_root=output_root,
        ),
        "next_commands": _next_commands(
            target_dir,
            comfyui_endpoint=comfyui_endpoint,
            workflow_path=workflow_path,
        ),
        "next_endpoints": _next_endpoints(),
    }


def _model_config_payload() -> dict[str, Any]:
    return {
        "profiles": {
            "gemini_writer": {
                "base_url": "https://YOUR_GEMINI_OPENAI_COMPATIBLE_ENDPOINT/v1",
                "api_key_env": "GEMINI_API_KEY",
                "model": "YOUR_GEMINI_MODEL",
                "temperature": 0.7,
                "max_attempts": 3,
                "requests_per_minute": 20,
            },
            "deepseek_editor": {
                "base_url": "https://YOUR_DEEPSEEK_OPENAI_COMPATIBLE_ENDPOINT/v1",
                "api_key_env": "DEEPSEEK_API_KEY",
                "model": "YOUR_DEEPSEEK_MODEL",
                "temperature": 0.8,
                "max_attempts": 3,
                "requests_per_minute": 20,
            },
            "gpt_visual": {
                "base_url": "https://api.openai.com/v1",
                "api_key_env": "OPENAI_API_KEY",
                "model": "YOUR_GPT_JSON_MODEL",
                "temperature": 0.4,
                "max_attempts": 3,
                "requests_per_minute": 30,
            },
        },
        "stages": {
            "chief_screenwriter": "gemini_writer",
            "deepseek_polish": "deepseek_editor",
            "gpt_prompt_writer": "gpt_visual",
            "gpt_prompt_audit": "gpt_visual",
            "gpt_prompt_reviser": "gpt_visual",
        },
    }


def _run_request_payload(
    *,
    workflow_path: str,
    comfyui_endpoint: str,
    output_root: str,
    prompt_writer_template: Path,
    prompt_audit_template: Path,
) -> dict[str, Any]:
    return {
        "idempotency_key": "relief-single-demo-001",
        "idea": "A tired office worker receives a small kindness at a convenience store.",
        "audience_pressure": "after-work fatigue and quiet anxiety",
        "preferred_series": "Convenience Store Nights",
        "preferred_style": "realistic, soft urban night, low stimulation",
        "duration_seconds": 90,
        "approval_mode": "auto",
        "output_root": output_root,
        "execution_policy": _execution_policy_payload(),
        "template_paths": {
            "prompt_writer_template_path": str(prompt_writer_template),
            "prompt_audit_template_path": str(prompt_audit_template),
        },
        "comfyui": _comfyui_payload(workflow_path, comfyui_endpoint),
    }


def _batch_request_payload(
    *,
    workflow_path: str,
    comfyui_endpoint: str,
    output_root: str,
    prompt_writer_template: Path,
    prompt_audit_template: Path,
) -> dict[str, Any]:
    return {
        "idempotency_key": "relief-batch-demo-001",
        "failure_policy": {
            "auto_retry_failed_items": 1,
            "pause_on_failure_count": 2,
            "pause_on_failure_rate": 0.5,
        },
        "defaults": {
            "approval_mode": "auto",
            "queue_priority": 0,
            "output_root": output_root,
            "duration_seconds": 90,
            "execution_policy": _execution_policy_payload(),
            "template_paths": {
                "prompt_writer_template_path": str(prompt_writer_template),
                "prompt_audit_template_path": str(prompt_audit_template),
            },
            "comfyui": _comfyui_payload(workflow_path, comfyui_endpoint),
        },
        "items": [
            {
                "idea": "A convenience-store clerk adds one extra pair of chopsticks for tomorrow.",
                "audience_pressure": "late-night work fatigue",
                "preferred_series": "Convenience Store Nights",
                "preferred_style": "realistic urban, soft rain, low stimulation",
                "queue_priority": 5,
            },
            {
                "idea": "A tiny pressure creature grows quiet after warm soup is offered.",
                "audience_pressure": "commute anxiety",
                "preferred_series": "Pressure Little Creature",
                "preferred_style": "soft fantasy, gentle humor, low stimulation",
            },
            {
                "idea": "A folder of unfinished tasks is tucked under a small blanket.",
                "audience_pressure": "unfinished work and self-blame",
                "preferred_series": "Unfinished Things Office",
                "preferred_style": "gentle miniature office, warm light, low stimulation",
            },
        ],
    }


def _comfyui_payload(workflow_path: str, comfyui_endpoint: str) -> dict[str, Any]:
    return {
        "enabled": True,
        "endpoint": comfyui_endpoint,
        "workflow_api_path": workflow_path,
        "wait_for_completion": True,
        "download_outputs": True,
        "output_timeout_seconds": 1800,
        "output_poll_interval_seconds": 5,
        "grid_image": {
            "mode": "auto",
            "provider": "openai_compatible",
            "base_url": "https://api.openai.com/v1",
            "api_key_env": "OPENAI_API_KEY",
            "model": "gpt-image-2",
            "size": "1024x1024",
            "quality": "medium",
            "output_format": "png",
        },
    }


def _execution_policy_payload() -> dict[str, Any]:
    return {
        "max_total_stage_executions": 18,
        "max_stage_executions": {
            "chief_screenwriter": 2,
            "deepseek_polish": 2,
            "gpt_prompt_writer": 2,
            "gpt_prompt_audit": 2,
            "four_grid_asset": 3,
            "comfyui": 3,
        },
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _bundle_file_index(paths: dict[str, str]) -> dict[str, dict[str, Any]]:
    return {name: _file_record(Path(path)) for name, path in paths.items()}


def _file_record(path: Path) -> dict[str, Any]:
    exists = path.exists()
    return {
        "path": str(path),
        "exists": exists,
        "size_bytes": path.stat().st_size if exists else 0,
        "sha256": _sha256_file(path) if exists and path.is_file() else "",
    }


def _bundle_checks(
    *,
    workflow_path: str,
    comfyui_endpoint: str,
    output_root: str,
) -> dict[str, dict[str, Any]]:
    workflow = Path(workflow_path)
    output = Path(output_root)
    workflow_exists = workflow.exists()
    return {
        "workflow_path": {
            "status": "pass" if workflow_exists else "warn",
            "path": workflow_path,
            "exists": workflow_exists,
            "message": (
                "Workflow file exists."
                if workflow_exists
                else "Workflow path was written into config but does not exist on this machine yet."
            ),
        },
        "comfyui_endpoint": {
            "status": "ready",
            "normalized": comfyui_endpoint,
            "message": "Run local-doctor or connect-comfyui to test this endpoint.",
        },
        "output_root": {
            "status": "ready",
            "path": output_root,
            "exists": output.exists(),
            "message": "The run pipeline will create output directories when needed.",
        },
        "secrets": {
            "status": "pending",
            "api_key_env": ["GEMINI_API_KEY", "DEEPSEEK_API_KEY", "OPENAI_API_KEY"],
            "message": "API keys are referenced by environment variable name only.",
        },
    }


def _next_commands(
    target_dir: Path,
    *,
    comfyui_endpoint: str,
    workflow_path: str,
) -> dict[str, str]:
    model_config = target_dir / "model_config.local.json"
    run_request = target_dir / "run_request.full-ltx.json"
    batch_request = target_dir / "batch_request.full-ltx.json"
    return {
        "doctor": (
            "relief-story-agent local-doctor --check-comfyui-connection "
            f'--comfyui-endpoint "{comfyui_endpoint}" '
            f'--comfyui-workflow-path "{workflow_path}" --pretty'
        ),
        "model_check": f'relief-story-agent model-check --model-config "{model_config}" --pretty',
        "run_preflight": (
            f'relief-story-agent diagnose --request "{run_request}" '
            f'--model-config "{model_config}" --pretty'
        ),
        "batch_plan": (
            f'relief-story-agent batch-plan --request "{batch_request}" '
            "--check-comfyui-connection --pretty"
        ),
    }


def _next_endpoints() -> dict[str, str]:
    return {
        "local_bootstrap": "/api/local/bootstrap",
        "local_doctor": "/api/local/doctor",
        "comfyui_connect": "/api/comfyui/connect",
        "model_check": "/api/config/model-check",
        "diagnose_run": "/api/config/diagnose",
        "diagnose_batch": "/api/config/diagnose-batch",
        "batch_plan": "/api/batches/plan",
        "create_run": "/api/runs",
        "create_batch": "/api/batches",
    }


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
