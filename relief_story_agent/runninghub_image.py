from __future__ import annotations

import os
import time
from typing import Any, Callable

import httpx

from .grid_image import GeneratedImage
from .models import GridImageConfig


class RunningHubImageRequestError(RuntimeError):
    def __init__(self, operation: str, response: httpx.Response):
        provider_code = ""
        provider_message = ""
        try:
            body = response.json()
        except (ValueError, TypeError):
            body = {}
        if isinstance(body, dict):
            error = body.get("error")
            if not isinstance(error, dict):
                error = {}
            provider_code = str(
                body.get("code")
                or body.get("errorCode")
                or error.get("code")
                or ""
            )
            provider_message = str(
                body.get("message")
                or body.get("msg")
                or body.get("errorMessage")
                or error.get("message")
                or ""
            )
        detail = ": ".join(
            value for value in (provider_code, provider_message) if value
        )
        suffix = f": {detail}" if detail else ""
        super().__init__(
            f"RunningHub G2 {operation} failed (HTTP {response.status_code}){suffix}"
        )
        self.status_code = response.status_code
        self.details = {
            "operation": operation,
            "provider_code": provider_code,
            "provider_message": provider_message,
        }


class RunningHubImageTaskProvider:
    def __init__(
        self,
        *,
        client: httpx.Client | None = None,
        sleep_fn: Callable[[float], None] = time.sleep,
        monotonic_fn: Callable[[], float] = time.monotonic,
    ):
        self.client = client
        self.sleep_fn = sleep_fn
        self.monotonic_fn = monotonic_fn

    def generate(self, *, prompt: str, config: GridImageConfig) -> GeneratedImage:
        if config.provider != "runninghub_image_task":
            raise ValueError("RunningHub image provider requires runninghub_image_task config")
        api_key = config.api_key or os.environ.get(config.api_key_env, "")
        if not api_key:
            raise ValueError(
                f"Missing environment variable for RunningHub API key: {config.api_key_env}"
            )
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "prompt": prompt,
            "aspectRatio": config.aspect_ratio,
            "resolution": config.resolution,
        }
        client = self.client or httpx.Client()
        create = client.post(
            f"{config.base_url.rstrip('/')}/openapi/v2/{config.model}/text-to-image",
            headers=headers,
            json=payload,
            timeout=config.timeout_seconds,
        )
        self._raise_for_status(create, "create task")
        create_body = self._response_body(create)
        task_id = self._task_id(create_body)
        if not task_id:
            raise ValueError("RunningHub G2 create response is missing taskId")

        started = self.monotonic_fn()
        result_url = ""
        while self.monotonic_fn() - started <= config.output_timeout_seconds:
            query = client.post(
                f"{config.base_url.rstrip('/')}/openapi/v2/query",
                headers=headers,
                json={"taskId": task_id},
                timeout=config.timeout_seconds,
            )
            self._raise_for_status(query, "query task")
            query_body = self._response_body(query)
            status = self._status(query_body)
            if status in {"SUCCESS", "SUCCEEDED", "COMPLETED", "FINISHED"}:
                result_url = self._result_url(query_body)
                if not result_url:
                    raise ValueError("RunningHub G2 completed without an image URL")
                break
            if status in {"FAILED", "ERROR", "CANCELLED", "CANCELED"}:
                raise ValueError(f"RunningHub G2 task {task_id} failed with status {status}")
            self.sleep_fn(config.output_poll_interval_seconds)
        else:
            raise TimeoutError(f"RunningHub G2 task {task_id} timed out")

        downloaded = client.get(result_url, timeout=config.timeout_seconds)
        self._raise_for_status(downloaded, "download image")
        content_type = downloaded.headers.get("content-type", "").split(";", 1)[0]
        if content_type not in {"image/png", "image/jpeg", "image/webp"}:
            content_type = self._detect_mime(downloaded.content)
        return GeneratedImage(
            content=downloaded.content,
            mime_type=content_type,
            provider=config.provider,
            model=config.model,
            task_id=task_id,
            aspect_ratio=config.aspect_ratio,
            resolution=config.resolution,
        )

    @staticmethod
    def _raise_for_status(response: httpx.Response, operation: str) -> None:
        if response.is_error:
            raise RunningHubImageRequestError(operation, response)

    @staticmethod
    def _response_body(response: httpx.Response) -> dict[str, Any]:
        body = response.json()
        if not isinstance(body, dict):
            raise ValueError("RunningHub response must be a JSON object")
        error_code = str(body.get("errorCode") or "").strip()
        error_message = str(body.get("errorMessage") or "").strip()
        task_status = str(body.get("status") or "").upper()
        if error_code or task_status in {"FAILED", "ERROR", "CANCELLED", "CANCELED"}:
            detail = ": ".join(
                value for value in (error_code, error_message or task_status) if value
            )
            raise ValueError(f"RunningHub request failed: {detail}")
        code = body.get("code")
        if code not in {None, 0, "0", 200, "200"}:
            raise ValueError(
                f"RunningHub request failed: {body.get('message') or body.get('msg') or code}"
            )
        return body

    @classmethod
    def _task_id(cls, body: dict[str, Any]) -> str:
        data = body.get("data")
        candidates = [body]
        if isinstance(data, dict):
            candidates.insert(0, data)
        for item in candidates:
            value = item.get("taskId") or item.get("task_id") or item.get("id")
            if value:
                return str(value)
        return ""

    @classmethod
    def _status(cls, body: dict[str, Any]) -> str:
        data = body.get("data")
        candidates = [data, body]
        for item in candidates:
            if isinstance(item, dict):
                value = item.get("status") or item.get("state") or item.get("taskStatus")
                if value:
                    return str(value).upper()
        return "PENDING"

    @classmethod
    def _result_url(cls, body: dict[str, Any]) -> str:
        return cls._find_url(body)

    @classmethod
    def _find_url(cls, value: Any) -> str:
        if isinstance(value, dict):
            for key in ("url", "fileUrl", "imageUrl", "downloadUrl"):
                candidate = value.get(key)
                if isinstance(candidate, str) and candidate.startswith(("http://", "https://")):
                    return candidate
            for nested in value.values():
                candidate = cls._find_url(nested)
                if candidate:
                    return candidate
        elif isinstance(value, list):
            for nested in value:
                candidate = cls._find_url(nested)
                if candidate:
                    return candidate
        return ""

    @staticmethod
    def _detect_mime(content: bytes) -> str:
        if content.startswith(b"\x89PNG\r\n\x1a\n"):
            return "image/png"
        if content.startswith(b"\xff\xd8\xff"):
            return "image/jpeg"
        if content.startswith(b"RIFF") and content[8:12] == b"WEBP":
            return "image/webp"
        raise ValueError("RunningHub G2 download is not a supported image")
