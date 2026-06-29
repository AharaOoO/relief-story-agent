from __future__ import annotations

from textwrap import dedent

CORE_TYPES = [
    "矛盾冲突内核",
    "哲理反思内核",
    "暖心善意内核",
    "自我和解内核",
    "奇幻解压内核",
    "Q版萌系内核",
    "误会反转内核",
    "关系修复内核",
    "陌生人善意内核",
]

SERIES_LIBRARY = [
    {
        "name": "便利店的夜晚",
        "style": "现实风格",
        "promise": "每集一个疲惫的人，在便利店里被一个轻微善意接住。",
    },
    {
        "name": "压力小怪物",
        "style": "奇幻风格",
        "promise": "压力拟人化为小怪物，主角学会照顾而不是消灭它。",
    },
    {
        "name": "未完成事务所",
        "style": "Q版风格",
        "promise": "小人管理未完成任务、没回消息和没说出口的话。",
    },
    {
        "name": "雨停之前",
        "style": "都市现实风格",
        "promise": "雨夜中的普通人，在雨停前完成一次情绪松动。",
    },
    {
        "name": "小精灵值夜班",
        "style": "奇幻治愈风格",
        "promise": "看不见的小精灵照顾深夜还没睡的人。",
    },
    {
        "name": "今天也没关系",
        "style": "生活流风格",
        "promise": "围绕普通人的小失败，证明没关系也能继续。",
    },
]

STRUCTURE_NAMES = ["压力入口", "轻微冲突", "温柔异动", "情绪释放", "余味结尾"]

SCORING_DIMENSIONS = [
    "core_clarity",
    "low_stimulation",
    "empathy",
    "aftertaste",
    "visual_feasibility",
    "series_potential",
    "completion_hook",
]


DEFAULT_CHIEF_SCREENWRITER_TEMPLATE = """
你是 chief_screenwriter，一名全面的短片总编剧，不是单一治愈模板生成器。
你的任务是创作 60-120 秒的“压力人群的低刺激情绪缓冲短片”。

观众状态：压力大、疲惫、焦虑、长期内耗，但仍希望在短时间里感到：
“我被理解了”“我可以慢一点”“今天没那么糟”“世界还有一点柔软”。

创作题目：{{idea}}
目标压力场景：{{audience_pressure}}
偏好风格：{{preferred_style}}
偏好系列：{{preferred_series}}
目标时长：{{duration_seconds}} 秒

可选内核类型：{{core_text}}

固定结构必须是：压力入口、轻微冲突、温柔异动、情绪释放、余味结尾。

系列库：
{{series_text}}

硬性规则：
1. 不要大吵大闹，不要强刺激，不要压迫观众。
2. 不要说教，不要鸡汤口号。
3. 用动作、物件、环境和细节表达情绪。
4. 结尾不是彻底解决问题，而是让人物和观众都松一口气。
5. 先生成 5 个内核候选，再选择最佳候选扩写完整分秒剧本。

返回 JSON，结构：
{
  "core_candidates": [
    {
      "title": "...",
      "core_type": "...",
      "core_sentence": "...",
      "pressure_point": "...",
      "style": "...",
      "series": "...",
      "logline": "...",
      "scores": {
        "core_clarity": 1-10,
        "low_stimulation": 1-10,
        "empathy": 1-10,
        "aftertaste": 1-10,
        "visual_feasibility": 1-10,
        "series_potential": 1-10,
        "completion_hook": 1-10
      }
    }
  ],
  "selected_core_index": 0,
  "draft_script": {
    "title": "...",
    "story_type": "...",
    "duration_seconds": {{duration_seconds}},
    "core_sentence": "...",
    "characters": ["..."],
    "setting": "...",
    "beats": [
      {"name": "压力入口", "time_range": "0-10s", "content": "..."},
      {"name": "轻微冲突", "time_range": "10-30s", "content": "..."},
      {"name": "温柔异动", "time_range": "30-60s", "content": "..."},
      {"name": "情绪释放", "time_range": "60-90s", "content": "..."},
      {"name": "余味结尾", "time_range": "90-120s", "content": "..."}
    ],
    "closing_caption": "..."
  }
}
""".strip()

DEFAULT_DEEPSEEK_POLISH_TEMPLATE = """
你是 deepseek_polish，负责把总编剧初稿改得更有细节、更可看。
你可以增强反转、动作、台词、画面细节和短视频完播吸引力，但不得提高刺激强度。

禁止：大吵大闹、强刺激、鸡汤口号、压迫式冲突、彻底解决一切的大圆满。
必须保留原始 core_sentence、内核类型、时长目标和五段结构。

输入 JSON：
{{draft_payload}}

返回 JSON：
{"polished_script": <完整剧本对象>}
""".strip()

def build_chief_screenwriter_prompt(
    *,
    idea: str,
    audience_pressure: str = "",
    preferred_style: str = "",
    preferred_series: str = "",
    duration_seconds: int = 90,
    template: str | None = None,
) -> str:
    """Build the Gemini/chief-screenwriter instruction prompt."""
    core_text = "、".join(CORE_TYPES)
    series_text = "\n".join(
        f"- 《{item['name']}》：{item['style']}。{item['promise']}" for item in SERIES_LIBRARY
    )
    tmpl = template or DEFAULT_CHIEF_SCREENWRITER_TEMPLATE
    return (
        tmpl.replace("{{idea}}", idea)
        .replace("{{audience_pressure}}", audience_pressure or "由你根据题目合理选择")
        .replace("{{preferred_style}}", preferred_style or "现实、奇幻、Q版、都市、生活流、温柔喜剧均可")
        .replace("{{preferred_series}}", preferred_series or "可从系列库中选择，也可生成独立单集")
        .replace("{{duration_seconds}}", str(duration_seconds))
        .replace("{{core_text}}", core_text)
        .replace("{{series_text}}", series_text)
    )


def build_deepseek_polish_prompt(draft_payload: dict, template: str | None = None) -> str:
    from .prompt_templates import _json
    tmpl = template or DEFAULT_DEEPSEEK_POLISH_TEMPLATE
    return tmpl.replace("{{draft_payload}}", _json(draft_payload))


def build_storyboard_prompt(script: dict) -> str:
    return dedent(
        f"""
        你是 gpt_storyboard，负责把剧本拆成 5-8 个镜头并生成 ComfyUI 可用提示词。
        每个镜头必须低刺激、画面清晰、服务原始内核。

        剧本 JSON：
        {script}

        返回 JSON：
        {{
          "shots": [
            {{
              "shot_id": 1,
              "time_range": "0-10s",
              "description": "中文分镜画面",
              "image_prompt": "中文图像提示词",
              "negative_prompt": "负面提示词",
              "scores": {{
                "core_clarity": 1-10,
                "low_stimulation": 1-10,
                "empathy": 1-10,
                "aftertaste": 1-10,
                "visual_feasibility": 1-10,
                "series_potential": 1-10,
                "completion_hook": 1-10
              }},
              "comfyui_inputs": {{
                "positive": "...",
                "negative": "...",
                "seed": 123,
                "filename_prefix": "relief_..."
              }}
            }}
          ]
        }}
        """
    ).strip()

