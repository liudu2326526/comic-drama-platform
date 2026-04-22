import asyncio
import pytest
import respx
import httpx

from app.infra.volcano_client import RealVolcanoClient
from app.infra.volcano_errors import (
    VolcanoRateLimitError, VolcanoAuthError, VolcanoServerError,
)


@pytest.fixture
def patched_settings(monkeypatch):
    monkeypatch.setenv("ARK_API_KEY", "sk-test")
    monkeypatch.setenv("AI_RETRY_BASE_SEC", "0")   # 测试不真等
    monkeypatch.setenv("AI_PROVIDER_MODE", "real")
    # 禁用代理，避免 respx 匹配失效
    monkeypatch.setenv("http_proxy", "")
    monkeypatch.setenv("https_proxy", "")
    monkeypatch.setenv("all_proxy", "")
    monkeypatch.setenv("HTTP_PROXY", "")
    monkeypatch.setenv("HTTPS_PROXY", "")
    monkeypatch.setenv("ALL_PROXY", "")
    from app.config import get_settings
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_respx_basic(respx_mock):
    respx_mock.post(url__regex=r"https://test\.com/?").mock(return_value=httpx.Response(200))
    async with httpx.AsyncClient(trust_env=False) as client:
        resp = await client.post("https://test.com")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_chat_success(patched_settings, respx_mock):
    # 使用 regex 确保匹配，即便 base_url 后面有斜杠
    respx_mock.post(url__regex=r".*/chat/completions").mock(
        return_value=httpx.Response(200, json={
            "choices": [{"finish_reason": "stop",
                         "message": {"role": "assistant", "content": "hi"}}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        })
    )
    c = RealVolcanoClient()
    resp = await c.chat_completions("doubao-1.5-pro-32k",
                                    [{"role": "user", "content": "hi"}])
    assert resp.choices[0].message.content == "hi"


@pytest.mark.asyncio
async def test_image_success(patched_settings, respx_mock):
    respx_mock.post(url__regex=r".*/images/generations").mock(
        return_value=httpx.Response(200, json={
            "data": [{"url": "https://xxx/1.png", "size": "1152x864"}],
            "usage": {"generated_images": 1},
        })
    )
    c = RealVolcanoClient()
    resp = await c.image_generations("doubao-seedream-5.0-lite", "cat")
    assert resp["data"][0]["url"].startswith("https://")


@pytest.mark.asyncio
async def test_rate_limit_honors_retry_after(patched_settings, respx_mock):
    route = respx_mock.post(url__regex=r".*/chat/completions")
    route.side_effect = [
        httpx.Response(429, headers={"Retry-After": "0"}, json={"error": {"code": "RateLimitExceeded"}}),
        httpx.Response(200, json={
            "choices": [{"finish_reason": "stop",
                         "message": {"role": "assistant", "content": "ok"}}],
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        }),
    ]
    c = RealVolcanoClient()
    resp = await c.chat_completions("doubao-1.5-pro-32k",
                                    [{"role": "user", "content": "hi"}])
    assert resp.choices[0].message.content == "ok"
    assert route.call_count == 2


@pytest.mark.asyncio
async def test_auth_not_retried(patched_settings, respx_mock):
    route = respx_mock.post(url__regex=r".*/chat/completions").mock(
        return_value=httpx.Response(401, json={"error": {"code": "InvalidApiKey"}}))
    c = RealVolcanoClient()
    with pytest.raises(VolcanoAuthError):
        await c.chat_completions("x", [{"role": "user", "content": "x"}])
    assert route.call_count == 1   # 只打一次
