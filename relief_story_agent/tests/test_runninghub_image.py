from __future__ import annotations

import io
import json

import httpx
import pytest
from PIL import Image, ImageDraw

from relief_story_agent.models import GridImageConfig
from relief_story_agent.runninghub_image import RunningHubImageTaskProvider


def _image_bytes(size=(1600, 900)) -> bytes:
    image = Image.new("RGB", size, "white")
    draw = ImageDraw.Draw(image)
    half_w = size[0] // 2
    half_h = size[1] // 2
    for index, color in enumerate(("red", "green", "blue", "yellow")):
        left = (index % 2) * half_w
        top = (index // 2) * half_h
        image.paste(color, (left, top, left + half_w, top + half_h))
        draw.line((left + 10, top + 10, left + 100, top + 100), fill="black")
    output = io.BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def test_runninghub_g2_creates_polls_and_downloads_2k_landscape(monkeypatch):
    monkeypatch.setenv("RUNNINGHUB_AI_API_KEY", "ai-secret")
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "cdn.example":
            return httpx.Response(
                200,
                content=_image_bytes(),
                headers={"content-type": "image/png"},
            )
        payload = json.loads(request.content.decode("utf-8"))
        requests.append((request.url.path, payload, request.headers["authorization"]))
        if request.url.path.endswith("/rhart-image-g-2/text-to-image"):
            return httpx.Response(200, json={"code": 0, "data": {"taskId": "g2-1"}})
        if request.url.path == "/openapi/v2/query":
            return httpx.Response(
                200,
                json={
                    "code": 0,
                    "data": {
                        "status": "SUCCESS",
                        "results": [{"url": "https://cdn.example/g2.png"}],
                    },
                },
            )
        return httpx.Response(404)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = RunningHubImageTaskProvider(
        client=client,
        sleep_fn=lambda _: None,
    )
    config = GridImageConfig(
        provider="runninghub_image_task",
        runninghub_site="ai",
        model="rhart-image-g-2",
        aspect_ratio="16:9",
        resolution="2k",
        output_poll_interval_seconds=0,
    )

    generated = provider.generate(prompt="A cinematic 2x2 contact sheet", config=config)

    assert generated.content.startswith(b"\x89PNG")
    assert generated.task_id == "g2-1"
    assert generated.provider == "runninghub_image_task"
    assert requests == [
        (
            "/openapi/v2/rhart-image-g-2/text-to-image",
            {
                "prompt": "A cinematic 2x2 contact sheet",
                "aspectRatio": "16:9",
                "resolution": "2k",
            },
            "Bearer ai-secret",
        ),
        (
            "/openapi/v2/query",
            {"taskId": "g2-1"},
            "Bearer ai-secret",
        ),
    ]


def test_runninghub_g2_uses_domestic_site_and_portrait_payload(monkeypatch):
    monkeypatch.setenv("RUNNINGHUB_CN_API_KEY", "cn-secret")
    captured = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "cdn.example":
            return httpx.Response(200, content=_image_bytes((900, 1600)))
        captured.append((str(request.url), json.loads(request.content)))
        if request.url.path.endswith("text-to-image"):
            return httpx.Response(200, json={"data": {"taskId": "g2-cn"}})
        return httpx.Response(
            200,
            json={
                "data": {
                    "status": "COMPLETED",
                    "result": {"fileUrl": "https://cdn.example/g2-cn.png"},
                }
            },
        )

    provider = RunningHubImageTaskProvider(
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        sleep_fn=lambda _: None,
    )
    generated = provider.generate(
        prompt="Portrait grid",
        config=GridImageConfig(
            provider="runninghub_image_task",
            runninghub_site="cn",
            model="rhart-image-g-2",
            aspect_ratio="9:16",
            resolution="2k",
            output_poll_interval_seconds=0,
        ),
    )

    assert captured[0][0].startswith("https://www.runninghub.cn/")
    assert captured[0][1]["aspectRatio"] == "9:16"
    assert generated.task_id == "g2-cn"


def test_runninghub_g2_preserves_safe_error_details_from_create_response(monkeypatch):
    monkeypatch.setenv("RUNNINGHUB_AI_API_KEY", "ai-secret")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            401,
            json={
                "code": "ACCOUNT_NOT_ELIGIBLE",
                "message": "Membership or account balance is required",
            },
        )

    provider = RunningHubImageTaskProvider(
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    with pytest.raises(RuntimeError) as captured:
        provider.generate(
            prompt="A cinematic 2x2 contact sheet",
            config=GridImageConfig(
                provider="runninghub_image_task",
                runninghub_site="ai",
                model="rhart-image-g-2",
            ),
        )

    error = captured.value
    assert getattr(error, "status_code", None) == 401
    assert "create task" in str(error)
    assert "ACCOUNT_NOT_ELIGIBLE" in str(error)
    assert "Membership or account balance is required" in str(error)
    assert getattr(error, "details", {}) == {
        "operation": "create task",
        "provider_code": "ACCOUNT_NOT_ELIGIBLE",
        "provider_message": "Membership or account balance is required",
    }


def test_runninghub_g2_reports_business_error_from_http_200_create_response(monkeypatch):
    monkeypatch.setenv("RUNNINGHUB_AI_API_KEY", "ai-secret")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "taskId": "",
                "status": "FAILED",
                "errorCode": "INSUFFICIENT_BALANCE",
                "errorMessage": "Please top up before creating a task",
                "results": None,
            },
        )

    provider = RunningHubImageTaskProvider(
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    with pytest.raises(ValueError) as captured:
        provider.generate(
            prompt="A cinematic 2x2 contact sheet",
            config=GridImageConfig(
                provider="runninghub_image_task",
                runninghub_site="ai",
                model="rhart-image-g-2",
            ),
        )

    assert "INSUFFICIENT_BALANCE" in str(captured.value)
    assert "Please top up before creating a task" in str(captured.value)
