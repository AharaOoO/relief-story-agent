import json
import tomllib
from pathlib import Path


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
