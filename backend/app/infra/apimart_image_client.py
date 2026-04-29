import asyncio
import time
from typing import Any

import httpx

from app.config import get_settings
from app.infra.volcano_client import MockVolcanoClient
from app.infra.volcano_errors import VolcanoAuthError


def _normalize_base_url(value: str) -> str:
    base = (value or "https://api.apimart.ai").rstrip("/")
    if base.endswith("/v1"):
        base = base[:-3]
    return base


def _extract_direct_url(data: dict[str, Any]) -> str | None:
    rows = data.get("data")
    if not isinstance(rows, list) or not rows:
        return None
    first = rows[0]
    if not isinstance(first, dict):
        return None
    url = first.get("url")
    return url if isinstance(url, str) and url else None


def _extract_task_id(data: dict[str, Any]) -> str | None:
    rows = data.get("data")
    if not isinstance(rows, list) or not rows:
        return None
    first = rows[0]
    if not isinstance(first, dict):
        return None
    task_id = first.get("task_id")
    return task_id if isinstance(task_id, str) and task_id else None


def _extract_completed_image_url(task_data: dict[str, Any]) -> str:
    images = ((task_data.get("result") or {}).get("images") or [])
    for image in images:
        if not isinstance(image, dict):
            continue
        value = image.get("url")
        if isinstance(value, list) and value:
            return str(value[0])
        if isinstance(value, str) and value:
            return value
    raise RuntimeError(f"Completed APIMart task has no image URL: {task_data}")


class APIMartImageClient:
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        quality: str = "low",
        output_format: str = "png",
        poll_interval_sec: float = 5.0,
        timeout_sec: float = 300.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        if not api_key:
            raise VolcanoAuthError("APIMART_API_KEY 或 OPENAI_IMAGE_API_KEY 未配置")
        self._base_url = _normalize_base_url(base_url)
        self._api_key = api_key
        self._quality = quality
        self._output_format = output_format
        self._poll_interval_sec = poll_interval_sec
        self._timeout_sec = timeout_sec
        self._transport = transport

    async def image_generations(
        self,
        model: str,
        prompt: str,
        *,
        references: list[str] | None = None,
        n: int = 1,
        size: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "model": model,
            "prompt": prompt,
            "n": n,
            "quality": self._quality,
            "output_format": self._output_format,
            **kwargs,
        }
        if size:
            body["size"] = size
        if references:
            body["image"] = references

        async with httpx.AsyncClient(
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            timeout=self._timeout_sec,
            trust_env=False,
            transport=self._transport,
        ) as client:
            response = await client.post(f"{self._base_url}/v1/images/generations", json=body)
            response.raise_for_status()
            submitted = response.json()

            direct_url = _extract_direct_url(submitted)
            if direct_url:
                return {"data": [{"url": direct_url}]}

            task_id = _extract_task_id(submitted)
            if not task_id:
                raise RuntimeError(f"APIMart image generation response has no task_id: {submitted}")

            image_url = await self._poll_image_url(client, task_id)
            return {"data": [{"url": image_url, "task_id": task_id, "status": "completed"}]}

    async def _poll_image_url(self, client: httpx.AsyncClient, task_id: str) -> str:
        deadline = time.monotonic() + self._timeout_sec
        transient_errors = 0
        while True:
            try:
                response = await client.get(f"{self._base_url}/v1/tasks/{task_id}")
            except httpx.TransportError as exc:
                transient_errors += 1
                if transient_errors > 3 or time.monotonic() >= deadline:
                    raise RuntimeError(
                        f"APIMart image task polling failed after transient network errors: {type(exc).__name__}"
                    ) from exc
                await asyncio.sleep(self._poll_interval_sec)
                continue
            transient_errors = 0
            response.raise_for_status()
            task_data = response.json().get("data") or {}
            status = task_data.get("status")
            if status == "completed":
                return _extract_completed_image_url(task_data)
            if status in {"failed", "cancelled", "canceled"}:
                error = task_data.get("error") or {}
                message = error.get("message") if isinstance(error, dict) else None
                raise RuntimeError(message or f"APIMart image generation {status}")
            if time.monotonic() >= deadline:
                raise TimeoutError(f"APIMart image generation timed out: {task_id}")
            await asyncio.sleep(self._poll_interval_sec)


def get_character_image_client() -> Any:
    settings = get_settings()
    if settings.ai_provider_mode == "mock":
        return MockVolcanoClient()

    api_key = settings.apimart_api_key or settings.openai_image_api_key
    base_url = settings.openai_image_base_url or settings.apimart_base_url
    return APIMartImageClient(
        api_key=api_key,
        base_url=base_url,
        quality=settings.apimart_image_quality,
        output_format=settings.apimart_image_output_format,
        poll_interval_sec=settings.apimart_poll_interval_sec,
        timeout_sec=settings.apimart_poll_timeout_sec,
    )


def get_character_image_model() -> str:
    settings = get_settings()
    return settings.openai_image_model or settings.apimart_image_model
