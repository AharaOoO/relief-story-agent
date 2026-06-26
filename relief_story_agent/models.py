from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from .comfyui_endpoint import normalize_comfyui_endpoint


class StageModelConfig(BaseModel):
    base_url: str = "http://127.0.0.1:8045/v1"
    api_key: str = Field(default="", exclude=True, repr=False)
    api_key_env: str = ""
    model: str = ""
    temperature: float = 0.7
    timeout_seconds: float = 60.0
    max_attempts: int = Field(default=3, ge=1, le=10)
    initial_backoff_seconds: float = Field(default=1.0, ge=0)
    backoff_multiplier: float = Field(default=2.0, ge=1.0)
    max_backoff_seconds: float = Field(default=30.0, ge=0)
    retry_jitter_ratio: float = Field(default=0.2, ge=0, le=1)
    requests_per_minute: float = Field(default=0, ge=0)
    input_cost_per_million: float = Field(default=0, ge=0)
    output_cost_per_million: float = Field(default=0, ge=0)


class ModelUsage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class ModelCallResult(BaseModel):
    payload: dict[str, Any]
    model: str = ""
    request_id: str = ""
    usage: ModelUsage = Field(default_factory=ModelUsage)


class ModelProbeRequest(BaseModel):
    real_run: bool = False
    profiles: list[str] = Field(default_factory=list)
    image_config: dict[str, Any] | None = None


class LocalSetupBundleRequest(BaseModel):
    output_dir: str
    workflow_path: str
    comfyui_endpoint: str = "http://127.0.0.1:8188"
    output_root: str = "D:/relief_story_runs"


class ModelAttempt(BaseModel):
    attempt_id: str
    stage: str
    attempt_number: int
    max_attempts: int
    status: Literal[
        "running",
        "succeeded",
        "retryable_failed",
        "permanent_failed",
    ] = "running"
    model: str = ""
    started_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    finished_at: str = ""
    duration_ms: float = 0
    retryable: bool = False
    retry_delay_seconds: float = 0
    error_type: str = ""
    error_message: str = ""
    http_status: int | None = None
    request_id: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    estimated_cost_usd: float = 0


class ModelUsageSummary(BaseModel):
    total_requests: int = 0
    total_attempts: int = 0
    retry_count: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    estimated_cost_usd: float = 0


class PlaceholderTarget(BaseModel):
    node: str
    input: str
    source: str


class GridImageConfig(BaseModel):
    mode: Literal["auto", "manual_override"] = "auto"
    manual_image_path: str | None = None
    provider: Literal["openai_compatible"] = "openai_compatible"
    base_url: str = "https://api.openai.com/v1"
    api_key: str = Field(default="", exclude=True, repr=False)
    api_key_env: str = "OPENAI_API_KEY"
    model: str = "gpt-image-2"
    size: str = "1024x1024"
    quality: Literal["low", "medium", "high", "auto"] = "medium"
    output_format: Literal["png", "jpeg", "webp"] = "png"
    timeout_seconds: float = Field(default=180.0, gt=0)
    max_attempts: int = Field(default=3, ge=1, le=10)
    prompt_max_chars: int = Field(default=4000, ge=500, le=16000)
    min_dimension: int = Field(default=512, ge=64)
    max_bytes: int = Field(default=50 * 1024 * 1024, ge=1024)

    def effective_mode(self) -> Literal["auto", "manual_override"]:
        return "manual_override" if self.manual_image_path else self.mode


class GridImageAttempt(BaseModel):
    attempt_number: int
    status: Literal["running", "succeeded", "failed"] = "running"
    error_type: str = ""
    error_message: str = ""
    started_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    finished_at: str = ""


class GridImageAsset(BaseModel):
    source: Literal["generated", "manual"]
    local_path: str
    sha256: str
    mime_type: Literal["image/png", "image/jpeg", "image/webp"]
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    byte_size: int = Field(gt=0)
    prompt: str = ""
    provider: str = ""
    model: str = ""
    generated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    comfyui_filename: str = ""
    upload_status: Literal["pending", "accepted", "unknown", "rejected"] = "pending"
    upload_error: str = ""


class ComfyUIRunConfig(BaseModel):
    enabled: bool = False
    endpoint: str = "http://127.0.0.1:8188"
    workflow_api_path: str | None = None
    placeholder_map_path: str | None = None
    placeholder_map: dict[str, PlaceholderTarget] = Field(default_factory=dict)
    wait_for_completion: bool = False
    download_outputs: bool = True
    output_timeout_seconds: float = Field(default=600.0, ge=0)
    output_poll_interval_seconds: float = Field(default=5.0, ge=0)
    grid_image: GridImageConfig = Field(default_factory=GridImageConfig)

    @field_validator("endpoint")
    @classmethod
    def _normalize_endpoint(cls, value: str) -> str:
        return normalize_comfyui_endpoint(value)


class ComfyUIConnectionRequest(BaseModel):
    endpoint: str = "http://127.0.0.1:8188"
    workflow_api_path: str | None = None
    placeholder_map_path: str | None = None
    placeholder_map: dict[str, PlaceholderTarget] = Field(default_factory=dict)
    timeout_seconds: float = Field(default=5.0, gt=0, le=60)

    @field_validator("endpoint")
    @classmethod
    def _normalize_endpoint(cls, value: str) -> str:
        return normalize_comfyui_endpoint(value)


class ComfyUIPreviewRequest(BaseModel):
    comfyui: ComfyUIRunConfig
    storyboard: list[dict[str, Any]] = Field(min_length=1)
    run_id: str = "preview"
    duration_seconds: int = 90
    include_workflow: bool = False


class ComfyUIWorkflowAnalysisRequest(BaseModel):
    comfyui: ComfyUIRunConfig


class ComfyUIWorkflowDiscoveryRequest(BaseModel):
    endpoint: str = "http://127.0.0.1:8188"
    search_roots: list[str] = Field(default_factory=list)
    max_results: int = Field(default=25, ge=1, le=500)
    filename_keywords: list[str] = Field(default_factory=list)
    include_unsupported: bool = True

    @field_validator("endpoint")
    @classmethod
    def _normalize_endpoint(cls, value: str) -> str:
        return normalize_comfyui_endpoint(value)


class ComfyUIOutputRefreshRequest(BaseModel):
    endpoint: str = "http://127.0.0.1:8188"
    prompt_ids: list[str] = Field(min_length=1)
    artifact_dir: str = ""
    wait_for_completion: bool = False
    download_outputs: bool = False
    output_timeout_seconds: float = Field(default=600.0, ge=0)
    output_poll_interval_seconds: float = Field(default=5.0, ge=0)

    @field_validator("endpoint")
    @classmethod
    def _normalize_endpoint(cls, value: str) -> str:
        return normalize_comfyui_endpoint(value)

    @field_validator("prompt_ids")
    @classmethod
    def _normalize_prompt_ids(cls, value: list[str]) -> list[str]:
        prompt_ids = [str(item).strip() for item in value if str(item).strip()]
        if not prompt_ids:
            raise ValueError("At least one non-empty prompt id is required")
        return prompt_ids


class ComfyUISubmission(BaseModel):
    submission_key: str
    content_fingerprint: str
    prompt_id: str
    client_id: str
    status: Literal["prepared", "accepted", "unknown", "rejected"] = "prepared"
    error: str = ""
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class ComfyUIOutput(BaseModel):
    prompt_id: str
    node_id: str = ""
    filename: str
    subfolder: str = ""
    type: str = "output"
    media_type: Literal["image", "video", "audio", "other"] = "other"
    url: str = ""
    local_path: str = ""


class ComfyUICancellation(BaseModel):
    prompt_id: str
    strategy: Literal["job_api", "legacy_queue", "none"] = "none"
    cancelled: bool = False
    remote_status: str = ""
    error: str = ""
    checked_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class FailureRecord(BaseModel):
    stage: str
    category: Literal[
        "transient",
        "throttled",
        "timeout",
        "configuration",
        "validation",
        "contract",
        "external",
        "cancelled",
        "unknown",
    ] = "unknown"
    code: str = "unknown_error"
    retryable: bool = False
    source: str = ""
    message: str = ""
    exception_type: str = ""
    http_status: int | None = None
    attempt_number: int | None = None
    details: dict[str, Any] = Field(default_factory=dict)
    recorded_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class TemplatePaths(BaseModel):
    prompt_writer_template_path: str | None = None
    prompt_audit_template_path: str | None = None


class ExecutionPolicy(BaseModel):
    max_total_stage_executions: int = Field(default=0, ge=0)
    max_stage_executions: dict[str, int] = Field(default_factory=dict)

    @field_validator("max_stage_executions")
    @classmethod
    def _validate_stage_execution_limits(cls, value: dict[str, int]) -> dict[str, int]:
        for stage, limit in value.items():
            if not stage:
                raise ValueError("execution policy stage names must be non-empty")
            if limit < 0:
                raise ValueError("execution policy stage limits must be >= 0")
        return value


class RunRequest(BaseModel):
    idempotency_key: str = ""
    idea: str
    queue_priority: int = 0
    audience_pressure: str = ""
    preferred_series: str = ""
    preferred_style: str = ""
    duration_seconds: int = 90
    output_root: str | None = None
    auto_select_core: bool = True
    approval_mode: Literal["auto", "manual"] = "manual"
    comfyui: ComfyUIRunConfig | None = None
    template_paths: TemplatePaths = Field(default_factory=TemplatePaths)
    model_profiles: dict[str, str] = Field(default_factory=dict)
    model_configs: dict[str, StageModelConfig] = Field(default_factory=dict)
    execution_policy: ExecutionPolicy = Field(default_factory=ExecutionPolicy)


class RunRequestDefaults(BaseModel):
    queue_priority: int | None = None
    audience_pressure: str | None = None
    preferred_series: str | None = None
    preferred_style: str | None = None
    duration_seconds: int | None = None
    output_root: str | None = None
    auto_select_core: bool | None = None
    approval_mode: Literal["auto", "manual"] | None = None
    comfyui: ComfyUIRunConfig | None = None
    template_paths: TemplatePaths | None = None
    model_profiles: dict[str, str] | None = None
    model_configs: dict[str, StageModelConfig] | None = None
    execution_policy: ExecutionPolicy | None = None


def apply_run_defaults(defaults: RunRequestDefaults, item: RunRequest) -> RunRequest:
    data = item.model_dump()
    for field_name in defaults.model_fields_set:
        default_value = getattr(defaults, field_name)
        if default_value is None:
            continue
        if field_name not in item.model_fields_set:
            data[field_name] = _dump_default_value(default_value)
            continue
        item_value = getattr(item, field_name)
        if isinstance(default_value, BaseModel) and isinstance(item_value, BaseModel):
            data[field_name] = _merge_model_defaults(default_value, item_value)
        elif isinstance(default_value, dict) and isinstance(item_value, dict):
            data[field_name] = {**default_value, **item_value}
    return RunRequest.model_validate(data)


def _merge_model_defaults(default_value: BaseModel, item_value: BaseModel) -> dict[str, Any]:
    data = default_value.model_dump()
    for field_name in item_value.model_fields_set:
        data[field_name] = getattr(item_value, field_name)
    return data


def _dump_default_value(value: Any) -> Any:
    return value.model_dump() if isinstance(value, BaseModel) else value


class RunRetryRequest(BaseModel):
    from_stage: Literal[
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
    ] | None = None


class BatchRetryRequest(RunRetryRequest):
    pass


class RunLog(BaseModel):
    stage: str
    message: str
    level: Literal["info", "warn", "error"] = "info"
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class RunEvent(BaseModel):
    sequence: int
    run_id: str
    event_type: str
    stage: str = ""
    message: str = ""
    data: dict[str, Any] = Field(default_factory=dict)
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class RunState(BaseModel):
    run_id: str
    request: RunRequest
    idempotency_key: str = ""
    request_fingerprint: str = ""
    status: Literal[
        "queued",
        "paused",
        "running",
        "awaiting_approval",
        "completed",
        "failed",
        "cancelled",
    ] = "queued"
    current_stage: str = "queued"
    logs: list[RunLog] = Field(default_factory=list)
    events: list[RunEvent] = Field(default_factory=list)
    core_candidates: list[dict[str, Any]] = Field(default_factory=list)
    selected_core: dict[str, Any] = Field(default_factory=dict)
    script: dict[str, Any] = Field(default_factory=dict)
    storyboard: list[dict[str, Any]] = Field(default_factory=list)
    final_storyboard: list[dict[str, Any]] = Field(default_factory=list)
    prompt_audit: dict[str, Any] = Field(default_factory=dict)
    prompt_revision_count: int = 0
    model_attempts: list[ModelAttempt] = Field(default_factory=list)
    model_usage_summary: ModelUsageSummary = Field(default_factory=ModelUsageSummary)
    failure_records: list[FailureRecord] = Field(default_factory=list)
    last_failure: FailureRecord | None = None
    comfyui_prompt_ids: list[str] = Field(default_factory=list)
    comfyui_submissions: list[ComfyUISubmission] = Field(default_factory=list)
    comfyui_outputs: list[ComfyUIOutput] = Field(default_factory=list)
    comfyui_cancellations: list[ComfyUICancellation] = Field(default_factory=list)
    comfyui_diagnostics: dict[str, Any] = Field(default_factory=dict)
    grid_image_prompt: str = ""
    grid_image_asset: GridImageAsset | None = None
    grid_image_attempts: list[GridImageAttempt] = Field(default_factory=list)
    grid_image_checkpoint: Literal[
        "",
        "prompt_compiled",
        "image_acquired",
        "image_validated",
        "image_uploaded",
        "workflow_patched",
    ] = ""
    grid_image_replacements: list[dict[str, Any]] = Field(default_factory=list)
    artifact_dir: str = ""
    error: str = ""
    failed_stage: str = ""
    retry_count: int = 0
    parent_batch_id: str = ""
    queue_priority: int = 0
    last_completed_stage: str = ""
    resume_stage: str = ""
    cancel_requested: bool = False
    execution_attempt: int = 0
    lease_owner: str = ""
    lease_expires_at: str = ""
    lease_seconds: float = 300.0
    queued_at: str = ""
    started_at: str = ""
    finished_at: str = ""
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def add_log(self, stage: str, message: str, level: Literal["info", "warn", "error"] = "info") -> None:
        self.logs.append(RunLog(stage=stage, message=message, level=level))
        self.updated_at = datetime.now(timezone.utc).isoformat()

    def add_event(
        self,
        event_type: str,
        *,
        stage: str = "",
        message: str = "",
        data: dict[str, Any] | None = None,
    ) -> None:
        self.events.append(
            RunEvent(
                sequence=len(self.events) + 1,
                run_id=self.run_id,
                event_type=event_type,
                stage=stage,
                message=message,
                data=data or {},
            )
        )
        self.updated_at = datetime.now(timezone.utc).isoformat()


class BatchFailurePolicy(BaseModel):
    auto_retry_failed_items: int = Field(default=0, ge=0, le=5)
    pause_on_failure_count: int = Field(default=0, ge=0)
    pause_on_failure_rate: float = Field(default=0, ge=0, le=1)


class BatchRunRequest(BaseModel):
    idempotency_key: str = ""
    defaults: RunRequestDefaults = Field(default_factory=RunRequestDefaults)
    failure_policy: BatchFailurePolicy = Field(default_factory=BatchFailurePolicy)
    items: list[RunRequest] = Field(min_length=1)

    def resolved_items(self) -> list[RunRequest]:
        return [apply_run_defaults(self.defaults, item) for item in self.items]


class BatchExportRequest(BaseModel):
    export_root: str | None = None
    include_zip: bool = True


class BatchExportValidationRequest(BaseModel):
    export_dir: str
    save_report: bool = False


class BatchExportZipValidationRequest(BaseModel):
    zip_path: str
    expected_sha256: str = ""
    expected_size_bytes: int = 0
    save_report: bool = False


class BatchRecoveryExecuteRequest(BaseModel):
    dry_run: bool = False
    action_codes: list[str] | None = None


class BatchRunItem(BaseModel):
    index: int
    run_id: str
    idea: str
    status: str
    current_stage: str
    queue_priority: int = 0
    error: str = ""


class BatchRunState(BaseModel):
    batch_id: str
    idempotency_key: str = ""
    request_fingerprint: str = ""
    failure_policy: BatchFailurePolicy = Field(default_factory=BatchFailurePolicy)
    status: Literal[
        "queued",
        "paused",
        "running",
        "awaiting_approval",
        "completed",
        "partial_failed",
        "failed",
        "cancelled",
    ] = "queued"
    paused: bool = False
    items: list[BatchRunItem] = Field(default_factory=list)
    summary: dict[str, int] = Field(default_factory=dict)
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
