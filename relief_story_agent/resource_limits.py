from contextlib import contextmanager
from threading import BoundedSemaphore


class ExecutionResourceLimits:
    def __init__(
        self,
        *,
        image_generation_concurrency: int = 2,
        comfyui_submission_concurrency: int = 1,
    ):
        if image_generation_concurrency < 1 or comfyui_submission_concurrency < 1:
            raise ValueError("resource concurrency limits must be at least 1")
        self.image_generation_concurrency = image_generation_concurrency
        self.comfyui_submission_concurrency = comfyui_submission_concurrency
        self._image = BoundedSemaphore(image_generation_concurrency)
        self._comfyui = BoundedSemaphore(comfyui_submission_concurrency)

    @contextmanager
    def image_generation(self):
        with self._image:
            yield

    @contextmanager
    def comfyui_submission(self):
        with self._comfyui:
            yield

    def status(self) -> dict[str, int]:
        return {
            "image_generation_concurrency": self.image_generation_concurrency,
            "comfyui_submission_concurrency": self.comfyui_submission_concurrency,
        }
