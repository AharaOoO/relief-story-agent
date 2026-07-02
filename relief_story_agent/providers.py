from __future__ import annotations

import json
import os
import time
from typing import Any, Protocol

from openai import OpenAI

from .models import ModelCallResult, ModelUsage, StageModelConfig


class ModelProvider(Protocol):
    def generate_json(
        self,
        stage: str,
        prompt: str,
        config: StageModelConfig | None = None,
    ) -> dict[str, Any] | ModelCallResult:
        ...


class OpenAICompatibleProvider:
    """Provider for OpenAI-compatible chat completion endpoints."""

    def __init__(self, configs: dict[str, StageModelConfig] | None = None):
        self.configs = configs or {}

    def generate_json(
        self,
        stage: str,
        prompt: str,
        config: StageModelConfig | None = None,
    ) -> ModelCallResult:
        cfg = config or self.configs.get(stage)
        if not cfg or not cfg.model:
            raise ValueError(f"Missing model config for stage: {stage}")
        api_key = _resolve_api_key(cfg)
        client = OpenAI(
            base_url=cfg.base_url,
            api_key=api_key,
            max_retries=0,
        )
        response = client.chat.completions.create(
            model=cfg.model,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=cfg.temperature,
            timeout=cfg.timeout_seconds,
        )
        content = response.choices[0].message.content or ""
        usage = getattr(response, "usage", None)
        return ModelCallResult(
            payload=self._parse_json(content),
            model=str(getattr(response, "model", "") or cfg.model),
            request_id=str(getattr(response, "_request_id", "") or ""),
            usage=ModelUsage(
                prompt_tokens=int(getattr(usage, "prompt_tokens", 0) or 0),
                completion_tokens=int(getattr(usage, "completion_tokens", 0) or 0),
                total_tokens=int(getattr(usage, "total_tokens", 0) or 0),
            ),
        )

    @staticmethod
    def _parse_json(content: str) -> dict[str, Any]:
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            start = content.find("{")
            end = content.rfind("}")
            if start >= 0 and end > start:
                return json.loads(content[start : end + 1])
            raise


class FakeModelProvider:
    def __init__(self, responses: dict[str, dict[str, Any]]):
        self.responses = responses
        self.calls: list[str] = []

    def generate_json(self, stage: str, prompt: str, config: StageModelConfig | None = None) -> dict[str, Any]:
        self.calls.append(stage)
        if stage not in self.responses:
            raise KeyError(f"No fake response configured for {stage}")
        return self.responses[stage]

    @classmethod
    def minimal_success(cls) -> "FakeModelProvider":
        return cls(
            {
                "chief_screenwriter": {
                    "core_candidates": [
                        {
                            "title": "多放了一双筷子",
                            "core_type": "暖心善意内核",
                            "core_sentence": "有时候人不是需要被拯救，只是需要被看见。",
                            "pressure_point": "下班后疲惫",
                            "style": "现实",
                            "series": "便利店的夜晚",
                            "logline": "便利店店员多放一双筷子。",
                            "scores": {
                                "core_clarity": 9,
                                "low_stimulation": 9,
                                "empathy": 9,
                                "aftertaste": 8,
                                "visual_feasibility": 9,
                                "series_potential": 8,
                                "completion_hook": 8,
                            },
                        }
                    ],
                    "selected_core_index": 0,
                    "draft_script": {
                        "title": "多放了一双筷子",
                        "story_type": "都市现实",
                        "duration_seconds": 90,
                        "core_sentence": "有时候人不是需要被拯救，只是需要被看见。",
                        "characters": ["林澈", "店员"],
                        "setting": "雨后便利店",
                        "beats": [
                            {"name": "压力入口", "time_range": "0-10s", "content": "林澈走进便利店。"},
                            {"name": "轻微冲突", "time_range": "10-30s", "content": "他只想买冷便当。"},
                            {"name": "温柔异动", "time_range": "30-60s", "content": "店员多放一碗汤。"},
                            {"name": "情绪释放", "time_range": "60-80s", "content": "他坐下慢慢吃饭。"},
                            {"name": "余味结尾", "time_range": "80-90s", "content": "热气升起来。"},
                        ],
                        "closing_caption": "不是每一天都要硬撑到最后。",
                    },
                },
                "deepseek_polish": {
                    "polished_script": {
                        "title": "多放了一双筷子",
                        "story_type": "都市现实",
                        "duration_seconds": 90,
                        "core_sentence": "有时候人不是需要被拯救，只是需要被看见。",
                        "characters": ["林澈", "店员"],
                        "setting": "雨后便利店",
                        "beats": [
                            {"name": "压力入口", "time_range": "0-10s", "content": "雨水映着便利店灯光。"},
                            {"name": "轻微冲突", "time_range": "10-30s", "content": "林澈说不用加热。"},
                            {"name": "温柔异动", "time_range": "30-60s", "content": "店员说另一双给明天的你。"},
                            {"name": "情绪释放", "time_range": "60-80s", "content": "他没有马上回复消息。"},
                            {"name": "余味结尾", "time_range": "80-90s", "content": "便当热气停在镜头里。"},
                        ],
                        "closing_caption": "不是每一天都要硬撑到最后。",
                    }
                },
                "quality_gate": {
                    "passed": True,
                    "issues": [],
                    "revision_instructions": [],
                    "scores": {
                        "story_logic": 9,
                        "character_consistency": 9,
                        "emotional_coherence": 9,
                        "producibility": 9,
                        "timing": 9,
                    },
                },
                "gpt_prompt_writer": {
                    "shots": [
                        {
                            "shot_id": 1,
                            "time_range": "0-12s",
                            "description": "雨后便利店外景，林澈推门进入。",
                            "image_prompt": "都市现实风格，雨后便利店，温柔灯光，疲惫上班族",
                            "negative_prompt": "强争吵，恐怖，压迫，鸡汤标语",
                            "scores": {
                                "core_clarity": 8,
                                "low_stimulation": 9,
                                "empathy": 8,
                                "aftertaste": 8,
                                "visual_feasibility": 9,
                                "series_potential": 8,
                                "completion_hook": 8,
                            },
                            "comfyui_inputs": {
                                "positive": "都市现实风格，雨后便利店",
                                "negative": "强争吵，恐怖，压迫",
                                "seed": int(time.time()) % 100000,
                                "filename_prefix": "relief_store_001",
                            },
                        }
                    ]
                },
                "gpt_prompt_audit": {
                    "passed": True,
                    "issues": [],
                    "revision_instructions": [],
                    "scores": {
                        "spatial_logic": 8,
                        "axis_continuity": 8,
                        "motion_logic": 8,
                        "static_logic": 8,
                        "story_alignment": 8,
                        "prompt_conciseness": 8,
                    },
                },
            }
        )


def _resolve_api_key(config: StageModelConfig) -> str:
    if config.api_key:
        return config.api_key
    if config.api_key_env:
        value = os.environ.get(config.api_key_env)
        if not value:
            raise ValueError(
                f"Missing environment variable for model API key: {config.api_key_env}"
            )
        return value
    return "local"
