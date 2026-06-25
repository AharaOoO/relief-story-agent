import base64

from relief_story_agent.image_providers import OpenAICompatibleGridImageProvider
from relief_story_agent.models import GridImageConfig


class FakeImages:
    def __init__(self, payload):
        self.payload = payload
        self.kwargs = None

    def generate(self, **kwargs):
        self.kwargs = kwargs
        return self.payload


class FakeClient:
    def __init__(self, payload):
        self.images = FakeImages(payload)


class ImageItem:
    def __init__(self, content):
        self.b64_json = base64.b64encode(content).decode("ascii")


class ImageResponse:
    def __init__(self, content):
        self.data = [ImageItem(content)]
        self.output_format = "png"


def test_provider_uses_current_gpt_image_parameters():
    client = FakeClient(ImageResponse(b"png-bytes"))
    provider = OpenAICompatibleGridImageProvider(client_factory=lambda config: client)
    config = GridImageConfig(
        model="gpt-image-2",
        size="1024x1024",
        quality="medium",
        output_format="png",
    )

    generated = provider.generate(prompt="four frames", config=config)

    assert generated.content == b"png-bytes"
    assert generated.mime_type == "image/png"
    assert client.images.kwargs == {
        "model": "gpt-image-2",
        "prompt": "four frames",
        "size": "1024x1024",
        "quality": "medium",
        "output_format": "png",
        "n": 1,
    }


def test_provider_rejects_empty_image_response():
    client = FakeClient(type("Response", (), {"data": []})())
    provider = OpenAICompatibleGridImageProvider(client_factory=lambda config: client)

    try:
        provider.generate(prompt="four frames", config=GridImageConfig())
    except ValueError as exc:
        assert "no image data" in str(exc)
    else:
        raise AssertionError("expected ValueError")
