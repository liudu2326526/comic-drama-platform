import json

import httpx
import pytest

from app.config import get_settings
from app.infra.volcano_client import RealVolcanoClient


@pytest.fixture
def patched_settings(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "ark_api_key", "test-key", raising=False)
    monkeypatch.setattr(settings, "ark_base_url", "https://ark.test", raising=False)
    monkeypatch.setattr(settings, "ai_retry_max", 1, raising=False)
    monkeypatch.setattr(settings, "ai_retry_base_sec", 0.01, raising=False)
    return settings


@pytest.mark.asyncio
async def test_video_task_create_uses_raw_prompt_and_reference_images(patched_settings, respx_mock):
    route = respx_mock.post(url__regex=r".*/contents/generations/tasks").mock(
        return_value=httpx.Response(200, json={"id": "cgt-test"})
    )
    client = RealVolcanoClient()

    await client.video_generations_create(
        model="doubao-seedance-2-0-fast-test",
        prompt="原样提示词",
        references=["https://example.com/1.png", "https://example.com/2.png"],
        duration=5,
        resolution="720p",
        ratio="9:16",
    )

    body = json.loads(route.calls[0].request.content.decode("utf-8"))
    assert body["content"][0] == {"type": "text", "text": "原样提示词"}
    assert body["content"][1]["role"] == "reference_image"
    assert body["content"][2]["role"] == "reference_image"
    assert body["duration"] == 5
    assert body["resolution"] == "720p"
    assert body["ratio"] == "9:16"


@pytest.mark.asyncio
async def test_video_task_create_accepts_first_and_last_frame_inputs(patched_settings, respx_mock):
    route = respx_mock.post(url__regex=r".*/contents/generations/tasks").mock(
        return_value=httpx.Response(200, json={"id": "cgt-test"})
    )
    client = RealVolcanoClient()

    await client.video_generations_create(
        model="doubao-seedance-2-0-test",
        prompt="通用人物参考视频提示词",
        image_inputs=[
            {"role": "first_frame", "url": "https://example.com/full.png"},
            {"role": "last_frame", "url": "https://example.com/head.png"},
        ],
        duration=8,
        resolution="720p",
        ratio="9:16",
        generate_audio=True,
    )

    body = json.loads(route.calls[0].request.content.decode("utf-8"))
    assert body["content"][1] == {
        "type": "image_url",
        "role": "first_frame",
        "image_url": {"url": "https://example.com/full.png"},
    }
    assert body["content"][2] == {
        "type": "image_url",
        "role": "last_frame",
        "image_url": {"url": "https://example.com/head.png"},
    }
    assert body["generate_audio"] is True


def test_real_volcano_client_uses_configured_timeout(patched_settings, monkeypatch):
    assert hasattr(patched_settings, "ai_request_timeout_sec")
    monkeypatch.setattr(patched_settings, "ai_request_timeout_sec", 123.0, raising=False)

    client = RealVolcanoClient()

    assert client._client.timeout.read == 123.0
