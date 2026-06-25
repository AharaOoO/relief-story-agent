import json
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from relief_story_agent.api import create_app
from relief_story_agent.artifacts import read_run_artifact_index, write_run_artifacts
from relief_story_agent.comfyui import (
    ComfyUIWaitCancelled,
    cancel_prompt_jobs,
    collect_prompt_outputs,
    download_prompt_outputs,
    wait_for_prompt_outputs,
)
from relief_story_agent.comfyui_outputs import refresh_comfyui_prompt_outputs
from relief_story_agent.models import (
    ComfyUIOutput,
    ComfyUIOutputRefreshRequest,
    ComfyUIRunConfig,
    RunRequest,
    RunRetryRequest,
    RunState,
)
from relief_story_agent.orchestrator import InMemoryRunStore, StoryRunOrchestrator
from relief_story_agent.providers import FakeModelProvider


HTTPX_CLIENT = httpx.Client


def test_cancel_prompt_jobs_uses_exact_modern_job_endpoint():
    requests: list[tuple[str, str]] = []

    def handler(request: httpx.Request):
        requests.append((request.method, request.url.path))
        assert request.method == "POST"
        assert request.url.path == "/api/jobs/prompt_1/cancel"
        return httpx.Response(200, json={"cancelled": True})

    results = cancel_prompt_jobs(
        ComfyUIRunConfig(endpoint="http://comfy.local"),
        ["prompt_1"],
        client=HTTPX_CLIENT(transport=httpx.MockTransport(handler)),
    )

    assert len(results) == 1
    assert results[0].prompt_id == "prompt_1"
    assert results[0].strategy == "job_api"
    assert results[0].cancelled is True
    assert results[0].remote_status == "cancelled"
    assert results[0].error == ""
    assert requests == [("POST", "/api/jobs/prompt_1/cancel")]
    assert all(path != "/interrupt" for _, path in requests)


@pytest.mark.parametrize("unsupported_status", [404, 405])
def test_cancel_prompt_jobs_falls_back_to_legacy_queue_for_unsupported_modern_endpoint(
    unsupported_status,
):
    requests: list[tuple[str, str, dict]] = []

    def handler(request: httpx.Request):
        body = json.loads(request.content) if request.content else {}
        requests.append((request.method, request.url.path, body))
        if request.url.path == "/api/jobs/prompt_1/cancel":
            return httpx.Response(unsupported_status)
        if request.url.path == "/queue":
            return httpx.Response(200, json={})
        raise AssertionError(f"unexpected request: {request.url}")

    results = cancel_prompt_jobs(
        ComfyUIRunConfig(endpoint="http://comfy.local"),
        ["prompt_1"],
        client=HTTPX_CLIENT(transport=httpx.MockTransport(handler)),
    )

    assert results[0].strategy == "legacy_queue"
    assert results[0].cancelled is True
    assert results[0].remote_status == "queued_delete_requested"
    assert requests == [
        ("POST", "/api/jobs/prompt_1/cancel", {}),
        ("POST", "/queue", {"delete": ["prompt_1"]}),
    ]


def test_cancel_prompt_jobs_does_not_use_unsafe_fallback_for_server_error():
    paths: list[str] = []

    def handler(request: httpx.Request):
        paths.append(request.url.path)
        return httpx.Response(500)

    results = cancel_prompt_jobs(
        ComfyUIRunConfig(endpoint="http://comfy.local"),
        ["prompt_1"],
        client=HTTPX_CLIENT(transport=httpx.MockTransport(handler)),
    )

    assert results[0].strategy == "none"
    assert results[0].cancelled is False
    assert results[0].remote_status == "http_500"
    assert results[0].error
    assert paths == ["/api/jobs/prompt_1/cancel"]
    assert "/queue" not in paths
    assert "/interrupt" not in paths


def test_collect_prompt_outputs_reads_images_and_video_files_from_history():
    def handler(request: httpx.Request):
        assert request.method == "GET"
        assert request.url.path == "/history/prompt_1"
        return httpx.Response(
            200,
            json={
                "prompt_1": {
                    "outputs": {
                        "9": {
                            "images": [
                                {
                                    "filename": "frame.png",
                                    "subfolder": "previews",
                                    "type": "output",
                                }
                            ]
                        },
                        "10": {
                            "gifs": [
                                {
                                    "filename": "movie.mp4",
                                    "subfolder": "",
                                    "type": "output",
                                }
                            ]
                        },
                    }
                }
            },
        )

    outputs = collect_prompt_outputs(
        ComfyUIRunConfig(endpoint="http://comfy.local"),
        ["prompt_1"],
        client=HTTPX_CLIENT(transport=httpx.MockTransport(handler)),
    )

    assert [output.filename for output in outputs] == ["frame.png", "movie.mp4"]
    assert outputs[0].media_type == "image"
    assert outputs[1].media_type == "video"
    assert outputs[1].url == "http://comfy.local/view?filename=movie.mp4&type=output"


def test_collect_prompt_outputs_prefers_video_extension_when_comfyui_uses_images_bucket():
    def handler(request: httpx.Request):
        assert request.url.path == "/history/prompt_1"
        return httpx.Response(
            200,
            json={
                "prompt_1": {
                    "outputs": {
                        "12": {
                            "images": [
                                {
                                    "filename": "ltx_render.mp4",
                                    "subfolder": "",
                                    "type": "output",
                                }
                            ]
                        }
                    }
                }
            },
        )

    outputs = collect_prompt_outputs(
        ComfyUIRunConfig(endpoint="http://comfy.local"),
        ["prompt_1"],
        client=HTTPX_CLIENT(transport=httpx.MockTransport(handler)),
    )

    assert outputs[0].filename == "ltx_render.mp4"
    assert outputs[0].media_type == "video"


def test_download_prompt_outputs_saves_files_under_artifact_dir(tmp_path):
    def handler(request: httpx.Request):
        assert request.url.path == "/view"
        assert request.url.params["filename"] == "movie.mp4"
        return httpx.Response(200, content=b"video-bytes")

    outputs = download_prompt_outputs(
        [
            ComfyUIOutput(
                prompt_id="prompt_1",
                node_id="10",
                filename="movie.mp4",
                media_type="video",
                url="http://comfy.local/view?filename=movie.mp4&type=output",
            )
        ],
        tmp_path,
        client=HTTPX_CLIENT(transport=httpx.MockTransport(handler)),
    )

    local_path = Path(outputs[0].local_path)
    assert local_path.parent.name == "comfyui_outputs"
    assert local_path.name == "prompt_1_10_movie.mp4"
    assert local_path.read_bytes() == b"video-bytes"


def test_wait_for_prompt_outputs_polls_until_history_has_files():
    calls = 0

    def handler(request: httpx.Request):
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(200, json={"prompt_1": {"outputs": {}}})
        return httpx.Response(
            200,
            json={
                "prompt_1": {
                    "outputs": {
                        "10": {
                            "videos": [
                                {
                                    "filename": "movie.mp4",
                                    "subfolder": "",
                                    "type": "output",
                                }
                            ]
                        }
                    }
                }
            },
        )

    outputs = wait_for_prompt_outputs(
        ComfyUIRunConfig(endpoint="http://comfy.local"),
        ["prompt_1"],
        timeout_seconds=1,
        poll_interval_seconds=0,
        client=HTTPX_CLIENT(transport=httpx.MockTransport(handler)),
        sleep_fn=lambda _: None,
    )

    assert calls == 2
    assert outputs[0].filename == "movie.mp4"


def test_wait_for_prompt_outputs_stops_when_cancellation_is_requested():
    history_calls = 0
    cancellation_checks = 0

    def handler(request: httpx.Request):
        nonlocal history_calls
        history_calls += 1
        return httpx.Response(200, json={"prompt_1": {"outputs": {}}})

    def should_cancel():
        nonlocal cancellation_checks
        cancellation_checks += 1
        return cancellation_checks >= 2

    with pytest.raises(ComfyUIWaitCancelled):
        wait_for_prompt_outputs(
            ComfyUIRunConfig(endpoint="http://comfy.local"),
            ["prompt_1"],
            timeout_seconds=10,
            poll_interval_seconds=5,
            client=HTTPX_CLIENT(transport=httpx.MockTransport(handler)),
            sleep_fn=lambda _: None,
            should_cancel=should_cancel,
        )

    assert history_calls == 1
    assert cancellation_checks == 2


def test_wait_for_prompt_outputs_checks_cancellation_during_long_poll_sleep():
    cancel_requested = False
    sleep_slices: list[float] = []

    def handler(request: httpx.Request):
        return httpx.Response(200, json={"prompt_1": {"outputs": {}}})

    def sleep_fn(seconds: float):
        nonlocal cancel_requested
        sleep_slices.append(seconds)
        cancel_requested = True

    with pytest.raises(ComfyUIWaitCancelled):
        wait_for_prompt_outputs(
            ComfyUIRunConfig(endpoint="http://comfy.local"),
            ["prompt_1"],
            timeout_seconds=10,
            poll_interval_seconds=5,
            client=HTTPX_CLIENT(transport=httpx.MockTransport(handler)),
            sleep_fn=sleep_fn,
            should_cancel=lambda: cancel_requested,
        )

    assert sleep_slices == [1.0]


def test_wait_for_prompt_outputs_prefers_cancellation_observed_during_history_request():
    cancel_requested = False

    def handler(request: httpx.Request):
        nonlocal cancel_requested
        if request.url.path.startswith("/history/"):
            cancel_requested = True
            prompt_id = request.url.path.rsplit("/", 1)[-1]
            return httpx.Response(200, json={prompt_id: {"outputs": {}}})
        if request.url.path == "/queue":
            return httpx.Response(200, json={})
        raise AssertionError(f"unexpected request: {request.url}")

    with pytest.raises(ComfyUIWaitCancelled):
        wait_for_prompt_outputs(
            ComfyUIRunConfig(endpoint="http://comfy.local"),
            ["prompt_1"],
            timeout_seconds=0,
            poll_interval_seconds=0,
            client=HTTPX_CLIENT(transport=httpx.MockTransport(handler)),
            sleep_fn=lambda _: None,
            should_cancel=lambda: cancel_requested,
        )


def test_standalone_comfyui_output_refresh_waits_and_downloads(tmp_path):
    def handler(request: httpx.Request):
        if request.url.path == "/history/prompt_1":
            return httpx.Response(
                200,
                json={
                    "prompt_1": {
                        "outputs": {
                            "12": {
                                "videos": [
                                    {
                                        "filename": "standalone.mp4",
                                        "subfolder": "",
                                        "type": "output",
                                    }
                                ]
                            }
                        }
                    }
                },
            )
        if request.url.path == "/view":
            return httpx.Response(200, content=b"standalone-video")
        raise AssertionError(f"unexpected request: {request.url}")

    result = refresh_comfyui_prompt_outputs(
        ComfyUIOutputRefreshRequest(
            endpoint="http://comfy.local",
            prompt_ids=["prompt_1"],
            artifact_dir=str(tmp_path),
            wait_for_completion=True,
            download_outputs=True,
            output_timeout_seconds=1,
            output_poll_interval_seconds=0,
        ),
        client=HTTPX_CLIENT(transport=httpx.MockTransport(handler)),
        sleep_fn=lambda _: None,
    )

    assert result["ready"] is True
    assert result["status"] == "ready"
    assert result["output_count"] == 1
    assert result["video_count"] == 1
    assert result["downloaded_count"] == 1
    assert Path(result["actual_outputs"][0]["local_path"]).read_bytes() == b"standalone-video"


def test_standalone_comfyui_output_refresh_returns_error_when_endpoint_is_unreachable():
    def handler(request: httpx.Request):
        raise httpx.ConnectError("offline", request=request)

    result = refresh_comfyui_prompt_outputs(
        ComfyUIOutputRefreshRequest(
            endpoint="http://comfy.local",
            prompt_ids=["prompt_1"],
        ),
        client=HTTPX_CLIENT(transport=httpx.MockTransport(handler)),
    )

    assert result["ready"] is False
    assert result["status"] == "error"
    assert "offline" in result["error"]
    assert result["actual_outputs"] == []


def test_api_refreshes_standalone_comfyui_outputs(tmp_path, monkeypatch):
    captured: dict[str, object] = {}

    def fake_refresh(request: ComfyUIOutputRefreshRequest):
        captured["request"] = request
        return {
            "endpoint": request.endpoint,
            "prompt_ids": request.prompt_ids,
            "status": "ready",
            "ready": True,
            "output_count": 1,
            "video_count": 1,
            "image_count": 0,
            "audio_count": 0,
            "downloaded_count": 0,
            "artifact_dir": request.artifact_dir,
            "actual_outputs": [
                {
                    "prompt_id": "prompt_1",
                    "node_id": "12",
                    "filename": "api.mp4",
                    "subfolder": "",
                    "type": "output",
                    "media_type": "video",
                    "url": "http://comfy.local/view?filename=api.mp4&type=output",
                    "local_path": "",
                }
            ],
            "diagnostics": {},
        }

    monkeypatch.setattr(
        "relief_story_agent.api.refresh_comfyui_prompt_outputs",
        fake_refresh,
    )
    client = TestClient(
        create_app(
            StoryRunOrchestrator(
                provider=FakeModelProvider.minimal_success(),
                store=InMemoryRunStore(),
            )
        )
    )

    response = client.post(
        "/api/comfyui/outputs",
        json={
            "endpoint": "comfy.local:8188",
            "prompt_ids": ["prompt_1"],
            "artifact_dir": str(tmp_path),
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ready"] is True
    assert body["actual_outputs"][0]["filename"] == "api.mp4"
    request = captured["request"]
    assert isinstance(request, ComfyUIOutputRefreshRequest)
    assert request.endpoint == "http://comfy.local:8188"
    assert request.prompt_ids == ["prompt_1"]


def test_api_refreshes_comfyui_outputs_and_artifact_index(tmp_path, monkeypatch):
    config = ComfyUIRunConfig(enabled=True, endpoint="http://comfy.local")
    run = RunState(
        run_id="run_outputs",
        request=RunRequest(
            idea="output recovery",
            output_root=str(tmp_path),
            comfyui=config,
        ),
        script={"duration_seconds": 90},
        final_storyboard=[{"shot_id": 1, "image_prompt": "quiet street"}],
        comfyui_prompt_ids=["prompt_1"],
    )
    write_run_artifacts(run)

    store = InMemoryRunStore()
    store.save(run)
    orchestrator = StoryRunOrchestrator(
        provider=FakeModelProvider.minimal_success(),
        store=store,
    )

    def handler(request: httpx.Request):
        if request.url.path == "/view":
            return httpx.Response(200, content=b"rendered-video")
        if request.url.path == "/history/prompt_1":
            return httpx.Response(
                200,
                json={
                    "prompt_1": {
                        "outputs": {
                            "12": {
                                "videos": [
                                    {
                                        "filename": "run_outputs.mp4",
                                        "subfolder": "",
                                        "type": "output",
                                    }
                                ]
                            }
                        }
                    }
                },
            )
        raise AssertionError(f"unexpected request: {request.url}")

    monkeypatch.setattr(
        "relief_story_agent.comfyui.httpx.Client",
        lambda **kwargs: HTTPX_CLIENT(transport=httpx.MockTransport(handler)),
    )

    client = TestClient(create_app(orchestrator))
    response = client.post(f"/api/runs/{run.run_id}/refresh-comfyui")

    assert response.status_code == 200
    body = response.json()
    assert body["actual_outputs"][0]["filename"] == "run_outputs.mp4"
    assert body["actual_outputs"][0]["media_type"] == "video"
    assert Path(body["actual_outputs"][0]["local_path"]).read_bytes() == b"rendered-video"

    refreshed = store.get(run.run_id)
    assert refreshed.comfyui_outputs[0].filename == "run_outputs.mp4"
    assert read_run_artifact_index(refreshed)["actual_outputs"][0]["filename"] == "run_outputs.mp4"


def test_comfyui_stage_can_wait_for_completion_and_download_outputs(tmp_path, monkeypatch):
    workflow_path = tmp_path / "workflow_api.json"
    workflow_path.write_text(
        json.dumps({"1": {"class_type": "PromptNode", "inputs": {"text": "old"}}}),
        encoding="utf-8",
    )
    config = ComfyUIRunConfig(
        enabled=True,
        endpoint="http://comfy.local",
        workflow_api_path=str(workflow_path),
        wait_for_completion=True,
        output_timeout_seconds=1,
        output_poll_interval_seconds=0,
        placeholder_map={
            "positive": {"node": "1", "input": "text", "source": "image_prompt"}
        },
    )
    store = InMemoryRunStore()
    run = RunState(
        run_id="run_auto_wait",
        request=RunRequest(
            idea="auto wait",
            output_root=str(tmp_path),
            comfyui=config,
        ),
        final_storyboard=[{"shot_id": 1, "image_prompt": "quiet street"}],
    )
    store.save(run)

    def handler(request: httpx.Request):
        if request.url.path == "/prompt":
            payload = json.loads(request.content)
            return httpx.Response(200, json={"prompt_id": payload["prompt_id"]})
        if request.url.path.startswith("/history/"):
            prompt_id = request.url.path.rsplit("/", 1)[-1]
            return httpx.Response(
                200,
                json={
                    prompt_id: {
                        "outputs": {
                            "12": {
                                "videos": [
                                    {
                                        "filename": "run_auto_wait.mp4",
                                        "subfolder": "",
                                        "type": "output",
                                    }
                                ]
                            }
                        }
                    }
                },
            )
        if request.url.path == "/view":
            return httpx.Response(200, content=b"auto-video")
        raise AssertionError(f"unexpected request: {request.url}")

    monkeypatch.setattr(
        "relief_story_agent.comfyui.httpx.Client",
        lambda **kwargs: HTTPX_CLIENT(transport=httpx.MockTransport(handler)),
    )
    orchestrator = StoryRunOrchestrator(
        provider=FakeModelProvider.minimal_success(),
        store=store,
    )

    orchestrator._execute(run, start_stage="comfyui")

    completed = store.get(run.run_id)
    assert completed.status == "completed"
    assert completed.comfyui_outputs[0].filename == "run_auto_wait.mp4"
    assert Path(completed.comfyui_outputs[0].local_path).read_bytes() == b"auto-video"
    assert read_run_artifact_index(completed)["actual_outputs"][0]["filename"] == "run_auto_wait.mp4"


def test_comfyui_wait_timeout_records_diagnostics_and_retry_reuses_prompt(
    tmp_path,
    monkeypatch,
):
    workflow_path = tmp_path / "workflow_api.json"
    workflow_path.write_text(
        json.dumps({"1": {"class_type": "PromptNode", "inputs": {"text": "old"}}}),
        encoding="utf-8",
    )
    config = ComfyUIRunConfig(
        enabled=True,
        endpoint="http://comfy.local",
        workflow_api_path=str(workflow_path),
        wait_for_completion=True,
        output_timeout_seconds=0,
        output_poll_interval_seconds=0,
        placeholder_map={
            "positive": {"node": "1", "input": "text", "source": "image_prompt"}
        },
    )
    store = InMemoryRunStore()
    run = RunState(
        run_id="run_timeout_recover",
        request=RunRequest(
            idea="timeout recover",
            output_root=str(tmp_path),
            comfyui=config,
        ),
        final_storyboard=[{"shot_id": 1, "image_prompt": "quiet street"}],
    )
    store.save(run)
    prompt_id = ""

    def timeout_handler(request: httpx.Request):
        nonlocal prompt_id
        if request.url.path == "/prompt":
            payload = json.loads(request.content)
            prompt_id = payload["prompt_id"]
            return httpx.Response(200, json={"prompt_id": prompt_id})
        if request.url.path.startswith("/history/"):
            current_prompt_id = request.url.path.rsplit("/", 1)[-1]
            return httpx.Response(200, json={current_prompt_id: {"outputs": {}}})
        if request.url.path == "/queue":
            return httpx.Response(
                200,
                json={"queue_running": [], "queue_pending": [[0, prompt_id, None, {}]]},
            )
        raise AssertionError(f"unexpected request: {request.url}")

    monkeypatch.setattr(
        "relief_story_agent.comfyui.httpx.Client",
        lambda **kwargs: HTTPX_CLIENT(transport=httpx.MockTransport(timeout_handler)),
    )
    orchestrator = StoryRunOrchestrator(
        provider=FakeModelProvider.minimal_success(),
        store=store,
    )

    orchestrator._execute(run, start_stage="comfyui")

    failed = store.get(run.run_id)
    assert failed.status == "failed"
    assert failed.failed_stage == "comfyui"
    assert failed.comfyui_prompt_ids == [prompt_id]
    assert failed.comfyui_diagnostics["prompt_ids"] == [prompt_id]
    assert failed.comfyui_diagnostics["queue"]["queue_pending"][0][1] == prompt_id
    assert read_run_artifact_index(failed)["comfyui_diagnostics"]["prompt_ids"] == [prompt_id]

    def recovered_handler(request: httpx.Request):
        if request.url.path == "/prompt":
            raise AssertionError("retry must not submit a duplicate ComfyUI prompt")
        if request.url.path.startswith("/history/"):
            current_prompt_id = request.url.path.rsplit("/", 1)[-1]
            return httpx.Response(
                200,
                json={
                    current_prompt_id: {
                        "outputs": {
                            "12": {
                                "videos": [
                                    {
                                        "filename": "recovered.mp4",
                                        "subfolder": "",
                                        "type": "output",
                                    }
                                ]
                            }
                        }
                    }
                },
            )
        if request.url.path == "/view":
            return httpx.Response(200, content=b"recovered-video")
        raise AssertionError(f"unexpected request: {request.url}")

    monkeypatch.setattr(
        "relief_story_agent.comfyui.httpx.Client",
        lambda **kwargs: HTTPX_CLIENT(transport=httpx.MockTransport(recovered_handler)),
    )

    recovered = orchestrator.retry(
        run.run_id,
        RunRetryRequest(from_stage="comfyui"),
    )

    assert recovered.status == "completed"
    assert recovered.comfyui_prompt_ids == [prompt_id]
    assert recovered.comfyui_outputs[0].filename == "recovered.mp4"
    assert Path(recovered.comfyui_outputs[0].local_path).read_bytes() == b"recovered-video"
