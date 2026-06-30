from __future__ import annotations

import json
import subprocess
import sys

import httpx
from fastapi.testclient import TestClient

from relief_story_agent.api import create_app
from relief_story_agent.orchestrator import StoryRunOrchestrator
from relief_story_agent.providers import FakeModelProvider
from relief_story_agent.runninghub import (
    RunningHubTaskOutputsRequest,
    RunningHubTaskRequest,
    RunningHubWorkflowRequest,
    build_runninghub_create_payload,
    check_runninghub_request,
    fetch_runninghub_outputs,
    fetch_runninghub_status,
    submit_runninghub_task,
)


def test_runninghub_payload_uses_advanced_workflow_contract_without_secret():
    request = RunningHubWorkflowRequest.model_validate(
        {
            "workflow_id": "2038860299301818369",
            "api_key_env": "RUNNINGHUB_API_KEY",
            "node_info_list": [
                {
                    "node_id": "12",
                    "field_name": "prompt",
                    "field_value": "gentle cinematic relief story",
                    "description": "main prompt",
                }
            ],
            "webhook_url": "https://callback.example/runninghub",
            "use_personal_queue": True,
            "instance_type": "plus",
        }
    )

    payload = build_runninghub_create_payload(request, api_key="secret-value")

    assert payload == {
        "apiKey": "secret-value",
        "workflowId": "2038860299301818369",
        "nodeInfoList": [
            {
                "nodeId": "12",
                "fieldName": "prompt",
                "fieldValue": "gentle cinematic relief story",
                "description": "main prompt",
            }
        ],
        "webhookUrl": "https://callback.example/runninghub",
        "usePersonalQueue": True,
        "instanceType": "plus",
    }
    public = request.model_dump()
    assert "api_key" not in public
    assert "secret-value" not in json.dumps(public)


def test_runninghub_check_requires_key_env_and_never_echoes_secret(monkeypatch):
    monkeypatch.delenv("RUNNINGHUB_API_KEY", raising=False)
    request = RunningHubWorkflowRequest(
        workflow_id="2038860299301818369",
        node_info_list=[{"node_id": "1", "field_name": "text", "field_value": "hello"}],
    )

    missing = check_runninghub_request(request)

    assert missing["ready"] is False
    assert missing["checks"][0]["id"] == "runninghub_api_key"
    assert missing["suggested_actions"] == ["set_runninghub_api_key_env"]

    monkeypatch.setenv("RUNNINGHUB_API_KEY", "secret-value")
    ready = check_runninghub_request(request)

    assert ready["ready"] is True
    assert "secret-value" not in json.dumps(ready)


def test_runninghub_dry_submit_returns_redacted_payload(monkeypatch):
    monkeypatch.setenv("RUNNINGHUB_API_KEY", "secret-value")
    request = RunningHubWorkflowRequest(
        workflow_id="2038860299301818369",
        node_info_list=[{"node_id": "1", "field_name": "text", "field_value": "hello"}],
    )

    result = submit_runninghub_task(request, dry_run=True)

    assert result["status"] == "dry_run"
    assert result["ready"] is True
    assert result["method"] == "POST"
    assert result["url"] == "https://www.runninghub.ai/task/openapi/create"
    assert result["payload"]["apiKey"] == "<redacted:RUNNINGHUB_API_KEY>"
    assert "secret-value" not in json.dumps(result)


def test_runninghub_live_create_status_outputs_use_official_endpoints(monkeypatch):
    monkeypatch.setenv("RUNNINGHUB_API_KEY", "secret-value")
    requests: list[tuple[str, dict]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content.decode("utf-8"))
        requests.append((request.url.path, payload))
        assert payload["apiKey"] == "secret-value"
        if request.url.path == "/task/openapi/create":
            return httpx.Response(200, json={"code": 0, "data": {"taskId": "task-cloud-1"}})
        if request.url.path == "/task/openapi/status":
            return httpx.Response(200, json={"code": 0, "data": {"status": "RUNNING"}})
        if request.url.path == "/task/openapi/outputs":
            return httpx.Response(
                200,
                json={
                    "code": 0,
                    "data": [
                        {
                            "fileUrl": "https://cdn.example/video.mp4",
                            "fileType": "video",
                            "taskCostTime": "12",
                        }
                    ],
                },
            )
        return httpx.Response(404)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    workflow_request = RunningHubWorkflowRequest(
        base_url="https://www.runninghub.ai/",
        workflow_id="2038860299301818369",
        node_info_list=[{"node_id": "1", "field_name": "text", "field_value": "hello"}],
    )

    created = submit_runninghub_task(workflow_request, client=client)
    status = fetch_runninghub_status(RunningHubTaskRequest(task_id="task-cloud-1"), client=client)
    outputs = fetch_runninghub_outputs(RunningHubTaskOutputsRequest(task_id="task-cloud-1"), client=client)

    assert created["task_id"] == "task-cloud-1"
    assert status["remote_status"] == "RUNNING"
    assert outputs["outputs"][0]["fileUrl"] == "https://cdn.example/video.mp4"
    assert [path for path, _ in requests] == [
        "/task/openapi/create",
        "/task/openapi/status",
        "/task/openapi/outputs",
    ]


def test_runninghub_api_check_and_dry_submit(monkeypatch):
    monkeypatch.setenv("RUNNINGHUB_API_KEY", "secret-value")
    client = TestClient(create_app(StoryRunOrchestrator(provider=FakeModelProvider.minimal_success())))
    payload = {
        "workflow_id": "2038860299301818369",
        "node_info_list": [{"node_id": "1", "field_name": "text", "field_value": "hello"}],
    }

    check = client.post("/api/runninghub/check", json=payload)
    submit = client.post("/api/runninghub/submit?dry_run=true", json=payload)

    assert check.status_code == 200
    assert check.json()["ready"] is True
    assert submit.status_code == 200
    assert submit.json()["status"] == "dry_run"
    assert "secret-value" not in json.dumps(submit.json())


def test_runninghub_cli_check_and_dry_submit(tmp_path, monkeypatch):
    monkeypatch.setenv("RUNNINGHUB_API_KEY", "secret-value")
    request_path = tmp_path / "runninghub.json"
    request_path.write_text(
        json.dumps(
            {
                "workflow_id": "2038860299301818369",
                "node_info_list": [
                    {"node_id": "1", "field_name": "text", "field_value": "hello"}
                ],
            }
        ),
        encoding="utf-8",
    )

    check = subprocess.run(
        [
            sys.executable,
            "-m",
            "relief_story_agent.cli",
            "runninghub-check",
            "--request",
            str(request_path),
            "--pretty",
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    submit = subprocess.run(
        [
            sys.executable,
            "-m",
            "relief_story_agent.cli",
            "runninghub-submit",
            "--request",
            str(request_path),
            "--dry-run",
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert check.returncode == 0
    assert json.loads(check.stdout)["ready"] is True
    assert submit.returncode == 0
    assert json.loads(submit.stdout)["payload"]["apiKey"] == "<redacted:RUNNINGHUB_API_KEY>"
    assert "secret-value" not in submit.stdout


def test_submit_runninghub_storyboard_and_wait(monkeypatch, tmp_path):
    monkeypatch.setenv("RUNNINGHUB_API_KEY", "secret-value")

    wf_path = tmp_path / "wf.json"
    wf_path.write_text(json.dumps({
        "3": {
            "inputs": {
                "noise_seed": 123,
                "text": "test"
            },
            "class_type": "KSampler"
        }
    }))

    from relief_story_agent.models import ComfyUIRunConfig
    from relief_story_agent.runninghub import submit_runninghub_storyboard, wait_for_runninghub_outputs

    config = ComfyUIRunConfig(
        enabled=True,
        workflow_api_path=str(wf_path),
        runninghub_workflow_id="rh-123",
        max_queue_size=2,
        wait_for_completion=True
    )

    storyboard = [{
        "time_range": "0-10s",
        "description": "shot 1",
        "image_prompt": "prompt 1",
        "negative_prompt": "",
        "comfyui_inputs": {
            "seed": 12345
        }
    }]

    monkeypatch.setattr(
        "relief_story_agent.comfyui.plan_storyboard_workflows",
        lambda *args, **kwargs: [
            type("Planned", (), {
                "submission_key": "ltx",
                "workflow": {
                    "3": {"inputs": {"noise_seed": 12345, "text": "prompt 1"}}
                },
                "replacements": [
                    {"node": "3", "input": "noise_seed", "key": "seed"},
                    {"node": "3", "input": "text", "key": "ltx_payload"}
                ]
            })
        ]
    )

    requests = []
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content.decode("utf-8"))
        requests.append((request.url.path, payload))
        if request.url.path == "/task/openapi/create":
            return httpx.Response(200, json={"code": 0, "data": {"taskId": "task-cloud-99"}})
        if request.url.path == "/task/openapi/status":
            return httpx.Response(200, json={"code": 0, "data": {"status": "SUCCESS"}})
        if request.url.path == "/task/openapi/outputs":
            return httpx.Response(200, json={"code": 0, "data": [{"fileUrl": "https://cdn.example/vid99.mp4"}]})
        return httpx.Response(404)

    client = httpx.Client(transport=httpx.MockTransport(handler))

    subs = submit_runninghub_storyboard(
        config,
        storyboard,
        "run-99",
        client=client
    )

    assert len(subs) == 1
    assert subs[0].prompt_id == "task-cloud-99"
    assert subs[0].status == "accepted"

    outputs = wait_for_runninghub_outputs(
        config,
        [sub.prompt_id for sub in subs],
        client=client
    )

    assert len(outputs) == 1
    assert outputs[0].url == "https://cdn.example/vid99.mp4"
    assert outputs[0].filename == "vid99.mp4"


def test_orchestrator_submits_to_runninghub_when_provider_is_configured(monkeypatch, tmp_path):
    submitted = False
    waited = False

    def mock_submit(config, storyboard, run_id, **kwargs):
        nonlocal submitted
        submitted = True
        from relief_story_agent.models import ComfyUISubmission
        return [ComfyUISubmission(
            submission_key="ltx",
            content_fingerprint="abc",
            prompt_id="task-123",
            client_id="runninghub",
            status="accepted"
        )]

    def mock_wait(config, task_ids, **kwargs):
        nonlocal waited
        waited = True
        from relief_story_agent.models import ComfyUIOutput
        return [ComfyUIOutput(
            prompt_id="task-123",
            filename="output.mp4"
        )]

    monkeypatch.setattr("relief_story_agent.orchestrator.submit_runninghub_storyboard", mock_submit)
    monkeypatch.setattr("relief_story_agent.orchestrator.wait_for_runninghub_outputs", mock_wait)

    from relief_story_agent.orchestrator import StoryRunOrchestrator
    from relief_story_agent.models import RunRequest, ComfyUIRunConfig, RenderBackendSpec
    from relief_story_agent.providers import FakeModelProvider
    from relief_story_agent.orchestrator import InMemoryRunStore

    orchestrator = StoryRunOrchestrator(
        provider=FakeModelProvider.minimal_success(),
        store=InMemoryRunStore()
    )

    req = RunRequest(
        idea="runninghub test",
        render_backend=RenderBackendSpec(provider="runninghub_workflow"),
        comfyui=ComfyUIRunConfig(
            enabled=True,
            workflow_api_path="some_path.json",
            runninghub_workflow_id="rh-123",
            wait_for_completion=True
        )
    )

    run = orchestrator.create_run(req)
    run.storyboard = [{"time_range": "0-10s", "description": "shot 1", "image_prompt": "prompt 1", "negative_prompt": "", "comfyui_inputs": {}}]
    run.final_storyboard = run.storyboard

    orchestrator._run_stage(run, "comfyui")

    assert submitted is True
    assert waited is True
    assert run.comfyui_outputs[0].filename == "output.mp4"

