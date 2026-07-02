from __future__ import annotations

import json
import uuid

import httpx
import pytest

from relief_story_agent.comfyui import (
    ComfyUISubmissionUnknown,
    enqueue_workflow,
    submit_storyboard,
)
from relief_story_agent.models import (
    ComfyUIRunConfig,
    ComfyUISubmission,
    RunRequest,
    RunState,
)
from relief_story_agent.orchestrator import StoryRunOrchestrator
from relief_story_agent.providers import FakeModelProvider
from relief_story_agent.storage import JsonFileRunStore


HTTPX_CLIENT = httpx.Client


def test_enqueue_workflow_includes_public_provenance_and_source_workflow():
    posted = {}

    def handler(request: httpx.Request):
        posted.update(json.loads(request.content))
        return httpx.Response(200, json={"prompt_id": "prompt-1"})

    client = HTTPX_CLIENT(transport=httpx.MockTransport(handler))
    result = enqueue_workflow(
        "http://comfy.local",
        {"1": {"class_type": "PromptNode", "inputs": {"text": "patched"}}},
        prompt_id="prompt-1",
        client_id="client-1",
        extra_data={
            "relief_story_agent": {"run_id": "run-1", "segment_id": "segment-1"},
            "extra_pnginfo": {"workflow": {"nodes": [], "links": []}},
        },
        client=client,
    )

    assert result == "prompt-1"
    assert posted["extra_data"]["client_id"] == "client-1"
    assert posted["extra_data"]["relief_story_agent"]["segment_id"] == "segment-1"
    assert posted["extra_data"]["extra_pnginfo"]["workflow"] == {
        "nodes": [],
        "links": [],
    }


def _workflow_file(tmp_path):
    path = tmp_path / "workflow_api.json"
    path.write_text(
        json.dumps(
            {
                "1": {
                    "class_type": "PromptNode",
                    "inputs": {"text": "old prompt"},
                }
            }
        ),
        encoding="utf-8",
    )
    return path


def _config(workflow_path):
    return ComfyUIRunConfig(
        enabled=True,
        endpoint="http://comfy.local",
        workflow_api_path=str(workflow_path),
        placeholder_map={
            "positive": {
                "node": "1",
                "input": "text",
                "source": "image_prompt",
            }
        },
    )


def _storyboard(prompt="雨后便利店，疲惫上班族推门进入"):
    return [
        {
            "shot_id": 1,
            "image_prompt": prompt,
            "comfyui_inputs": {"seed": 101},
        }
    ]


def test_submit_storyboard_uses_deterministic_prompt_id_and_skips_accepted_submission(tmp_path):
    posted_payloads = []

    def handler(request: httpx.Request):
        assert request.url.path == "/prompt"
        payload = json.loads(request.content)
        posted_payloads.append(payload)
        return httpx.Response(200, json={"prompt_id": payload["prompt_id"], "number": 1})

    client = HTTPX_CLIENT(transport=httpx.MockTransport(handler))
    config = _config(_workflow_file(tmp_path))

    first = submit_storyboard(config, _storyboard(), "run_stable", client=client)
    second = submit_storyboard(
        config,
        _storyboard(),
        "run_stable",
        existing_submissions=first,
        client=client,
    )

    assert len(posted_payloads) == 1
    assert uuid.UUID(posted_payloads[0]["prompt_id"]).version == 5
    assert first[0].status == "accepted"
    assert second[0].prompt_id == first[0].prompt_id


def test_submit_storyboard_records_unknown_timeout_then_reconciles_without_duplicate_post(tmp_path):
    updates: list[list[ComfyUISubmission]] = []
    expected_prompt_id = ""

    def timeout_handler(request: httpx.Request):
        nonlocal expected_prompt_id
        payload = json.loads(request.content)
        expected_prompt_id = payload["prompt_id"]
        raise httpx.ReadTimeout("response was lost", request=request)

    config = _config(_workflow_file(tmp_path))
    timeout_client = HTTPX_CLIENT(transport=httpx.MockTransport(timeout_handler))

    with pytest.raises(ComfyUISubmissionUnknown):
        submit_storyboard(
            config,
            _storyboard(),
            "run_timeout",
            client=timeout_client,
            on_update=lambda current: updates.append(
                [item.model_copy(deep=True) for item in current]
            ),
        )

    unknown = updates[-1]
    assert unknown[0].status == "unknown"
    assert unknown[0].prompt_id == expected_prompt_id

    requests = []

    def reconcile_handler(request: httpx.Request):
        requests.append((request.method, request.url.path))
        return httpx.Response(
            200,
            json={"id": expected_prompt_id, "status": "pending"},
        )

    reconcile_client = HTTPX_CLIENT(transport=httpx.MockTransport(reconcile_handler))
    recovered = submit_storyboard(
        config,
        _storyboard(),
        "run_timeout",
        existing_submissions=unknown,
        client=reconcile_client,
    )

    assert requests == [("GET", f"/api/jobs/{expected_prompt_id}")]
    assert recovered[0].status == "accepted"
    assert recovered[0].prompt_id == expected_prompt_id


def test_unknown_submission_is_reposted_with_same_id_only_after_not_found_checks(tmp_path):
    requests = []
    posted_prompt_id = ""
    existing = [
        ComfyUISubmission(
            submission_key="shot:1",
            content_fingerprint="placeholder",
            prompt_id=str(uuid.uuid4()),
            client_id="run_missing:shot:1",
            status="unknown",
        )
    ]
    config = _config(_workflow_file(tmp_path))

    # Use a real planned fingerprint from an interrupted first attempt.
    interrupted_updates = []

    def timeout_handler(request: httpx.Request):
        raise httpx.ReadTimeout("lost", request=request)

    with pytest.raises(ComfyUISubmissionUnknown):
        submit_storyboard(
            config,
            _storyboard(),
            "run_missing",
            client=HTTPX_CLIENT(transport=httpx.MockTransport(timeout_handler)),
            on_update=lambda current: interrupted_updates.append(
                [item.model_copy(deep=True) for item in current]
            ),
        )
    existing = interrupted_updates[-1]

    def handler(request: httpx.Request):
        nonlocal posted_prompt_id
        requests.append((request.method, request.url.path))
        if request.url.path.startswith("/api/jobs/"):
            return httpx.Response(404, json={"error": "Job not found"})
        if request.url.path == "/queue":
            return httpx.Response(200, json={"queue_running": [], "queue_pending": []})
        if request.url.path == "/history":
            return httpx.Response(200, json={})
        payload = json.loads(request.content)
        posted_prompt_id = payload["prompt_id"]
        return httpx.Response(200, json={"prompt_id": posted_prompt_id})

    recovered = submit_storyboard(
        config,
        _storyboard(),
        "run_missing",
        existing_submissions=existing,
        client=HTTPX_CLIENT(transport=httpx.MockTransport(handler)),
    )

    assert requests == [
        ("GET", f"/api/jobs/{existing[0].prompt_id}"),
        ("GET", "/queue"),
        ("GET", "/history"),
        ("POST", "/prompt"),
    ]
    assert posted_prompt_id == existing[0].prompt_id
    assert recovered[0].status == "accepted"


def test_changed_prompt_gets_new_submission_id_instead_of_reusing_old_result(tmp_path):
    posted_ids = []

    def handler(request: httpx.Request):
        payload = json.loads(request.content)
        posted_ids.append(payload["prompt_id"])
        return httpx.Response(200, json={"prompt_id": payload["prompt_id"]})

    client = HTTPX_CLIENT(transport=httpx.MockTransport(handler))
    config = _config(_workflow_file(tmp_path))
    first = submit_storyboard(config, _storyboard("旧提示词"), "run_changed", client=client)
    second = submit_storyboard(
        config,
        _storyboard("修正后的新提示词"),
        "run_changed",
        existing_submissions=first,
        client=client,
    )

    assert len(posted_ids) == 2
    assert posted_ids[0] != posted_ids[1]
    assert first[0].content_fingerprint != second[0].content_fingerprint


def test_orchestrator_persists_unknown_submission_and_recovers_it_after_restart(
    tmp_path,
    monkeypatch,
):
    config = _config(_workflow_file(tmp_path))
    state_dir = tmp_path / "state"
    store = JsonFileRunStore(state_dir)
    run = RunState(
        run_id="run_restart",
        request=RunRequest(
            idea="重启恢复",
            approval_mode="auto",
            comfyui=config,
        ),
        final_storyboard=_storyboard(),
    )
    store.save(run)

    def timeout_handler(request: httpx.Request):
        raise httpx.ReadTimeout("response lost", request=request)

    timeout_client = HTTPX_CLIENT(transport=httpx.MockTransport(timeout_handler))
    monkeypatch.setattr(
        "relief_story_agent.comfyui.httpx.Client",
        lambda **kwargs: timeout_client,
    )
    first_orchestrator = StoryRunOrchestrator(
        provider=FakeModelProvider.minimal_success(),
        store=store,
    )

    first_orchestrator._execute(run, start_stage="comfyui")

    interrupted = JsonFileRunStore(state_dir).get(run.run_id)
    assert interrupted.status == "failed"
    assert interrupted.failed_stage == "comfyui"
    assert interrupted.comfyui_submissions[0].status == "unknown"
    prompt_id = interrupted.comfyui_submissions[0].prompt_id

    requests = []

    def reconcile_handler(request: httpx.Request):
        requests.append((request.method, request.url.path))
        return httpx.Response(200, json={"id": prompt_id, "status": "pending"})

    reconcile_client = HTTPX_CLIENT(transport=httpx.MockTransport(reconcile_handler))
    monkeypatch.setattr(
        "relief_story_agent.comfyui.httpx.Client",
        lambda **kwargs: reconcile_client,
    )
    restarted_orchestrator = StoryRunOrchestrator(
        provider=FakeModelProvider.minimal_success(),
        store=JsonFileRunStore(state_dir),
    )

    recovered = restarted_orchestrator.retry(run.run_id)

    assert recovered.status == "completed"
    assert recovered.comfyui_prompt_ids == [prompt_id]
    assert recovered.comfyui_submissions[0].status == "accepted"
    assert requests == [("GET", f"/api/jobs/{prompt_id}")]
