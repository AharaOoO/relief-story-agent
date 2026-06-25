from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .models import RunRequest


DEFAULT_PROMPT_WRITER_TEMPLATE = """
你是 gpt_prompt_writer，负责把 DeepSeek 改好的短片剧本转成可用于 GPT image2 四宫格关键帧和 ComfyUI/LTX 的分镜提示词。

要求：
1. 生成 5-8 个镜头，每个镜头都必须服务剧情内核，不写无意义空镜。
2. 每个 image_prompt 面向 GPT image2 四宫格关键帧，控制在 60-120 个中文字符左右，不写长篇小说段落。
3. 画面要交代角色、站位、空间关系、动作、光线和情绪，但保持低刺激。
4. negative_prompt 简洁列出不要的内容，如争吵、恐怖、字幕、水印、角色错位、越轴。
5. comfyui_inputs 至少包含 positive、negative、seed、strength。

剧本 JSON：
{{script_json}}

目标时长：{{duration_seconds}} 秒
偏好风格：{{preferred_style}}
工作流上下文：
{{workflow_context}}

返回 JSON：
{
  "shots": [
    {
      "shot_id": 1,
      "time_range": "0-10s",
      "description": "中文分镜画面",
      "image_prompt": "60-120 个中文字符左右的四宫格关键帧提示词",
      "negative_prompt": "负面提示词",
      "scores": {
        "core_clarity": 1,
        "low_stimulation": 1,
        "empathy": 1,
        "aftertaste": 1,
        "visual_feasibility": 1,
        "series_potential": 1,
        "completion_hook": 1
      },
      "comfyui_inputs": {
        "positive": "...",
        "negative": "...",
        "seed": 123,
        "strength": 0.72,
        "filename_prefix": "relief_..."
      }
    }
  ]
}
""".strip()


DEFAULT_PROMPT_AUDIT_TEMPLATE = """
你是 gpt_prompt_audit，负责检查第 4 步生成的分镜提示词是否存在漏洞。

重点检查：
1. 角色是否存在位置错乱、左右关系漂移、人物数量变化。
2. 空间关系是否清楚，站位是否能连续。
3. 镜头设计是否越轴，前后镜头方向是否互相打架。
4. 动态画面逻辑是否合理，动作是否能从上一个镜头自然接到下一个镜头。
5. 静态画面逻辑是否符合剧情文意，物件、光线、情绪是否一致。
6. 每个镜头是否都有叙事含义，是否服务短片内核。
7. GPT image2 四宫格 image_prompt 是否过长，是否有无关铺陈。

剧本 JSON：
{{script_json}}

分镜提示词 JSON：
{{storyboard_json}}

Workflow context:
{{workflow_context}}

返回 JSON：
{
  "passed": true,
  "issues": [
    {"code": "spatial_confusion", "message": "...", "shot_id": 1}
  ],
  "revision_instructions": ["..."],
  "scores": {
    "spatial_logic": 1,
    "axis_continuity": 1,
    "motion_logic": 1,
    "static_logic": 1,
    "story_alignment": 1,
    "prompt_conciseness": 1
  }
}
""".strip()


DEFAULT_PROMPT_REVISER_TEMPLATE = """
你是 gpt_prompt_reviser，负责根据漏洞检查意见修正第 4 步的分镜提示词。

修正原则：
1. 只修正镜头描述、image_prompt、negative_prompt 和 comfyui_inputs，不改剧本内核。
2. 固定角色站位、空间关系和镜头方向，解决越轴、错位和动作不连续问题。
3. 每个 image_prompt 仍然面向 GPT image2 四宫格关键帧，控制在 60-120 个中文字符左右。
4. 输出完整 shots 数组，不要只输出修改片段。

剧本 JSON：
{{script_json}}

原分镜提示词 JSON：
{{storyboard_json}}

漏洞检查 JSON：
{{audit_json}}

Workflow context:
{{workflow_context}}

返回 JSON：
{"shots": [<修正后的完整镜头数组>]}
""".strip()


def build_prompt_writer_prompt(
    *,
    request: RunRequest,
    script: dict[str, Any],
    workflow_context: str = "",
) -> str:
    template = _load_template(
        request.template_paths.prompt_writer_template_path,
        DEFAULT_PROMPT_WRITER_TEMPLATE,
    )
    return _render_template(
        template,
        {
            "script_json": _json(script),
            "storyboard_json": "",
            "audit_json": "",
            "duration_seconds": str(script.get("duration_seconds") or request.duration_seconds),
            "preferred_style": request.preferred_style or "由模型根据剧本选择",
            "workflow_context": workflow_context or "未配置 ComfyUI workflow",
        },
        required_placeholders=("script_json",),
    )


def build_prompt_audit_prompt(
    *,
    request: RunRequest,
    script: dict[str, Any],
    storyboard: list[dict[str, Any]],
    workflow_context: str = "",
) -> str:
    template = _load_template(
        request.template_paths.prompt_audit_template_path,
        DEFAULT_PROMPT_AUDIT_TEMPLATE,
    )
    return _render_template(
        template,
        {
            "script_json": _json(script),
            "storyboard_json": _json(storyboard),
            "audit_json": "",
            "duration_seconds": str(script.get("duration_seconds") or request.duration_seconds),
            "preferred_style": request.preferred_style or "由模型根据剧本选择",
            "workflow_context": workflow_context or "鏈厤缃?ComfyUI workflow",
        },
        required_placeholders=("script_json", "storyboard_json"),
    )


def build_prompt_reviser_prompt(
    *,
    request: RunRequest,
    script: dict[str, Any],
    storyboard: list[dict[str, Any]],
    audit: dict[str, Any],
    workflow_context: str = "",
) -> str:
    return _render_template(
        DEFAULT_PROMPT_REVISER_TEMPLATE,
        {
            "script_json": _json(script),
            "storyboard_json": _json(storyboard),
            "audit_json": _json(audit),
            "duration_seconds": str(script.get("duration_seconds") or request.duration_seconds),
            "preferred_style": request.preferred_style or "由模型根据剧本选择",
            "workflow_context": workflow_context or "鏈厤缃?ComfyUI workflow",
        },
        required_placeholders=("script_json", "storyboard_json", "audit_json"),
    )


def _load_template(path: str | None, default_template: str) -> str:
    if not path:
        return default_template
    template_path = Path(path)
    if not template_path.exists():
        raise FileNotFoundError(f"Template file not found: {path}")
    return template_path.read_text(encoding="utf-8")


def _render_template(
    template: str,
    values: dict[str, str],
    *,
    required_placeholders: tuple[str, ...],
) -> str:
    missing = [key for key in required_placeholders if "{{" + key + "}}" not in template]
    if missing:
        raise ValueError(f"Template missing required placeholder(s): {', '.join(missing)}")
    rendered = template
    for key, value in values.items():
        rendered = rendered.replace("{{" + key + "}}", value)
    unresolved = sorted(set(re.findall(r"{{\s*([^{}]+?)\s*}}", rendered)))
    if unresolved:
        raise ValueError(f"Unsupported template placeholder(s): {', '.join(unresolved)}")
    return rendered


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2)
