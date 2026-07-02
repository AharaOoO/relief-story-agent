from __future__ import annotations

import json
import os
from typing import Any, Mapping

import httpx
from pydantic import BaseModel, ConfigDict, Field, field_validator


DEFAULT_RUNNINGHUB_BASE_URL = "https://www.runninghub.ai"
DEFAULT_RUNNINGHUB_API_KEY_ENV = "RUNNINGHUB_API_KEY"
CREATE_PATH = "/task/openapi/create"
STATUS_PATH = "/task/openapi/status"
OUTPUTS_PATH = "/task/openapi/outputs"


class RunningHubNodeInfo(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    node_id: str | int = Field(alias="nodeId")
    field_name: str = Field(alias="fieldName")
    field_value: Any = Field(alias="fieldValue")
    description: str = ""

    @field_validator("node_id", "field_name")
    @classmethod
    def _non_empty(cls, value: str | int) -> str | int:
        if isinstance(value, str) and not value.strip():
            raise ValueError("value must not be empty")
        return value


class RunningHubWorkflowRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    workflow_id: str | int = Field(alias="workflowId")
    node_info_list: list[RunningHubNodeInfo] = Field(alias="nodeInfoList", min_length=1)
    api_key: str = Field(default="", exclude=True, repr=False)
    api_key_env: str = DEFAULT_RUNNINGHUB_API_KEY_ENV
    base_url: str = DEFAULT_RUNNINGHUB_BASE_URL
    webhook_url: str = Field(default="", alias="webhookUrl")
    use_personal_queue: bool = Field(default=False, alias="usePersonalQueue")
    instance_type: str = Field(default="", alias="instanceType")
    timeout_seconds: float = Field(default=60.0, gt=0)

    @field_validator("workflow_id", "api_key_env")
    @classmethod
    def _required_text(cls, value: str | int) -> str | int:
        if isinstance(value, str) and not value.strip():
            raise ValueError("value must not be empty")
        return value

    @field_validator("base_url")
    @classmethod
    def _normalize_base_url(cls, value: str) -> str:
        normalized = value.strip().rstrip("/")
        if not normalized:
            raise ValueError("base_url must not be empty")
        return normalized


class RunningHubTaskRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    task_id: str = Field(alias="taskId")
    api_key: str = Field(default="", exclude=True, repr=False)
    api_key_env: str = DEFAULT_RUNNINGHUB_API_KEY_ENV
    base_url: str = DEFAULT_RUNNINGHUB_BASE_URL
    timeout_seconds: float = Field(default=60.0, gt=0)

    @field_validator("task_id", "api_key_env")
    @classmethod
    def _required_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("value must not be empty")
        return value

    @field_validator("base_url")
    @classmethod
    def _normalize_base_url(cls, value: str) -> str:
        normalized = value.strip().rstrip("/")
        if not normalized:
            raise ValueError("base_url must not be empty")
        return normalized


class RunningHubTaskOutputsRequest(RunningHubTaskRequest):
    pass


def build_runninghub_create_payload(
    request: RunningHubWorkflowRequest,
    *,
    api_key: str,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "apiKey": api_key,
        "workflowId": request.workflow_id,
        "nodeInfoList": [
            {
                "nodeId": node.node_id,
                "fieldName": node.field_name,
                "fieldValue": node.field_value,
                "description": node.description,
            }
            for node in request.node_info_list
        ],
    }
    if request.webhook_url:
        payload["webhookUrl"] = request.webhook_url
    if request.use_personal_queue:
        payload["usePersonalQueue"] = request.use_personal_queue
    if request.instance_type:
        payload["instanceType"] = request.instance_type
    return payload


def build_runninghub_task_payload(request: RunningHubTaskRequest, *, api_key: str) -> dict[str, Any]:
    return {
        "apiKey": api_key,
        "taskId": request.task_id,
    }


def check_runninghub_request(
    request: RunningHubWorkflowRequest,
    *,
    environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    env = environ if environ is not None else os.environ
    configured = bool(request.api_key or env.get(request.api_key_env))
    checks = [
        _check(
            "runninghub_api_key",
            "pass" if configured else "fail",
            (
                f"{request.api_key_env} is configured."
                if configured
                else f"Set {request.api_key_env} before submitting to RunningHub."
            ),
            {
                "api_key_env": request.api_key_env,
                "secret_configured": configured,
            },
        ),
        _check(
            "runninghub_workflow",
            "pass",
            "RunningHub workflow id and node mapping are present.",
            {
                "workflow_id": request.workflow_id,
                "node_info_count": len(request.node_info_list),
                "base_url": request.base_url,
            },
        ),
    ]
    ready = all(check["status"] == "pass" for check in checks)
    return {
        "status": "ready" if ready else "blocked",
        "ready": ready,
        "provider": "runninghub",
        "mode": "advanced_workflow_api",
        "checks": checks,
        "suggested_actions": [] if ready else ["set_runninghub_api_key_env"],
        "endpoints": {
            "create": f"{request.base_url}{CREATE_PATH}",
            "status": f"{request.base_url}{STATUS_PATH}",
            "outputs": f"{request.base_url}{OUTPUTS_PATH}",
        },
    }


def submit_runninghub_task(
    request: RunningHubWorkflowRequest,
    *,
    client: httpx.Client | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    readiness = check_runninghub_request(request)
    redacted_payload = build_runninghub_create_payload(
        request,
        api_key=_redacted_api_key(request.api_key_env),
    )
    url = f"{request.base_url}{CREATE_PATH}"
    if dry_run:
        return {
            "status": "dry_run",
            "ready": readiness["ready"],
            "provider": "runninghub",
            "mode": "advanced_workflow_api",
            "method": "POST",
            "url": url,
            "payload": redacted_payload,
            "checks": readiness["checks"],
            "suggested_actions": readiness["suggested_actions"],
        }
    if not readiness["ready"]:
        return {
            "status": "blocked",
            "ready": False,
            "provider": "runninghub",
            "mode": "advanced_workflow_api",
            "method": "POST",
            "url": url,
            "payload": redacted_payload,
            "checks": readiness["checks"],
            "suggested_actions": readiness["suggested_actions"],
        }
    api_key = _effective_api_key(request.api_key, request.api_key_env)
    payload = build_runninghub_create_payload(request, api_key=api_key)
    response_payload = _post_json(
        client,
        url,
        payload,
        timeout_seconds=request.timeout_seconds,
    )
    task_id = _extract_task_id(response_payload.get("response"))
    ready = bool(response_payload.get("ok")) and bool(task_id)
    return {
        "status": "submitted" if ready else "remote_error",
        "ready": ready,
        "provider": "runninghub",
        "mode": "advanced_workflow_api",
        "method": "POST",
        "url": url,
        "task_id": task_id,
        "payload": redacted_payload,
        **response_payload,
    }


def fetch_runninghub_status(
    request: RunningHubTaskRequest,
    *,
    client: httpx.Client | None = None,
) -> dict[str, Any]:
    return _post_runninghub_task_endpoint(
        request,
        client=client,
        path=STATUS_PATH,
        result_name="status",
    )


def fetch_runninghub_outputs(
    request: RunningHubTaskOutputsRequest,
    *,
    client: httpx.Client | None = None,
) -> dict[str, Any]:
    return _post_runninghub_task_endpoint(
        request,
        client=client,
        path=OUTPUTS_PATH,
        result_name="outputs",
    )


def _post_runninghub_task_endpoint(
    request: RunningHubTaskRequest,
    *,
    client: httpx.Client | None,
    path: str,
    result_name: str,
) -> dict[str, Any]:
    api_key = _effective_api_key(request.api_key, request.api_key_env)
    url = f"{request.base_url}{path}"
    payload = build_runninghub_task_payload(request, api_key=api_key)
    redacted_payload = build_runninghub_task_payload(
        request,
        api_key=_redacted_api_key(request.api_key_env),
    )
    response_payload = _post_json(
        client,
        url,
        payload,
        timeout_seconds=request.timeout_seconds,
    )
    response = response_payload.get("response")
    data = _response_data(response)
    remote_status = _extract_remote_status(data) if result_name == "status" else ""
    outputs = _extract_outputs(data) if result_name == "outputs" else []
    ready = bool(response_payload.get("ok"))
    return {
        "status": "received" if ready else "remote_error",
        "ready": ready,
        "provider": "runninghub",
        "method": "POST",
        "url": url,
        "task_id": request.task_id,
        "payload": redacted_payload,
        "remote_status": remote_status,
        "outputs": outputs,
        **response_payload,
    }


def _effective_api_key(explicit: str, env_name: str) -> str:
    key = explicit or os.environ.get(env_name, "")
    if not key:
        raise ValueError(f"Missing RunningHub API key. Set {env_name}.")
    return key


def _redacted_api_key(env_name: str) -> str:
    return f"<redacted:{env_name}>"


def _post_json(
    client: httpx.Client | None,
    url: str,
    payload: dict[str, Any],
    *,
    timeout_seconds: float,
) -> dict[str, Any]:
    owns_client = client is None
    active_client = client or httpx.Client(timeout=timeout_seconds, trust_env=False)
    try:
        response = active_client.post(url, json=payload)
        parsed = _parse_json_response(response)
        return {
            "ok": 200 <= response.status_code < 300 and _remote_code_ok(parsed),
            "http_status": response.status_code,
            "response": parsed,
        }
    except httpx.RequestError as exc:
        return {
            "ok": False,
            "http_status": 0,
            "response": {},
            "error": f"Unable to reach RunningHub: {exc}",
        }
    finally:
        if owns_client:
            active_client.close()


def _parse_json_response(response: httpx.Response) -> dict[str, Any]:
    try:
        parsed = response.json()
    except json.JSONDecodeError:
        return {"raw_text": response.text}
    return parsed if isinstance(parsed, dict) else {"data": parsed}


def _remote_code_ok(response: dict[str, Any]) -> bool:
    code = response.get("code")
    if code in (None, 0, "0", "success", "SUCCESS"):
        return True
    return False


def _response_data(response: Any) -> Any:
    if isinstance(response, dict) and "data" in response:
        return response["data"]
    return response


def _extract_task_id(response: Any) -> str:
    data = _response_data(response)
    if isinstance(data, dict):
        return str(data.get("taskId") or data.get("task_id") or data.get("task_id_str") or "")
    if isinstance(data, str):
        return data
    return ""


def _extract_remote_status(data: Any) -> str:
    if isinstance(data, dict):
        return str(data.get("status") or data.get("taskStatus") or data.get("state") or "")
    if isinstance(data, str):
        return data
    return ""


def _extract_outputs(data: Any) -> list[Any]:
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        outputs = data.get("outputs") or data.get("data") or data.get("files")
        if isinstance(outputs, list):
            return outputs
    return []


def _check(
    check_id: str,
    status: str,
    message: str,
    details: dict[str, Any],
) -> dict[str, Any]:
    return {
        "id": check_id,
        "status": status,
        "message": message,
        "details": details,
    }


class RunningHubWaitCancelled(RuntimeError):
    """Raised when a run cancellation is observed while waiting for RunningHub outputs."""


class RunningHubOutputTimeout(TimeoutError):
    def __init__(self, message: str, diagnostics: dict[str, Any]):
        super().__init__(message)
        self.diagnostics = diagnostics


def submit_runninghub_storyboard(
    config: ComfyUIRunConfig,
    storyboard: list[dict[str, Any]],
    run_id: str,
    *,
    duration_seconds: int = 90,
    existing_submissions: list[ComfyUISubmission] | None = None,
    on_update: Any = None,
    client: httpx.Client | None = None,
    grid_image_asset: GridImageAsset | None = None,
) -> list[ComfyUISubmission]:
    from .comfyui import plan_storyboard_workflows, _content_fingerprint, _new_submission, _update_submission, _notify

    existing = existing_submissions or []
    submissions: list[ComfyUISubmission] = []

    planned_workflows = plan_storyboard_workflows(
        config,
        storyboard,
        run_id,
        duration_seconds=duration_seconds,
        grid_image_asset=grid_image_asset,
        allow_unuploaded_grid_image=True,
    )

    for planned in planned_workflows:
        fingerprint = _content_fingerprint(planned.workflow)
        previous = next(
            (
                item
                for item in existing
                if item.submission_key == planned.submission_key
                and item.content_fingerprint == fingerprint
            ),
            None,
        )
        submission = previous.model_copy(deep=True) if previous else _new_submission(
            run_id,
            planned.submission_key,
            fingerprint,
        )
        submissions.append(submission)
        if submission.status == "accepted":
            continue

        _update_submission(submission, status="prepared", error="")
        if on_update:
            _notify(on_update, submissions)

        node_info_list = []
        for rep in planned.replacements:
            node_id = str(rep["node"])
            field_name = rep["input"]
            try:
                field_value = planned.workflow[node_id]["inputs"][field_name]
            except KeyError:
                field_value = rep.get("value_preview", "")

            node_info_list.append(RunningHubNodeInfo(
                nodeId=node_id,
                fieldName=field_name,
                fieldValue=field_value,
                description=rep.get("key", "")
            ))

        wf_id = config.runninghub_workflow_id or str(config.workflow_api_path or "")
        request = RunningHubWorkflowRequest(
            workflowId=wf_id,
            nodeInfoList=node_info_list,
            api_key_env=config.api_key_env or DEFAULT_RUNNINGHUB_API_KEY_ENV,
        )

        try:
            res = submit_runninghub_task(request, client=client)
            if res.get("status") == "submitted":
                task_id = res.get("task_id")
                _update_submission(submission, status="accepted", prompt_id=task_id)
                if on_update:
                    _notify(on_update, submissions)
            else:
                err_msg = res.get("message") or "Failed to submit to RunningHub"
                _update_submission(submission, status="rejected", error=err_msg)
                if on_update:
                    _notify(on_update, submissions)
                raise ValueError(f"RunningHub submission failed: {err_msg}")
        except Exception as exc:
            _update_submission(submission, status="rejected", error=str(exc))
            if on_update:
                _notify(on_update, submissions)
            raise

    return submissions


def wait_for_runninghub_outputs(
    config: ComfyUIRunConfig,
    task_ids: list[str],
    *,
    should_cancel: Any = None,
    client: httpx.Client | None = None,
) -> list[ComfyUIOutput]:
    import time
    from .models import ComfyUIOutput

    outputs: list[ComfyUIOutput] = []
    pending_ids = list(task_ids)

    timeout = config.output_timeout_seconds or 600.0
    poll_interval = config.output_poll_interval_seconds or 5.0
    start_time = time.time()

    while pending_ids:
        if should_cancel and should_cancel():
            raise RunningHubWaitCancelled("RunningHub wait cancelled")

        if time.time() - start_time > timeout:
            raise RunningHubOutputTimeout(
                "RunningHub outputs timeout exceeded",
                {"pending_tasks": pending_ids}
            )

        for task_id in list(pending_ids):
            status_req = RunningHubTaskRequest(
                taskId=task_id,
                api_key_env=config.api_key_env or DEFAULT_RUNNINGHUB_API_KEY_ENV,
            )
            try:
                status_res = fetch_runninghub_status(status_req, client=client)
                remote_status = status_res.get("remote_status")

                if remote_status == "SUCCESS":
                    out_req = RunningHubTaskOutputsRequest(
                        taskId=task_id,
                        api_key_env=config.api_key_env or DEFAULT_RUNNINGHUB_API_KEY_ENV,
                    )
                    out_res = fetch_runninghub_outputs(out_req, client=client)
                    remote_outputs = out_res.get("outputs", [])

                    for out in remote_outputs:
                        file_url = out.get("fileUrl")
                        if file_url:
                            outputs.append(ComfyUIOutput(
                                prompt_id=task_id,
                                node_id="",
                                filename=file_url.split("/")[-1] or "output.mp4",
                                url=file_url,
                            ))
                    pending_ids.remove(task_id)
                elif remote_status in {"FAILED", "CANCELLED"}:
                    raise ValueError(f"RunningHub task {task_id} failed with remote status: {remote_status}")
            except Exception as exc:
                if "failed with remote status" in str(exc):
                    raise
                # Log or ignore transient polling errors to be resilient
                pass

        if pending_ids:
            time.sleep(poll_interval)

    return outputs

