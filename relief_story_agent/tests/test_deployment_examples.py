import json
import tomllib
from pathlib import Path

from relief_story_agent.model_config import ModelConfigRegistry
from relief_story_agent.models import BatchRunRequest, RunRequest
from relief_story_agent.smoke_comfyui import ComfyUISmokeRequest


PACKAGE_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = PACKAGE_DIR.parent
EXAMPLES_DIR = PACKAGE_DIR / "examples"


def test_deployment_json_examples_are_valid():
    for name in ("run_request.example.json", "batch_request.example.json"):
        payload = json.loads((EXAMPLES_DIR / name).read_text(encoding="utf-8"))
        assert isinstance(payload, dict)


def test_comfyui_connect_example_targets_local_address_box_flow():
    payload = json.loads((EXAMPLES_DIR / "comfyui_connect.example.json").read_text(encoding="utf-8"))

    assert payload["endpoint"] == "http://127.0.0.1:8188"
    assert payload["workflow_api_path"].endswith("ltx23_four_grid.json")
    assert payload["timeout_seconds"] == 5


def test_smoke_request_example_is_valid_and_safe_by_default():
    payload = json.loads((EXAMPLES_DIR / "smoke_request.example.json").read_text(encoding="utf-8"))
    request = ComfyUISmokeRequest.model_validate(payload)

    assert request.dry_run is True
    assert request.workflow_path.endswith(".json")
    assert request.comfyui_base_url == "http://127.0.0.1:8188"
    assert request.manual_grid_image_path
    assert request.output_root == "D:/relief_story_smoke"


def test_prompt_template_examples_contain_required_placeholders():
    writer = (EXAMPLES_DIR / "templates" / "prompt_writer.default.md").read_text(encoding="utf-8")
    audit = (EXAMPLES_DIR / "templates" / "prompt_audit.default.md").read_text(encoding="utf-8")

    assert "{{script_json}}" in writer
    assert "{{duration_seconds}}" in writer
    assert "{{preferred_style}}" in writer
    assert "{{workflow_context}}" in writer
    assert "{{script_json}}" in audit
    assert "{{storyboard_json}}" in audit
    assert "{{workflow_context}}" in audit


def test_full_ltx_run_examples_are_valid_json():
    model_config_path = EXAMPLES_DIR / "model_config.local.example.json"
    run_request_path = EXAMPLES_DIR / "run_request.full-ltx.example.json"

    registry = ModelConfigRegistry.from_file(model_config_path, environ={})
    run_request = RunRequest.model_validate(
        json.loads(run_request_path.read_text(encoding="utf-8"))
    )

    assert "gemini_writer" in registry.profiles
    assert registry.stages["chief_screenwriter"] == "gemini_writer"
    assert run_request.approval_mode == "auto"
    assert run_request.comfyui is not None
    assert run_request.comfyui.enabled is True
    assert run_request.comfyui.workflow_api_path.endswith("ltx23_four_grid.json")
    assert run_request.comfyui.grid_image.model == "gpt-image-2"
    assert run_request.template_paths.prompt_writer_template_path.endswith(".md")
    assert run_request.execution_policy.max_total_stage_executions >= 10
    assert run_request.execution_policy.max_stage_executions["gpt_prompt_audit"] == 2


def test_full_ltx_batch_example_has_multiple_items_and_failure_policy():
    payload = json.loads(
        (EXAMPLES_DIR / "batch_request.full-ltx.example.json").read_text(encoding="utf-8")
    )
    request = BatchRunRequest.model_validate(payload)

    assert request.idempotency_key
    assert len(request.items) >= 3
    assert request.failure_policy.auto_retry_failed_items == 1
    assert request.failure_policy.pause_on_failure_count >= 1
    assert request.defaults.approval_mode == "auto"
    assert request.defaults.comfyui is not None
    assert request.defaults.comfyui.grid_image.model == "gpt-image-2"
    assert request.defaults.execution_policy is not None
    assert request.defaults.execution_policy.max_total_stage_executions >= 10


def test_local_deployment_guides_cover_required_operator_workflows():
    local_deployment = (PROJECT_ROOT / "docs" / "LOCAL_DEPLOYMENT.md").read_text(encoding="utf-8")
    comfyui_guide = (PROJECT_ROOT / "docs" / "COMFYUI_LTX23_GUIDE.md").read_text(encoding="utf-8")
    template_guide = (PROJECT_ROOT / "docs" / "TEMPLATE_GUIDE.md").read_text(encoding="utf-8")

    for required in (
        "python -m pip install -e .",
        "GEMINI_API_KEY",
        "DEEPSEEK_API_KEY",
        "OPENAI_API_KEY",
        "relief-story-agent setup",
        "relief-story-agent diagnose",
        "relief-story-agent pipeline-schema",
        "smoke-comfyui --dry-run",
        "POST /api/batches",
        "export/validate",
        "acceptance",
        "relief-story-agent run",
        "relief-story-agent batch-plan",
        "relief-story-agent batch",
        "relief-story-agent export-batch",
        "relief-story-agent recovery-plan",
        "relief-story-agent recover-batch",
        "relief-story-agent run-status",
        "relief-story-agent runs",
        "relief-story-agent batch-status",
        "relief-story-agent batches",
        "relief-story-agent scheduler",
        "relief-story-agent run-events",
        "relief-story-agent run-artifacts",
        "relief-story-agent run-audit",
        "relief-story-agent batch-artifacts",
        "relief-story-agent batch-health",
        "relief-story-agent validate-export",
        "relief-story-agent validate-export-zip",
        "execution_policy",
        "fix_execution_policy",
        "127.0.0.1:8188/queue",
    ):
        assert required in local_deployment

    for required in (
        "LiteGraph",
        "API prompt JSON",
        "POST /api/comfyui/connect",
        "LoadImage",
        "four-grid",
        "out of VRAM",
        "does not generate nodes",
    ):
        assert required in comfyui_guide

    for required in (
        "{{script_json}}",
        "{{storyboard_json}}",
        "{{workflow_context}}",
        "gpt_prompt_reviser",
        "one revision",
        "relief-story-agent diagnose",
        "artifacts",
    ):
        assert required in template_guide


def test_start_server_example_uses_module_entrypoint():
    text = (EXAMPLES_DIR / "start_server.example.ps1").read_text(encoding="utf-8")
    assert "python -m relief_story_agent.server" in text
    assert "--state-dir" in text
    assert "--model-config" in text


def test_project_can_be_installed_with_console_script():
    pyproject = tomllib.loads((PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8"))

    assert pyproject["project"]["name"] == "relief-story-agent"
    assert pyproject["project"]["scripts"]["relief-story-agent"] == "relief_story_agent.cli:main"
    assert pyproject["project"]["scripts"]["relief-story-agent-server"] == "relief_story_agent.server:main"
    assert "relief_story_agent" in pyproject["tool"]["setuptools"]["packages"]
    package_data = pyproject["tool"]["setuptools"]["package-data"]["relief_story_agent"]
    assert "examples/*.bat" in package_data
    assert "examples/templates/*.md" in package_data


def test_source_checkout_has_portable_windows_launchers():
    root_bat = (PROJECT_ROOT / "start_relief_story_agent.bat").read_text(encoding="utf-8")
    example_bat = (EXAMPLES_DIR / "start_server.example.bat").read_text(encoding="utf-8")

    for text in (root_bat, example_bat):
        assert "%~dp0" in text
        assert "PYTHONPATH" in text
        assert "python -m relief_story_agent.server" in text
        assert "--state-dir" in text


def test_readme_documents_one_click_and_editable_startup_paths():
    text = (PACKAGE_DIR / "README.md").read_text(encoding="utf-8")

    assert "start_relief_story_agent.bat" in text
    assert 'python -m pip install -e "D:\\codex工作区"' in text
    assert "relief-story-agent serve --host 127.0.0.1 --port 8891" in text
    assert "smoke_request.example.json" in text
    assert "run_request.full-ltx.example.json" in text
    assert "batch_request.full-ltx.example.json" in text
    assert "examples/templates/prompt_writer.default.md" in text
    assert "docs/LOCAL_DEPLOYMENT.md" in text
    assert "docs/COMFYUI_LTX23_GUIDE.md" in text
    assert "docs/TEMPLATE_GUIDE.md" in text
    assert "relief-story-agent run" in text
    assert "relief-story-agent pipeline-schema" in text
    assert "relief-story-agent batch-plan" in text
    assert "relief-story-agent export-batch" in text
    assert "relief-story-agent recovery-plan" in text
    assert "relief-story-agent run-status" in text
    assert "relief-story-agent runs" in text
    assert "relief-story-agent batch-health" in text
    assert "relief-story-agent run-events" in text
    assert "relief-story-agent run-audit" in text
    assert "relief-story-agent scheduler" in text
    assert "relief-story-agent validate-export" in text
    assert "execution_policy" in text
    assert "fix_execution_policy" in text
    assert "127.0.0.1:8188/queue" in text


def test_handoff_docs_do_not_keep_obsolete_local_baseline():
    for path in (
        PROJECT_ROOT / "README.md",
        PROJECT_ROOT / "PROJECT_HANDOFF.md",
        PROJECT_ROOT / "NEXT_SESSION_PROMPT.md",
    ):
        text = path.read_text(encoding="utf-8")
        assert "229 passed" not in text
        assert "80da952 feat: add local ComfyUI smoke runner" not in text
