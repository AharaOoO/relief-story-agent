from __future__ import annotations

import base64
import os
from typing import Callable

from openai import OpenAI

from .grid_image import GeneratedImage
from .models import GridImageConfig


class OpenAICompatibleGridImageProvider:
    def __init__(self, client_factory: Callable[[GridImageConfig], object] | None = None):
        self.client_factory = client_factory or self._build_client

    def generate(self, *, prompt: str, config: GridImageConfig) -> GeneratedImage:
        client = self.client_factory(config)
        response = client.images.generate(
            model=config.model,
            prompt=prompt,
            size=config.size,
            quality=config.quality,
            output_format=config.output_format,
            n=1,
        )
        data = list(getattr(response, "data", None) or [])
        if not data or not getattr(data[0], "b64_json", None):
            raise ValueError("image provider returned no image data")
        content = base64.b64decode(data[0].b64_json, validate=True)
        return GeneratedImage(
            content=content,
            mime_type={
                "png": "image/png",
                "jpeg": "image/jpeg",
                "webp": "image/webp",
            }[config.output_format],
            provider=config.provider,
            model=config.model,
        )

    @staticmethod
    def _build_client(config: GridImageConfig) -> OpenAI:
        api_key = config.api_key or os.environ.get(config.api_key_env, "")
        if not api_key:
            raise ValueError(
                f"Missing environment variable for image API key: {config.api_key_env}"
            )
        return OpenAI(
            base_url=config.base_url,
            api_key=api_key,
            max_retries=0,
            timeout=config.timeout_seconds,
        )
