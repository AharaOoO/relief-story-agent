from __future__ import annotations

import json

from relief_story_agent import cli
from relief_story_agent.models import RunRequest, TemplatePaths
from relief_story_agent.prompt_templates import (
    build_prompt_audit_prompt,
    build_prompt_reviser_prompt,
    build_prompt_writer_prompt,
    validate_prompt_template_file,
)
import pytest


def test_prompt_writer_uses_default_template_with_concise_runninghub_g2_guidance():
    prompt = build_prompt_writer_prompt(
        request=RunRequest(idea="rainy store", preferred_style="realistic"),
        script={"title": "rainy store", "duration_seconds": 90},
        workflow_context="LTX node 202",
    )

    assert "gpt_prompt_writer" in prompt
    assert "RunningHub G2" in prompt
    assert "GPT image2" not in prompt
    assert "60-120" in prompt
    assert "{{script_json}}" not in prompt


def test_prompt_writer_uses_user_md_template_when_path_is_configured(tmp_path):
    template_path = tmp_path / "writer.md"
    template_path.write_text(
        "CUSTOM WRITER\nscript={{script_json}}\nstyle={{preferred_style}}\nworkflow={{workflow_context}}",
        encoding="utf-8",
    )
    request = RunRequest(
        idea="custom",
        preferred_style="Q版",
        template_paths=TemplatePaths(prompt_writer_template_path=str(template_path)),
    )

    prompt = build_prompt_writer_prompt(
        request=request,
        script={"title": "custom script"},
        workflow_context="workflow ok",
    )

    assert prompt.startswith("CUSTOM WRITER")
    assert '"title": "custom script"' in prompt
    assert "style=Q版" in prompt
    assert "workflow=workflow ok" in prompt


def test_audit_and_reviser_templates_render_storyboard_and_audit_context(tmp_path):
    audit_template = tmp_path / "audit.md"
    audit_template.write_text(
        "CUSTOM AUDIT\nworkflow={{workflow_context}}\nstory={{storyboard_json}}\nscript={{script_json}}",
        encoding="utf-8",
    )
    request = RunRequest(
        idea="audit",
        template_paths=TemplatePaths(prompt_audit_template_path=str(audit_template)),
    )

    audit_prompt = build_prompt_audit_prompt(
        request=request,
        script={"title": "script"},
        storyboard=[{"shot_id": 1, "image_prompt": "short"}],
        workflow_context="workflow ok",
    )
    reviser_prompt = build_prompt_reviser_prompt(
        request=request,
        script={"title": "script"},
        storyboard=[{"shot_id": 1, "image_prompt": "short"}],
        audit={"passed": False, "revision_instructions": ["fix axis"]},
        workflow_context="workflow ok",
    )

    assert audit_prompt.startswith("CUSTOM AUDIT")
    assert "workflow=workflow ok" in audit_prompt
    assert '"image_prompt": "short"' in audit_prompt
    assert "gpt_prompt_reviser" in reviser_prompt
    assert "fix axis" in reviser_prompt
    assert "workflow ok" in reviser_prompt


def test_user_writer_template_must_include_script_placeholder(tmp_path):
    template_path = tmp_path / "writer.md"
    template_path.write_text("CUSTOM WRITER without script", encoding="utf-8")
    request = RunRequest(
        idea="custom",
        template_paths=TemplatePaths(prompt_writer_template_path=str(template_path)),
    )

    with pytest.raises(ValueError, match="script_json"):
        build_prompt_writer_prompt(request=request, script={"title": "script"})


def test_validate_prompt_template_file_reports_placeholders_and_fingerprint(tmp_path):
    writer = tmp_path / "writer.md"
    writer.write_text("SCRIPT {{script_json}}\nSTYLE {{preferred_style}}", encoding="utf-8")

    result = validate_prompt_template_file(writer, "writer")

    assert result["status"] == "pass"
    assert result["kind"] == "writer"
    assert result["missing_required_placeholders"] == []
    assert result["unsupported_placeholders"] == []
    assert result["optional_placeholders_present"] == ["preferred_style"]
    assert len(result["sha256"]) == 64


def test_validate_prompt_template_file_rejects_missing_and_unsupported_placeholders(tmp_path):
    audit = tmp_path / "audit.md"
    audit.write_text("SCRIPT {{script_json}}\nBAD {{shots_json}}", encoding="utf-8")

    result = validate_prompt_template_file(audit, "audit")

    assert result["status"] == "fail"
    assert result["missing_required_placeholders"] == ["storyboard_json"]
    assert result["unsupported_placeholders"] == ["shots_json"]


def test_cli_template_check_reports_template_readiness(tmp_path, capsys):
    writer = tmp_path / "writer.md"
    audit = tmp_path / "audit.md"
    writer.write_text("SCRIPT {{script_json}}\nSTYLE {{preferred_style}}", encoding="utf-8")
    audit.write_text("SCRIPT {{script_json}}\nSTORY {{storyboard_json}}", encoding="utf-8")

    exit_code = cli.main(
        [
            "template-check",
            "--writer-template",
            str(writer),
            "--audit-template",
            str(audit),
            "--pretty",
        ]
    )

    assert exit_code == 0
    output = json.loads(capsys.readouterr().out)
    assert output["ready"] is True
    assert [check["kind"] for check in output["checks"]] == ["writer", "audit"]
    assert output["checks"][0]["status"] == "pass"
