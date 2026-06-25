from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .artifacts import read_batch_artifact_index, read_run_artifact_index
from .models import (
    BatchRunRequest,
    ComfyUIRunConfig,
    RunRequest,
    RunRequestDefaults,
)
from .orchestrator import InMemoryRunStore, StoryRunOrchestrator
from .providers import FakeModelProvider


def run_local_demo(output_dir: str | Path, *, batch_size: int = 2) -> dict[str, Any]:
    if batch_size < 1:
        raise ValueError("batch_size must be at least 1")

    target_dir = Path(output_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    runs_root = target_dir / "runs"
    runs_root.mkdir(parents=True, exist_ok=True)

    provider = FakeModelProvider.minimal_success()
    store = InMemoryRunStore()
    orchestrator = StoryRunOrchestrator(provider=provider, store=store)

    single_run = orchestrator.create_run(
        _demo_run_request(
            "local-demo-single",
            "A tired worker finds one small quiet kindness after a long shift.",
            output_root=runs_root,
        )
    )

    batch = orchestrator.create_batch(
        BatchRunRequest(
            idempotency_key=f"local-demo-batch-{batch_size}",
            defaults=RunRequestDefaults(
                approval_mode="auto",
                output_root=str(runs_root),
                comfyui=ComfyUIRunConfig(enabled=False),
            ),
            items=[
                RunRequest(
                    idempotency_key=f"local-demo-batch-item-{index}",
                    idea=_batch_idea(index),
                )
                for index in range(batch_size)
            ],
        )
    )
    batch_runs = [store.get(item.run_id) for item in batch.items]

    result: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "completed" if single_run.status == "completed" and batch.status == "completed" else "failed",
        "mode": "offline_demo",
        "output_dir": str(target_dir),
        "external_calls": {
            "model_provider": "fake",
            "comfyui": False,
            "image_generation": False,
        },
        "single_run": _run_summary(single_run),
        "batch": {
            "batch_id": batch.batch_id,
            "status": batch.status,
            "summary": dict(batch.summary),
            "artifact_index": read_batch_artifact_index(batch, batch_runs),
            "items": [_batch_item_summary(store.get(item.run_id), item.index) for item in batch.items],
        },
        "model_stage_calls": list(provider.calls),
    }
    summary_path = target_dir / "local_demo_summary.json"
    result["summary_path"] = str(summary_path)
    summary_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


def _demo_run_request(idempotency_key: str, idea: str, *, output_root: Path) -> RunRequest:
    return RunRequest(
        idempotency_key=idempotency_key,
        idea=idea,
        audience_pressure="Work fatigue, emotional drain, and wanting to be seen without drama.",
        preferred_series="Quiet convenience store nights",
        preferred_style="warm realistic low-stimulation short video",
        approval_mode="auto",
        output_root=str(output_root),
        comfyui=ComfyUIRunConfig(enabled=False),
    )


def _batch_idea(index: int) -> str:
    ideas = [
        "A convenience-store clerk leaves an extra pair of chopsticks for tomorrow.",
        "An unfinished folder icon gets tucked in for the night by a tiny desk light.",
        "A pressure cloud over someone's shoulder dissolves beside a warm vending machine.",
        "A night bus ride becomes softer when the city lights slow down.",
        "A small bowl of soup waits beside a muted work phone.",
    ]
    return ideas[index % len(ideas)]


def _run_summary(run) -> dict[str, Any]:
    artifact_index = read_run_artifact_index(run)
    return {
        "run_id": run.run_id,
        "status": run.status,
        "current_stage": run.current_stage,
        "artifact_dir": run.artifact_dir,
        "artifact_index": artifact_index,
        "comfyui_prompt_ids": list(run.comfyui_prompt_ids),
        "final_prompt_count": len(run.final_storyboard),
    }


def _batch_item_summary(run, index: int) -> dict[str, Any]:
    summary = _run_summary(run)
    summary["index"] = index
    summary["idea"] = run.request.idea
    return summary
