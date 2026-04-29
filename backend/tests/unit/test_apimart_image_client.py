import pytest
import json
import httpx

from app.infra.apimart_image_client import APIMartImageClient


@pytest.mark.asyncio
async def test_apimart_image_client_submits_and_polls_task():
    requests: list[httpx.Request] = []
    poll_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal poll_count
        requests.append(request)
        if request.method == "POST" and request.url.path == "/v1/images/generations":
            return httpx.Response(
                200,
                json={"data": [{"status": "submitted", "task_id": "task-1"}]},
            )
        if request.method == "GET" and request.url.path == "/v1/tasks/task-1":
            poll_count += 1
            if poll_count == 1:
                return httpx.Response(200, json={"data": {"status": "running"}})
            return httpx.Response(
                200,
                json={
                    "data": {
                        "status": "completed",
                        "result": {"images": [{"url": ["https://upload.apimart.ai/f/out.png"]}]},
                    }
                },
            )
        return httpx.Response(404)

    client = APIMartImageClient(
        api_key="sk-test",
        base_url="https://api.apimart.ai/v1",
        poll_interval_sec=0,
        timeout_sec=5,
        transport=httpx.MockTransport(handler),
    )

    response = await client.image_generations(
        "gpt-image-2",
        "角色全身设定图",
        references=["https://example.com/ref.png"],
        size="768x1344",
    )

    assert response == {
        "data": [
            {
                "url": "https://upload.apimart.ai/f/out.png",
                "task_id": "task-1",
                "status": "completed",
            }
        ]
    }
    assert len(requests) == 3
    assert poll_count == 2
    body = json.loads(requests[0].content.decode())
    assert body["model"] == "gpt-image-2"
    assert body["image"] == ["https://example.com/ref.png"]


@pytest.mark.asyncio
async def test_apimart_image_client_retries_transient_poll_connect_error():
    poll_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal poll_count
        if request.method == "POST" and request.url.path == "/v1/images/generations":
            return httpx.Response(
                200,
                json={"data": [{"status": "submitted", "task_id": "task-2"}]},
            )
        if request.method == "GET" and request.url.path == "/v1/tasks/task-2":
            poll_count += 1
            if poll_count == 1:
                return httpx.Response(200, json={"data": {"status": "running"}})
            if poll_count == 2:
                raise httpx.ConnectError("tls handshake failed", request=request)
            return httpx.Response(
                200,
                json={
                    "data": {
                        "status": "completed",
                        "result": {"images": [{"url": ["https://upload.apimart.ai/f/retry.png"]}]},
                    }
                },
            )
        return httpx.Response(404)

    client = APIMartImageClient(
        api_key="sk-test",
        base_url="https://api.apimart.ai",
        poll_interval_sec=0,
        timeout_sec=5,
        transport=httpx.MockTransport(handler),
    )

    response = await client.image_generations("gpt-image-2", "角色 360 旋转设定图")

    assert response["data"][0]["url"] == "https://upload.apimart.ai/f/retry.png"
    assert poll_count == 3
