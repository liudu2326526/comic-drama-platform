import asyncio
import json
import logging
from abc import ABC, abstractmethod
from typing import Any

import httpx

from app.config import get_settings
from app.infra.volcano_errors import (
    VolcanoAuthError,
    VolcanoError,
    VolcanoRateLimitError,
    VolcanoServerError,
    VolcanoTimeoutError,
    classify_http,
    classify_exception,
)

logger = logging.getLogger(__name__)


class VolcanoClient(ABC):
    @abstractmethod
    async def chat_completions(self, model: str, messages: list[dict], **kwargs) -> Any:
        pass

    @abstractmethod
    async def image_generations(
        self,
        model: str,
        prompt: str,
        *,
        references: list[str] | None = None,
        n: int = 1,
        size: str | None = None,
        **kwargs: Any,
    ) -> Any:
        pass

    @abstractmethod
    async def video_generations_create(self, **kwargs: Any) -> Any:
        pass

    @abstractmethod
    async def video_generations_get(self, task_id: str) -> Any:
        pass


class _ChatResponse:
    """兼容 mock 和 openai SDK 的响应结构。"""

    class Choice:
        class Message:
            def __init__(self, content: str):
                self.content = content
                self.role = "assistant"

        def __init__(self, content: str, finish_reason: str):
            self.message = self.Message(content)
            self.finish_reason = finish_reason

    def __init__(self, content: str, finish_reason: str = "stop"):
        self.choices = [self.Choice(content, finish_reason)]

    @classmethod
    def from_dict(cls, data: dict) -> "_ChatResponse":
        choice = data.get("choices", [{}])[0]
        msg = choice.get("message", {})
        return cls(
            content=msg.get("content", ""),
            finish_reason=choice.get("finish_reason", "stop"),
        )


class MockVolcanoClient(VolcanoClient):
    """
    M2 使用的 Mock 客户端。不真正调 API,按 M2 任务需求返回固定格式的假数据。
    """

    async def chat_completions(self, model: str, messages: list[dict], **kwargs) -> Any:
        user_msg = next(
            (m["content"] for m in reversed(messages) if m["role"] == "user"), ""
        )
        logger.info(f"Mock Volcano Chat: model={model}, user_msg={user_msg[:50]}")

        # 1. 小说解析任务 (parse_novel)
        if "解析" in user_msg and "JSON" in user_msg:
            content = {
                "summary": "这是一个关于勇气的虚构故事。",
                "parsed_stats": ["角色: 3", "场景: 2", "预计时长: 60s"],
                "overview": "故事发生在遥远的未来,人类与 AI 共存...",
                "suggested_shots": 12,
            }
            resp_str = json.dumps(content)
            print(f"\n[AI Chat Output] Model: {model}\nContent: {resp_str}\n")
            return _ChatResponse(resp_str)

        # 1.5 角色提取任务 (gen_character_asset)
        if "角色" in user_msg and "提取" in user_msg:
            content = {
                "characters": [
                    {
                        "name": "秦昭",
                        "role_type": "protagonist",
                        "summary": "少年天子",
                        "description": "心怀大志的少年皇帝。"
                    },
                    {
                        "name": "江离",
                        "role_type": "supporting",
                        "summary": "摄政王",
                        "description": "权倾朝野的摄政王。"
                    }
                ]
            }
            resp_str = json.dumps(content)
            print(f"\n[AI Chat Output] Model: {model}\nContent: {resp_str}\n")
            return _ChatResponse(resp_str)

        # 1.6 场景提取任务 (gen_scene_asset)
        if "场景" in user_msg and "提取" in user_msg:
            content = {
                "scenes": [
                    {
                        "name": "长安殿",
                        "theme": "palace",
                        "summary": "金碧辉煌的大殿",
                        "description": "权力交锋的中心。"
                    },
                    {
                        "name": "御花园",
                        "theme": "palace",
                        "summary": "幽静的花园",
                        "description": "偶遇与密谈之所。"
                    }
                ]
            }
            resp_str = json.dumps(content)
            print(f"\n[AI Chat Output] Model: {model}\nContent: {resp_str}\n")
            return _ChatResponse(resp_str)

        # 2. 分镜生成任务 (gen_storyboard)
        elif "分镜" in user_msg:
            storyboards = []
            for i in range(1, 11):  # 固定返回 10 条
                storyboards.append(
                    {
                        "idx": i,
                        "title": f"分镜 {i}",
                        "description": f"这是第 {i} 个镜头的详细描述内容。",
                        "detail": f"镜头 {i} 的视觉细节提示词",
                        "duration_sec": 5.0,
                    }
                )
            resp_str = json.dumps(storyboards)
            print(f"\n[AI Chat Output] Model: {model}\nContent: {resp_str}\n")
            return _ChatResponse(resp_str)

    async def image_generations(
        self,
        model: str,
        prompt: str,
        *,
        references: list[str] | None = None,
        n: int = 1,
        size: str | None = None,
        **kwargs: Any,
    ) -> Any:
        logger.info(f"Mock Volcano Image: model={model}, prompt={prompt[:50]}, refs={len(references or [])}")
        img_url = "https://placehold.co/1024x1024?text=Mock+Image"
        print(f"\n[AI Image Output] Model: {model}\nURL: {img_url}\n")
        return {"data": [{"url": img_url}]}

    async def video_generations_create(self, **kwargs: Any) -> Any:
        logger.info("Mock Volcano Video Create")
        return {"id": "mock-video-task"}

    async def video_generations_get(self, task_id: str) -> Any:
        logger.info("Mock Volcano Video Get")
        return {
            "id": task_id,
            "status": "succeeded",
            "content": {
                "video_url": "https://placehold.co/720x1280.mp4",
                "last_frame_url": "https://placehold.co/720x1280.png?text=Mock+Last+Frame",
            },
        }


class RealVolcanoClient(VolcanoClient):
    """
    M3a 真正实现的客户端。使用 httpx 直连,支持重试与错误分类。
    """

    def __init__(self) -> None:
        s = get_settings()
        if not s.ark_api_key:
            raise VolcanoAuthError("ark_api_key 未配置")
        self._client = httpx.AsyncClient(
            base_url=s.ark_base_url,
            headers={
                "Authorization": f"Bearer {s.ark_api_key}",
                "Content-Type": "application/json",
            },
            timeout=60.0,
            trust_env=False,
        )
        self._settings = s

    async def _request_with_retry(self, method: str, path: str, json_body: dict | None = None) -> dict:
        last_exc: Exception | None = None
        for attempt in range(self._settings.ai_retry_max):
            try:
                logger.info(f"Real Volcano Request: {method} {path} (attempt {attempt+1})")
                resp = await self._client.request(method, path, json=json_body)
                logger.info(f"Real Volcano Response: {resp.status_code}")
                classify_http(resp)
                return resp.json()
            except httpx.HTTPError as e:
                volcano_err = classify_exception(e)
                if isinstance(volcano_err, (VolcanoServerError, VolcanoTimeoutError)):
                    last_exc = volcano_err
                    await asyncio.sleep(self._settings.ai_retry_base_sec * (4**attempt))
                    continue
                raise volcano_err
            except VolcanoRateLimitError as e:
                last_exc = e
                delay = e.retry_after or (self._settings.ai_retry_base_sec * (4**attempt))
                await asyncio.sleep(delay)
            except (VolcanoServerError, VolcanoTimeoutError) as e:
                last_exc = e
                await asyncio.sleep(self._settings.ai_retry_base_sec * (4**attempt))
            except VolcanoError:
                raise  # 不可重试的错误(Auth/Param/ContentFilter)直接抛出
        raise last_exc or VolcanoServerError("exhausted retries")

    async def chat_completions(self, model: str, messages: list[dict], **kwargs: Any) -> Any:
        body = {"model": model, "messages": messages, **kwargs}
        resp_json = await self._request_with_retry("POST", "/chat/completions", body)
        resp = _ChatResponse.from_dict(resp_json)
        print(f"\n[AI Chat Output] Model: {model}\nContent: {resp.choices[0].message.content}\n")
        return resp

    async def image_generations(
        self,
        model: str,
        prompt: str,
        *,
        references: list[str] | None = None,
        n: int = 1,
        size: str | None = None,
        **kwargs: Any,
    ) -> Any:
        if references:
            body = {
                "model": model,
                "prompt": prompt,
                "image": references,
                "response_format": "url",
                "watermark": False,
                **kwargs,
            }
        else:
            body = {
                "model": model,
                "prompt": prompt,
                "response_format": "url",
                "watermark": False,
                **kwargs,
            }

        if size:
            body["size"] = size
        if n != 1:
            body["n"] = n

        resp_json = await self._request_with_retry("POST", "/images/generations", body)
        urls = [item.get("url") for item in resp_json.get("data", [])]
        print(f"\n[AI Image Output] Model: {model}\nURLs: {urls}\n")
        return resp_json

    async def video_generations_create(
        self,
        *,
        model: str,
        prompt: str,
        references: list[str],
        duration: int | None,
        resolution: str,
        ratio: str,
        generate_audio: bool = False,
        watermark: bool = False,
        return_last_frame: bool = True,
        execution_expires_after: int = 3600,
    ) -> dict:
        content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
        for url in references:
            content.append({"type": "image_url", "role": "reference_image", "image_url": {"url": url}})
        body = {
            "model": model,
            "content": content,
            "resolution": resolution,
            "ratio": ratio,
            "generate_audio": generate_audio,
            "watermark": watermark,
            "return_last_frame": return_last_frame,
            "execution_expires_after": execution_expires_after,
        }
        if duration is not None:
            body["duration"] = duration
        return await self._request_with_retry("POST", "/contents/generations/tasks", body)

    async def video_generations_get(self, task_id: str) -> dict:
        return await self._request_with_retry("GET", f"/contents/generations/tasks/{task_id}", None)


def get_volcano_client() -> VolcanoClient:
    settings = get_settings()
    if settings.ai_provider_mode == "mock":
        return MockVolcanoClient()
    return RealVolcanoClient()
